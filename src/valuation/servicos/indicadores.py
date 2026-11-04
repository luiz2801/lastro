"""Indicadores por ativo: série histórica (anual + LTM) e múltiplos de mercado."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pandas as pd

from valuation.analise import anomalias as an
from valuation.analise import indicadores as ind
from valuation.config import Settings
from valuation.contabil import ErroContabil
from valuation.contabil import financeiras as fin
from valuation.contabil import nao_financeiras as nf
from valuation.contabil import periodos as per
from valuation.data import precos as prc
from valuation.modelos import multiplos as mt
from valuation.modelos import ponte as pt
from valuation.servicos.empresa import Padronizada
from valuation.servicos.mercado import Mercado


@dataclass(frozen=True)
class TabelaIndicadores:
    """Uma linha por período, na ordem de `colunas`; a última é o LTM."""

    tabela: pd.DataFrame
    colunas: list[str]
    definicoes: dict[str, tuple[str, str, str]]  # indicador -> (rótulo, unidade, glossário)
    financeira: bool


@dataclass(frozen=True)
class IndicadoresMercado:
    fundamentos: mt.Fundamentos
    multiplos: dict[str, float]


def datas_com_ltm(contas: pd.DataFrame) -> pd.Index:
    """Datas com fluxos acumulados e balanço: os pontos em que o LTM pode ser calculado."""
    return per.acumulado_no_ano(contas).index.intersection(per.saldos(contas).index)


def data_balanco(contas: pd.DataFrame, base: dt.date) -> pd.Timestamp:
    """Última data até a data-base com fluxos acumulados e balanço (ponto do LTM)."""
    comuns = datas_com_ltm(contas)
    comuns = comuns[comuns <= pd.Timestamp(base)]
    if comuns.empty:
        raise ErroContabil(f"Nenhuma demonstração até {base}.")
    return pd.Timestamp(comuns.max())


def _anos_encerrados(indice: pd.Index, base: dt.date) -> list[object]:
    """Exercícios (índice anual) encerrados em 31/12 até a data-base."""
    return [a for a in indice if dt.date(int(a), 12, 31) <= base]


def serie_indicadores(
    p: Padronizada, settings: Settings, base: dt.date, anos: int
) -> TabelaIndicadores:
    """Indicadores dos últimos `anos` exercícios encerrados até a data-base, mais o LTM."""
    financeira = p.plano.tipo == "financeira"
    data_bal = data_balanco(p.contas, base)
    if financeira:
        anual = fin.metricas(per.anual(p.contas))
        ltm = fin.metricas_ltm(p.contas, dt_fim=data_bal)
        definicoes = ind.HISTORICOS_FINANCEIRA
        calcular = ind.historicos_financeira
    else:
        aliquota = settings.impostos.aliquota_nominal
        anual = nf.metricas(per.anual(p.contas), aliquota_nominal=aliquota, ajustes=p.ajustes)
        ltm = nf.metricas_ltm(
            p.contas, aliquota_nominal=aliquota, dt_fim=data_bal, ajustes=p.ajustes
        )
        definicoes = ind.HISTORICOS
        calcular = ind.historicos
    anual = anual.loc[_anos_encerrados(anual.index, base)].tail(anos)
    tabela = calcular(pd.concat([anual, ltm.to_frame().T]))
    colunas = [*map(str, anual.index), f"LTM {data_bal:%m/%Y}"]
    return TabelaIndicadores(tabela, colunas, definicoes, financeira)


@dataclass(frozen=True)
class TabelaBalanco:
    """Endividamento, liquidez e caixa: uma linha por período, a última é o LTM."""

    tabela: pd.DataFrame
    motivos: pd.DataFrame  # mesma forma de `tabela`; texto onde o valor é NaN
    colunas: list[str]


@dataclass(frozen=True)
class AnaliseIndicador:
    """Um indicador no histórico anual + LTM: o que saiu da referência, e por quê."""

    nome: str
    serie: pd.Series  # índice = rótulo do período
    filtro: an.Filtro | None  # `None` = sem tratamento (valor em R$)
    atual: float
    referencia: float
    descartados: pd.Series
    marcados: pd.Series
    motivos: pd.Series  # período -> por que falta
    aviso_referencia: str | None


def serie_balanco(
    p: Padronizada, settings: Settings, base: dt.date, anos: int
) -> TabelaBalanco | None:
    """Indicadores de `ind.BALANCO`; `None` para financeiras, cujo plano de contas não os tem."""
    if p.plano.tipo == "financeira":
        return None
    data_bal = data_balanco(p.contas, base)
    aliquota = settings.impostos.aliquota_nominal
    largo = per.anual(p.contas)
    anual = nf.metricas(largo, aliquota_nominal=aliquota, ajustes=p.ajustes)
    encerrados = _anos_encerrados(anual.index, base)[-anos:]
    ltm_largo = per.ltm(p.contas, data_bal)
    ltm = nf.metricas_ltm(p.contas, aliquota_nominal=aliquota, dt_fim=data_bal, ajustes=p.ajustes)
    tabela, motivos = ind.balanco_e_caixa(
        pd.concat([largo.loc[encerrados], ltm_largo.to_frame().T]),
        pd.concat([anual.loc[encerrados], ltm.to_frame().T]),
        ifrs16=p.ajustes.ifrs16,
    )
    return TabelaBalanco(tabela, motivos, [*map(str, encerrados), f"LTM {data_bal:%m/%Y}"])


def analisar_indicador(
    serie: pd.Series, motivos: pd.Series | None, nome: str, tipo: an.Referencia
) -> AnaliseIndicador:
    """Mesma regra dos múltiplos, com a classe do indicador. Sem classe (R$), nada é filtrado."""
    classe = an.CLASSES.get(nome)
    vazio = pd.Series(dtype="object")
    filtro = None if classe is None else an.filtrar(serie, classe)
    return AnaliseIndicador(
        nome=nome,
        serie=serie,
        filtro=filtro,
        atual=float(serie.iloc[-1]) if len(serie) else float("nan"),
        referencia=float("nan") if filtro is None else an.referencia(filtro, tipo),
        descartados=vazio if filtro is None else filtro.descartados,
        marcados=pd.Series(dtype="float64") if filtro is None else filtro.marcados,
        motivos=vazio if motivos is None else motivos.dropna(),
        aviso_referencia=an.AVISO_MEDIA_SIMPLES if tipo == "media_simples" else None,
    )


def fundamentos(
    p: Padronizada,
    cap: prc.MarketCap,
    settings: Settings,
    base: dt.date,
    dolar: float,
    acoes: int | None = None,
) -> mt.Fundamentos:
    """Métricas LTM no último balanço até a data-base e market cap, em BRL.

    `acoes` = quantidade usada no valor por ação (padrão: ON + PN do market cap).
    """
    data_bal = data_balanco(p.contas, base)
    acoes = sum(c.acoes for c in cap.classes) if acoes is None else acoes
    if p.plano.tipo == "financeira":
        return mt.fundamentos_financeira(
            p.premissas.ticker,
            fin.metricas_ltm(p.contas, dt_fim=data_bal),
            acoes=acoes,
            data_balanco=data_bal.date(),
            market_cap=cap.valor,
        )
    ltm = nf.metricas_ltm(
        p.contas,
        aliquota_nominal=settings.impostos.aliquota_nominal,
        dt_fim=data_bal,
        ajustes=p.ajustes,
    )
    itens = pt.itens_do_balanco(
        ltm,
        acoes=acoes,
        data_balanco=data_bal.date(),
        coligadas=p.premissas.ajustes.coligadas,
        minoritarios="contabil",
    )
    cambio = 1.0 if p.moeda == "BRL" else dolar
    return mt.fundamentos(p.premissas.ticker, ltm, itens=itens, market_cap=cap.valor, cambio=cambio)


def indicadores_de_mercado(
    p: Padronizada, mk: Mercado, settings: Settings, base: dt.date
) -> IndicadoresMercado:
    """Fundamentos LTM da data-base e os múltiplos de mercado (a mesma conta do `comparar`)."""
    f = fundamentos(p, mk.cap, settings, base, mk.macro.cambio.valor)
    return IndicadoresMercado(f, ind.de_mercado(f, financeira=p.plano.tipo == "financeira"))
