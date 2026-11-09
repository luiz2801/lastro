"""Aba Dividendos: DPA por ano, total de 12 meses e proventos por data ex (só lê o disco).

Fonte: yfinance (`series TICKER` baixa). O Yahoo não separa dividendo de JCP nem informa a data de
pagamento. O yield usa o `Adj Close`, como o comando `proventos`.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from valuation import config as cfg
from valuation.analise import proventos as prv
from valuation.gui import cartoes, grafico
from valuation.saida import formato as fo
from valuation.servicos import historico_mercado as hm

TRACO = "—"
ANOS = 10


def mostrar(ticker: str, series: hm.SeriesMercado | None, base: dt.date) -> None:
    dividendos = hm.dividendos_em_disco(ticker, dir_raw=cfg.DIR_RAW)
    if series is None or dividendos is None:
        st.info(
            f"{TRACO} sem proventos de {ticker} em disco. Clique em **Atualizar** para baixá-los."
        )
        return
    historico = series.cotacao
    dpa12, yield12 = prv.dpa_12m(dividendos, historico, base)
    st.markdown(
        cartoes.secao(
            "Últimos 12 meses",
            [
                cartoes.cartao("Dividendo por ação", fo.brl(dpa12)),
                cartoes.cartao("Dividend yield", fo.formatar(yield12, "%", 2)),
            ],
            f"Datas ex de {base - dt.timedelta(days=365):%d/%m/%Y} a {base:%d/%m/%Y}. Yield sobre "
            "o Adj Close (ajustado por dividendos).",
        ),
        unsafe_allow_html=True,
    )
    por_ano = prv.dpa_anual(dividendos, historico, base, ANOS)
    st.subheader("Dividendo por ação por ano")
    st.plotly_chart(grafico.dpa_anual(por_ano), width="stretch")
    st.caption(f"Ano de {base.year} parcial (em cinza), até {base:%d/%m/%Y}.")
    tabela = pd.DataFrame(
        {
            "Ano": [f"{a} (parcial)" if p else str(a) for a, p in por_ano["parcial"].items()],
            "DPA": [fo.brl(v) for v in por_ano["dpa"]],
            "Proventos": por_ano["n_proventos"].astype(int).to_numpy(),
            "Adj Close": [fo.brl(v) for v in por_ano["preco"]],
            "Dividend yield": [fo.formatar(v, "%", 2) for v in por_ano["dividend_yield"]],
        }
    ).iloc[::-1]
    st.dataframe(tabela, hide_index=True, width="stretch")

    st.subheader("Proventos por data ex")
    ate_base = dividendos[dividendos.index <= pd.Timestamp(base)]
    detalhe = pd.DataFrame(
        {
            "Data ex": [pd.Timestamp(str(d)).strftime("%d/%m/%Y") for d in ate_base.index[::-1]],
            "Valor por ação": [fo.brl(float(v)) for v in ate_base.to_numpy()[::-1]],
        }
    )
    st.dataframe(detalhe, hide_index=True, width="stretch")
    st.caption(
        "Fonte: yfinance. Sem tipo (dividendo ou JCP) nem data de pagamento: o Yahoo não traz. "
        "O Adj Close deixa o yield dos anos antigos acima do yield sobre o preço da época."
    )
