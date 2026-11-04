"""Ponto de entrada do `streamlit run`. Rota: `?ticker=PETR4` abre o ativo; sem ele, o início."""

from __future__ import annotations

import streamlit as st

from valuation.config import ErroConfiguracao
from valuation.data.cadastro import normalizar_ticker
from valuation.gui import ativo, inicio


def principal() -> None:
    st.set_page_config(page_title="Lastro — valuation", page_icon="📈", layout="wide")
    ticker = st.query_params.get("ticker")
    try:
        if ticker:
            ativo.mostrar(normalizar_ticker(ticker))
        else:
            inicio.mostrar()
    except ErroConfiguracao as e:
        st.error(f"Configuração inválida: {e}")
    st.divider()
    st.caption("Estudo pessoal; não é recomendação de investimento.")


principal()
