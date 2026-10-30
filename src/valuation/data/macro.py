"""Dados macro gratuitos: Banco Central (SGS e Focus) e Tesouro Transparente.

Cada dado é lido de duas fontes independentes e comparado (`validacao.cruzar`):

| Dado           | Principal                    | Alternativa                                    |
|----------------|------------------------------|------------------------------------------------|
| Selic          | SGS 432 (meta)               | SGS 11 (diária) anualizada                     |
| IPCA 12 meses  | SGS 13522                    | composição dos últimos 12 valores do SGS 433   |
| Dólar          | SGS 1 (PTAX venda)           | fechamento de `BRL=X` (yfinance)               |
| Rf em BRL      | NTN-F ~10 anos (Tesouro)     | NTN-B ~10 anos + IPCA do Focus (Fisher)        |

Respostas ficam em `data/raw/macro/` com `.meta.json`, via `http.baixar`.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar
from urllib.parse import quote

import numpy as np
import pandas as pd

from valuation.config import ValidacaoCruzada
from valuation.data.http import SessaoHttp, baixar
from valuation.data.validacao import ErroDadosExternos, Leitura, Validado, cruzar, manual

logger = logging.getLogger(__name__)

T = TypeVar("T")

URL_SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
URL_FOCUS = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais"
URL_TESOURO = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3/"
    "resource/796d2059-14e9-44e3-80c9-2d9e30b405c1/download/precotaxatesourodireto.csv"
)

SGS_SELIC_META = 432
SGS_SELIC_DIARIA = 11
SGS_CDI = 12
SGS_IPCA_MENSAL = 433
SGS_IPCA_12M = 13522
SGS_DOLAR = 1

TITULO_NTNF = "Tesouro Prefixado com Juros Semestrais"
TITULO_NTNB = "Tesouro IPCA+ com Juros Semestrais"
PRAZO_RF_ANOS = 10.0
PRAZO_RF_MIN_ANOS = 7.0
PRAZO_RF_MAX_ANOS = 13.0
DIAS_UTEIS_ANO = 252


def _baixar_texto(
    url: str,
    destino: Path,
    *,
    ttl: dt.timedelta,
    sessao: SessaoHttp,
    agora: dt.datetime,
    forcar: bool,
) -> str:
    arquivo = baixar(url, destino, ttl=ttl, sessao=sessao, agora=agora, forcar=forcar)
    return arquivo.caminho.read_text(encoding="utf-8")


def serie_sgs(
    codigo: int,
    inicio: dt.date,
    fim: dt.date,
    *,
    dir_raw: Path,
    ttl: dt.timedelta,
    sessao: SessaoHttp,
    agora: dt.datetime,
    forcar: bool = False,
) -> pd.Series[float]:
    """Série do SGS entre `inicio` e `fim` (inclusive), indexada por data, valores float."""
    url = (
        f"{URL_SGS.format(codigo=codigo)}?formato=json"
        f"&dataInicial={inicio:%d/%m/%Y}&dataFinal={fim:%d/%m/%Y}"
    )
    destino = dir_raw / "macro" / f"sgs_{codigo}_{inicio:%Y%m%d}_{fim:%Y%m%d}.json"
    bruto = json.loads(
        _baixar_texto(url, destino, ttl=ttl, sessao=sessao, agora=agora, forcar=forcar)
    )
    if not isinstance(bruto, list):
        raise ErroDadosExternos(f"SGS {codigo}: resposta inesperada: {str(bruto)[:200]}")
    if not bruto:
        raise ErroDadosExternos(f"SGS {codigo}: sem dados entre {inicio} e {fim}")
    datas = pd.to_datetime([x["data"] for x in bruto], format="%d/%m/%Y")
    valores = pd.to_numeric([x["valor"] for x in bruto])
    return pd.Series(valores, index=datas, name=str(codigo), dtype="float64").sort_index()


def _ultimo_ate(serie: pd.Series[float], data_base: dt.date) -> tuple[dt.date, float]:
    """Último valor com data <= `data_base` (a Selic meta do SGS traz datas futuras)."""
    valida = serie.loc[serie.index <= pd.Timestamp(data_base)]
    if valida.empty:
        raise ErroDadosExternos(f"Série {serie.name}: sem valor até {data_base}")
    return valida.index[-1].date(), float(valida.iloc[-1])


def focus_anual(
    indicador: str,
    data_base: dt.date,
    *,
    dir_raw: Path,
    ttl: dt.timedelta,
    sessao: SessaoHttp,
    agora: dt.datetime,
    forcar: bool = False,
) -> tuple[dt.date, dict[int, float]]:
    """Mediana das expectativas anuais do Focus na última reunião até `data_base`.

    Devolve (data da pesquisa, {ano: mediana em decimal}). Câmbio fica em R$/US$ (não é %).
    """
    filtro = f"Indicador eq '{indicador}' and Data le '{data_base:%Y-%m-%d}' and baseCalculo eq 0"
    url = (
        f"{URL_FOCUS}?$filter={quote(filtro)}&$orderby=Data%20desc&$top=40"
        "&$select=Data,DataReferencia,Mediana&$format=json"
    )
    nome = indicador.lower().replace(" ", "_").replace("/", "_")
    destino = dir_raw / "macro" / f"focus_{nome}_{data_base:%Y%m%d}.json"
    linhas = json.loads(
        _baixar_texto(url, destino, ttl=ttl, sessao=sessao, agora=agora, forcar=forcar)
    )
    valores = linhas.get("value") if isinstance(linhas, dict) else None
    if not valores:
        raise ErroDadosExternos(f"Focus {indicador}: sem expectativas até {data_base}")
    ultima = max(v["Data"] for v in valores)
    escala = 1.0 if indicador == "Câmbio" else 0.01
    por_ano = {
        int(v["DataReferencia"]): float(v["Mediana"]) * escala
        for v in valores
        if v["Data"] == ultima
    }
    return dt.date.fromisoformat(ultima), dict(sorted(por_ano.items()))


@dataclass(frozen=True)
class TituloTesouro:
    tipo: str
    vencimento: dt.date
    data_base: dt.date
    taxa: float  # decimal a.a.


def carregar_taxas_tesouro(
    *,
    dir_raw: Path,
    ttl: dt.timedelta,
    sessao: SessaoHttp,
    agora: dt.datetime,
    forcar: bool = False,
) -> pd.DataFrame:
    """CSV de taxas do Tesouro Direto (`;`, decimal `,`), apenas NTN-F e NTN-B."""
    destino = dir_raw / "macro" / "tesouro_precotaxa.csv"
    arquivo = baixar(URL_TESOURO, destino, ttl=ttl, sessao=sessao, agora=agora, forcar=forcar)
    bruto = pd.read_csv(arquivo.caminho, sep=";", decimal=",", encoding="latin-1", dtype=str)
    bruto.columns = [c.strip() for c in bruto.columns]
    faltam = {"Tipo Titulo", "Data Vencimento", "Data Base", "Taxa Compra Manha"} - set(
        bruto.columns
    )
    if faltam:
        raise ErroDadosExternos(f"CSV do Tesouro sem as colunas {sorted(faltam)}")
    bruto = bruto.loc[bruto["Tipo Titulo"].isin([TITULO_NTNF, TITULO_NTNB])]
    return pd.DataFrame(
        {
            "tipo": bruto["Tipo Titulo"],
            "vencimento": pd.to_datetime(bruto["Data Vencimento"], format="%d/%m/%Y"),
            "data_base": pd.to_datetime(bruto["Data Base"], format="%d/%m/%Y"),
            "taxa": pd.to_numeric(bruto["Taxa Compra Manha"].str.replace(",", "."), errors="coerce")
            / 100,
        }
    ).dropna()


def titulo_longo(taxas: pd.DataFrame, tipo: str, data_base: dt.date) -> TituloTesouro:
    """Título de `tipo` com vencimento mais próximo de 10 anos, na última data <= `data_base`."""
    do_tipo = taxas.loc[(taxas["tipo"] == tipo) & (taxas["data_base"] <= pd.Timestamp(data_base))]
    if do_tipo.empty:
        raise ErroDadosExternos(f"Tesouro: sem taxas de '{tipo}' até {data_base}")
    dia = do_tipo["data_base"].max()
    do_dia = do_tipo.loc[do_tipo["data_base"] == dia].copy()
    do_dia["prazo"] = (do_dia["vencimento"] - dia).dt.days / 365.25
    do_dia["dist"] = (do_dia["prazo"] - PRAZO_RF_ANOS).abs()
    escolhido = do_dia.sort_values("dist").iloc[0]
    if not PRAZO_RF_MIN_ANOS <= escolhido["prazo"] <= PRAZO_RF_MAX_ANOS:
        raise ErroDadosExternos(
            f"Tesouro: '{tipo}' em {dia.date()} não tem vencimento entre "
            f"{PRAZO_RF_MIN_ANOS:.0f} e {PRAZO_RF_MAX_ANOS:.0f} anos "
            f"(mais próximo: {escolhido['vencimento'].date()})"
        )
    return TituloTesouro(tipo, escolhido["vencimento"].date(), dia.date(), float(escolhido["taxa"]))


@dataclass(frozen=True)
class Macro:
    data_base: dt.date
    selic: Validado
    ipca_12m: Validado
    cambio: Validado
    rf_brl: Validado
    ipca_esperado: dict[int, float]
    data_focus: dt.date | None

    @property
    def avisos(self) -> list[str]:
        itens = (self.selic, self.ipca_12m, self.cambio, self.rf_brl)
        return [a for v in itens if (a := v.aviso)]


def _tentar(nome: str, f: Callable[[], T]) -> T | None:
    """Executa uma leitura; falha de uma fonte vira `None` (a outra pode cobrir)."""
    try:
        return f()
    except Exception as e:  # ErroDownload, ErroDadosExternos, JSON/CSV malformado...
        logger.warning("%s indisponível: %s", nome, e)
        return None


def carregar_macro(
    data_base: dt.date,
    *,
    tolerancias: ValidacaoCruzada,
    rf_override: float | None,
    cambio_alternativo: Leitura | None,
    dir_raw: Path,
    ttl: dt.timedelta,
    sessao: SessaoHttp,
    agora: dt.datetime,
    forcar: bool = False,
) -> Macro:
    """Selic, IPCA 12m, dólar, Rf em BRL e expectativas de IPCA, cada um validado em 2 fontes.

    `cambio_alternativo` vem de quem chama (fechamento do `BRL=X` no yfinance): esta camada
    não conhece provedores de preço.
    """
    inicio = data_base - dt.timedelta(days=430)

    def sgs(codigo: int) -> pd.Series[float]:
        return serie_sgs(
            codigo,
            inicio,
            data_base,
            dir_raw=dir_raw,
            ttl=ttl,
            sessao=sessao,
            agora=agora,
            forcar=forcar,
        )

    def selic_meta() -> Leitura:
        d, v = _ultimo_ate(sgs(SGS_SELIC_META), data_base)
        return Leitura(v / 100, f"SGS {SGS_SELIC_META} (meta)", d)

    def selic_diaria() -> Leitura:
        d, v = _ultimo_ate(sgs(SGS_SELIC_DIARIA), data_base)
        return Leitura((1 + v / 100) ** DIAS_UTEIS_ANO - 1, f"SGS {SGS_SELIC_DIARIA} (diária)", d)

    def ipca_12m_direto() -> Leitura:
        d, v = _ultimo_ate(sgs(SGS_IPCA_12M), data_base)
        return Leitura(v / 100, f"SGS {SGS_IPCA_12M}", d)

    def ipca_12m_composto() -> Leitura:
        mensal = sgs(SGS_IPCA_MENSAL)
        mensal = mensal.loc[mensal.index <= pd.Timestamp(data_base)].tail(12)
        if len(mensal) < 12:
            raise ErroDadosExternos(f"IPCA mensal: só {len(mensal)} meses disponíveis")
        acumulado = float(np.prod(1 + mensal.to_numpy() / 100) - 1)
        return Leitura(
            acumulado, f"SGS {SGS_IPCA_MENSAL} (12 meses compostos)", mensal.index[-1].date()
        )

    def dolar() -> Leitura:
        d, v = _ultimo_ate(sgs(SGS_DOLAR), data_base)
        return Leitura(v, f"SGS {SGS_DOLAR} (PTAX venda)", d)

    selic = cruzar(
        "Selic",
        _tentar("Selic meta", selic_meta),
        _tentar("Selic diária", selic_diaria),
        tolerancia=tolerancias.selic_abs,
    )
    ipca_12m = cruzar(
        "IPCA 12m",
        _tentar("IPCA 12m", ipca_12m_direto),
        _tentar("IPCA mensal", ipca_12m_composto),
        tolerancia=tolerancias.ipca_abs,
    )
    cambio = cruzar(
        "Dólar (R$/US$)",
        _tentar("PTAX", dolar),
        cambio_alternativo,
        tolerancia=tolerancias.cambio_rel,
        relativa=True,
    )

    focus = _tentar(
        "Focus IPCA",
        lambda: focus_anual(
            "IPCA", data_base, dir_raw=dir_raw, ttl=ttl, sessao=sessao, agora=agora, forcar=forcar
        ),
    )
    data_focus, ipca_esperado = focus if focus else (None, {})

    if rf_override is not None:
        rf = manual("Rf BRL", rf_override)
    else:
        taxas = carregar_taxas_tesouro(
            dir_raw=dir_raw, ttl=ttl, sessao=sessao, agora=agora, forcar=forcar
        )
        ntnf = _tentar("NTN-F", lambda: titulo_longo(taxas, TITULO_NTNF, data_base))
        ntnb = _tentar("NTN-B", lambda: titulo_longo(taxas, TITULO_NTNB, data_base))
        principal = (
            Leitura(ntnf.taxa, f"NTN-F {ntnf.vencimento:%m/%Y} (Tesouro)", ntnf.data_base)
            if ntnf
            else None
        )
        alternativa = None
        if ntnb and ipca_esperado:
            ipca_lp = ipca_esperado[max(ipca_esperado)]
            alternativa = Leitura(
                (1 + ntnb.taxa) * (1 + ipca_lp) - 1,
                f"NTN-B {ntnb.vencimento:%m/%Y} + Focus {max(ipca_esperado)}",
                ntnb.data_base,
            )
        rf = cruzar("Rf BRL", principal, alternativa, tolerancia=tolerancias.rf_abs)

    return Macro(data_base, selic, ipca_12m, cambio, rf, ipca_esperado, data_focus)
