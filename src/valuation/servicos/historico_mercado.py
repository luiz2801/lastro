"""Cotação e série histórica de múltiplos de um ativo (ADR 0023).

`carregar_series` lê só o que está em disco. `baixar_series` é quem usa a rede, e a GUI só o chama a
pedido do usuário ou para ativo sem nenhum cache.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field, replace
from pathlib import Path

import pandas as pd

from valuation.analise import anomalias as an
from valuation.analise import indicadores as ind
from valuation.analise import serie_multiplos as sm
from valuation.config import DIR_PROCESSED, DIR_RAW, Settings
from valuation.contabil import ErroContabil
from valuation.contabil import padronizacao as pad
from valuation.data import cadastro as cad
from valuation.data import cvm
from valuation.data import precos as prc
from valuation.data.http import SessaoHttp
from valuation.data.validacao import ErroDadosExternos
from valuation.modelos import ErroModelo
from valuation.modelos import multiplos as mt
from valuation.saida import arquivos as arq
from valuation.servicos import comparacao as cmp
from valuation.servicos import indicadores as sind
from valuation.servicos.empresa import Padronizada


@dataclass(frozen=True)
class SeriesMercado:
    ticker: str
    cotacao: pd.DataFrame  # índice = data; close, adj_close, volume
    multiplos: pd.DataFrame  # índice = último pregão do mês; uma coluna por múltiplo; NaN = lacuna
    market_cap: pd.Series
    vigencia: pd.Series  # data -> fim do período do LTM vigente
    inicio_composicao: dt.date | None
    avisos: list[str] = field(default_factory=list)
    nao_positivos: pd.DataFrame | None = None  # data x múltiplo: True = métrica ≤ 0 (não é lacuna)


@dataclass(frozen=True)
class CartoesCotacao:
    preco: float
    data_preco: dt.date
    faixa_52_semanas: tuple[float, float] | None
    market_cap: float
    dividend_yield: float


@dataclass(frozen=True)
class AnaliseMultiplo:
    """Um múltiplo na janela escolhida: a série inteira, o que saiu da referência e por quê."""

    nome: mt.NomeMultiplo
    serie: pd.Series
    filtro: an.Filtro
    atual: float
    referencia: float
    descartados: pd.Series  # data -> motivo; inclui métrica ≤ 0
    lacunas: int
    aviso_referencia: str | None


def _dir_precos(dir_raw: Path) -> Path:
    return dir_raw / "precos"


def baixar_series(
    empresa: cad.Empresa,
    ticker: str,
    settings: Settings,
    base: dt.date,
    agora: dt.datetime,
    *,
    sessao: SessaoHttp,
    forcar: bool = False,
    dir_raw: Path = DIR_RAW,
    dir_processed: Path = DIR_PROCESSED,
) -> list[str]:
    """Baixa cotação de cada classe, splits e os ITR antigos. Devolve avisos.

    Sem cotação do próprio papel ⇒ `ErroDadosExternos`; as demais faltas viram aviso.
    """
    avisos: list[str] = []
    yf = prc.YFinanceProvider(
        _dir_precos(dir_raw),
        dt.timedelta(hours=settings.cache_ttl_horas.precos),
        agora,
        forcar=forcar,
    )
    inicio = (pd.Timestamp(base) - pd.DateOffset(years=settings.historico_anos)).date()
    for classe in empresa.classes:
        try:
            yf.historico(prc.simbolo_yahoo(classe.ticker), inicio, base)
        except ErroDadosExternos as e:
            if classe.ticker == ticker:
                raise
            avisos.append(f"{classe.ticker} sem histórico de cotação: {e}")
    try:
        yf.splits(prc.simbolo_yahoo(ticker))
    except ErroDadosExternos as e:
        avisos.append(f"{ticker} sem lista de splits: {e}")
    cvm.coletar_series(
        cvm.AlvoCVM(empresa.cnpj, empresa.cd_cvm, empresa.escala_acoes),
        base.year,
        settings.historico_anos,
        dir_raw=dir_raw,
        dir_processed=dir_processed,
        ttl=dt.timedelta(hours=settings.cache_ttl_horas.cvm),
        sessao=sessao,
        agora=agora,
        forcar=forcar,
    )
    return avisos


def _contas_da_serie(p: Padronizada, dir_processed: Path) -> pd.DataFrame:
    """Contas com os ITR antigos, só em memória: `contas_padronizadas.parquet` não muda."""
    itr = cvm.ler_series_itr(dir_processed, p.empresa.cd_cvm)
    if itr is None or itr.empty:
        return p.contas
    demonstracoes = pd.concat(
        [pad.ler_demonstracoes(dir_processed, p.empresa.cd_cvm), itr], ignore_index=True
    )
    consolidado = bool(p.selecionadas["consolidado"].iloc[0])
    selecionadas = pad.selecionar_reapresentacoes(demonstracoes, consolidado=consolidado)
    return pad.padronizar(selecionadas, p.plano, ticker=p.premissas.ticker)


def _precos_em_cache(
    p: Padronizada, ticker: str, dir_raw: Path
) -> tuple[pd.DataFrame | None, dict[str, pd.Series]]:
    """Cotação do papel e `close` de cada classe com cache."""
    dir_precos = _dir_precos(dir_raw)
    cotacao = prc.historico_em_cache(prc.simbolo_yahoo(ticker), dir_precos)
    closes: dict[str, pd.Series] = {}
    for classe in p.empresa.classes:
        df = prc.historico_em_cache(prc.simbolo_yahoo(classe.ticker), dir_precos)
        if df is not None and not df.empty:
            closes[classe.ticker] = df["close"]
    return cotacao, closes


def _market_caps(
    empresa: cad.Empresa,
    composicao: pd.DataFrame,
    closes: dict[str, pd.Series],
    pontos: pd.DatetimeIndex,
) -> pd.Series:
    valores: dict[pd.Timestamp, float] = {}
    for ponto in pontos:
        precos: dict[str, float] = {}
        for t, serie in closes.items():
            ate = serie[serie.index <= ponto].dropna()
            if not ate.empty:
                precos[t] = float(ate.iloc[-1])
        try:
            valores[ponto] = prc.market_cap(empresa, composicao, precos, ponto.date()).valor
        except ErroDadosExternos:
            valores[ponto] = float("nan")
    return pd.Series(valores, dtype="float64")


def _fundamentos_vigentes(
    p: Padronizada,
    contas: pd.DataFrame,
    fins: list[pd.Timestamp],
    settings: Settings,
    avisos: list[str],
) -> dict[pd.Timestamp, mt.Fundamentos]:
    """Fundamentos em cada fim de período usado; LTM incompleto fica de fora, com aviso."""
    com_serie = replace(p, contas=contas)
    sem_cap = prc.MarketCap(float("nan"), (), dt.date.min, ())
    fundamentos: dict[pd.Timestamp, mt.Fundamentos] = {}
    for fim in fins:
        try:
            # `acoes` só entra no valor por ação, que aqui não é usado.
            fundamentos[fim] = sind.fundamentos(
                com_serie, sem_cap, settings, fim.date(), 1.0, acoes=1
            )
        except (ErroContabil, ErroModelo) as e:
            avisos.append(f"LTM de {fim:%d/%m/%Y} indisponível, lacuna na série: {e}")
    return fundamentos


def carregar_series(
    p: Padronizada,
    ticker: str,
    settings: Settings,
    base: dt.date,
    *,
    dir_raw: Path = DIR_RAW,
    dir_processed: Path = DIR_PROCESSED,
) -> SeriesMercado | None:
    """Série do que está em disco, sem rede; `None` se não há cotação do papel em cache."""
    cotacao, closes = _precos_em_cache(p, ticker, dir_raw)
    if cotacao is None or cotacao.empty:
        return None
    avisos: list[str] = []
    pontos = sm.pontos_mensais(pd.DatetimeIndex(cotacao.index), base, settings.historico_anos)
    nomes = ind.MERCADO_FINANCEIRA if p.plano.tipo == "financeira" else ind.MERCADO
    vazio = pd.Series(float("nan"), index=pontos, dtype="float64")
    composicao = cvm.ler_composicao_serie(dir_processed, p.empresa.cd_cvm)
    if p.moeda != "BRL":
        avisos.append(f"Série de múltiplos só em BRL; {ticker} reporta em {p.moeda}.")
        composicao = None
    if composicao is None or composicao.empty:
        if p.moeda == "BRL":
            avisos.append(f"{ticker} sem composição do capital em disco: múltiplos em lacuna.")
        multiplos = pd.DataFrame({n: vazio for n in nomes}, index=pontos)
        return SeriesMercado(ticker, cotacao, multiplos, vazio, vazio, None, avisos)

    splits = prc.splits_em_cache(prc.simbolo_yahoo(ticker), _dir_precos(dir_raw))
    if splits is None:
        avisos.append(
            f"{ticker} sem lista de splits em disco: quantidade de ações sem ajuste. Clique em "
            "Atualizar."
        )
        splits = pd.Series(dtype="float64", index=pd.DatetimeIndex([]))
    else:
        avisos += sm.conferir_splits(composicao, splits)
    inicio_composicao = pd.Timestamp(composicao["dt_refer"].min()).date()
    if pontos.size and pontos[0].date() < inicio_composicao:
        avisos.append(
            f"A CVM só publica a quantidade de ações desde {inicio_composicao:%d/%m/%Y}: múltiplos "
            "em lacuna antes disso."
        )
    if cvm.ler_series_itr(dir_processed, p.empresa.cd_cvm) is None:
        avisos.append("Sem os ITR antigos em disco: LTM anual até 2024. Clique em Atualizar.")

    caps = _market_caps(p.empresa, sm.acoes_na_base_atual(composicao, splits), closes, pontos)
    contas = _contas_da_serie(p, dir_processed)
    entradas = sm.datas_de_entrada(
        sind.datas_com_ltm(contas),
        cvm.ler_datas_divulgacao(dir_processed, p.empresa.cd_cvm),
    )
    vigentes = sm.vigencia(pontos, entradas)
    usados = sorted(pd.Timestamp(d) for d in vigentes[caps.notna()].dropna().unique())
    fundamentos = _fundamentos_vigentes(p, contas, usados, settings, avisos)
    multiplos = pd.DataFrame(
        {n: sm.serie_multiplo(n, caps, vigentes, fundamentos) for n in nomes}, index=pontos
    )
    nao_positivos = pd.DataFrame(
        {n: sm.denominador_nao_positivo(n, vigentes[caps.notna()], fundamentos) for n in nomes},
        index=pontos,
    ).fillna(False)
    return SeriesMercado(
        ticker, cotacao, multiplos, caps, vigentes, inicio_composicao, avisos, nao_positivos
    )


def cartoes(series: SeriesMercado, base: dt.date) -> CartoesCotacao | None:
    """Valores de hoje; `None` se não há fechamento até a data-base."""
    fechamentos = series.cotacao.loc[series.cotacao.index <= pd.Timestamp(base), "close"].dropna()
    if fechamentos.empty:
        return None
    caps = series.market_cap.dropna()
    ultimo_dy = series.multiplos["dividend_yield"].iloc[-1] if len(series.multiplos) else None
    return CartoesCotacao(
        float(fechamentos.iloc[-1]),
        pd.Timestamp(fechamentos.index[-1]).date(),
        arq.faixa_52_semanas(series.cotacao, base),
        float(caps.iloc[-1]) if not caps.empty else float("nan"),
        float("nan") if ultimo_dy is None else float(ultimo_dy),
    )


def analisar_multiplo(
    series: SeriesMercado,
    nome: mt.NomeMultiplo,
    janela_anos: int,
    tipo: an.Referencia,
    settings: Settings,
    base: dt.date,
) -> AnaliseMultiplo:
    """Filtra a janela e calcula a referência. "Atual" é o último ponto, sem preenchimento."""
    inicio = pd.Timestamp(base) - pd.DateOffset(years=janela_anos)
    serie = series.multiplos.loc[series.multiplos.index > inicio, nome]
    filtro = an.filtrar(serie, an.CLASSES[nome], cmp.corte_fixo(settings, nome))
    motivos = filtro.descartados.copy()
    if series.nao_positivos is not None and an.CLASSES[nome] is an.Classe.POSITIVO:
        marcas = series.nao_positivos.loc[serie.index, nome]
        extra = pd.Series("múltiplo ≤ 0", index=marcas[marcas].index, dtype="object")
        motivos = pd.concat([motivos, extra]).sort_index()
    return AnaliseMultiplo(
        nome=nome,
        serie=serie,
        filtro=filtro,
        atual=float(serie.iloc[-1]) if len(serie) else float("nan"),
        referencia=an.referencia(filtro, tipo),
        descartados=motivos,
        lacunas=int(serie.isna().sum()) - int(motivos.index.isin(serie[serie.isna()].index).sum()),
        aviso_referencia=an.AVISO_MEDIA_SIMPLES if tipo == "media_simples" else None,
    )
