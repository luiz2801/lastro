"""Dividend yield por ano do ativo e dos pares, só do que está em disco (sem rede).

A conta é a de `analise/proventos.py` (DPA do Yahoo ÷ `Adj Close`); os proventos e as cotações vêm
do cache de `series`/`proventos`.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from valuation.analise import proventos as prv
from valuation.config import DIR_RAW
from valuation.data import precos as prc


@dataclass(frozen=True)
class YieldDoGrupo:
    serie: pd.DataFrame  # índice = ano; `valor` (mediana) e `n`
    por_empresa: dict[str, pd.Series] = field(default_factory=dict)
    faltam: dict[str, str] = field(default_factory=dict)  # ticker -> motivo


def yield_por_ano(
    ticker: str, base: dt.date, anos: int, *, dir_raw: Path = DIR_RAW
) -> tuple[pd.Series | None, str | None]:
    """Yield por ano do papel em disco, ou `None` e o motivo."""
    pasta = dir_raw / "precos"
    simbolo = prc.simbolo_yahoo(ticker)
    dividendos = prc.dividendos_em_cache(simbolo, pasta)
    if dividendos is None:
        return None, "sem proventos em disco"
    historico = prc.historico_em_cache(simbolo, pasta)
    if historico is None or historico.empty:
        return None, "sem cotação em disco"
    return prv.dpa_anual(dividendos, historico, base, anos)["dividend_yield"], None


def yield_do_grupo(
    tickers: Sequence[str], base: dt.date, anos: int, *, dir_raw: Path = DIR_RAW
) -> YieldDoGrupo:
    por_empresa: dict[str, pd.Series] = {}
    faltam: dict[str, str] = {}
    for ticker in tickers:
        serie, motivo = yield_por_ano(ticker, base, anos, dir_raw=dir_raw)
        if serie is None:
            faltam[ticker] = motivo or ""
        else:
            por_empresa[ticker] = serie
    return YieldDoGrupo(prv.mediana_do_grupo(por_empresa), por_empresa, faltam)
