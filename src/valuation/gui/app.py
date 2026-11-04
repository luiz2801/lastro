"""Entrada do `streamlit run`. Rotas: `?ticker=PETR4`, `?pagina=perfil`; sem nada, o início."""

from __future__ import annotations

import datetime as dt

import streamlit as st

from valuation.config import ErroConfiguracao
from valuation.data.cadastro import normalizar_ticker
from valuation.gui import ativo, inicio, navegacao, pagina_perfil

# O `st.metric` corta o que não cabe com reticências, e número pela metade engana: quebra a linha.
CSS_CARTOES = """<style>
[data-testid="stMetricValue"], [data-testid="stMetricValue"] *,
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: clip !important;
}
</style>"""


def principal() -> None:
    st.set_page_config(page_title="Lastro — valuation", page_icon="📈", layout="wide")
    st.markdown(CSS_CARTOES, unsafe_allow_html=True)
    ticker = st.query_params.get("ticker")
    try:
        navegacao.mostrar()
        if st.query_params.get("pagina") == navegacao.PAGINA_PERFIL:
            pagina_perfil.mostrar(dt.date.today())
        elif ticker:
            ativo.mostrar(normalizar_ticker(ticker))
        else:
            inicio.mostrar()
    except ErroConfiguracao as e:
        st.error(f"Configuração inválida: {e}")
    st.divider()
    st.caption("Estudo pessoal; não é recomendação de investimento.")


principal()
