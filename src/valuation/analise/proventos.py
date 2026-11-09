"""Dividendo por ação (DPA) e dividend yield por ano-calendário, a partir dos proventos do Yahoo.

Função pura: recebe as séries e a data-base, não consulta rede nem relógio.

Convenções (decididas pelo usuário):
- DPA do ano = soma dos proventos com data ex no ano (o Yahoo já ajusta por splits).
- DY do ano = DPA ÷ último `Adj Close` do ano (ou da data-base, no ano corrente). O `Adj Close` é
  ajustado por dividendos, então fica abaixo do preço da época e o DY dos anos antigos sai maior
  que o yield realmente pago sobre o preço de então.
- Ano corrente (o da data-base) é marcado como parcial.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

COLUNAS = ["dpa", "n_proventos", "preco", "dividend_yield", "parcial"]


def dpa_anual(
    dividendos: pd.Series, historico: pd.DataFrame, data_base: dt.date, anos: int
) -> pd.DataFrame:
    """Tabela por ano (índice = ano, crescente) com `COLUNAS`, dos `anos` últimos anos.

    Só entram proventos com data ex até a data-base. Ano sem provento tem DPA 0. `preco` é NaN
    (e o DY também) se o histórico não cobrir o ano.
    """
    if anos < 1:
        raise ValueError("anos deve ser >= 1")
    base = pd.Timestamp(data_base)
    pagos = dividendos[dividendos.index <= base]
    anos_pagos = pd.DatetimeIndex(pagos.index).year
    anos_preco = pd.DatetimeIndex(historico.index).year
    primeiro = base.year - anos + 1
    linhas: dict[int, dict[str, object]] = {}
    for ano in range(primeiro, base.year + 1):
        do_ano = pagos[anos_pagos == ano]
        limite = min(pd.Timestamp(year=ano, month=12, day=31), base)
        no_ano = historico.loc[(anos_preco == ano) & (historico.index <= limite), "adj_close"]
        no_ano = no_ano.dropna()
        preco = float(no_ano.iloc[-1]) if not no_ano.empty else float("nan")
        dpa = float(do_ano.sum())
        linhas[ano] = {
            "dpa": dpa,
            "n_proventos": len(do_ano),
            "preco": preco,
            "dividend_yield": dpa / preco if preco > 0 else float("nan"),
            "parcial": ano == base.year,
        }
    tabela = pd.DataFrame.from_dict(linhas, orient="index", columns=COLUNAS)
    tabela.index.name = "ano"
    return tabela
