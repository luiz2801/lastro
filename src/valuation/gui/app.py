"""Entrada do `streamlit run`. Rotas: `?ticker=PETR4`, `?pagina=perfil`; sem nada, o início."""

from __future__ import annotations

import datetime as dt

import streamlit as st

from valuation.config import ErroConfiguracao
from valuation.data.cadastro import normalizar_ticker
from valuation.gui import ativo, inicio, navegacao, pagina_perfil


def principal() -> None:
    st.set_page_config(page_title="Lastro — valuation", page_icon="📈", layout="wide")
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
