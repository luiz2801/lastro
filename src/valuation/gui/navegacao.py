"""Barra lateral de todas as páginas: busca e Início."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from valuation.gui import dados

CHAVE_BUSCA = "busca_ativo"


def _nomes(cadastro: pd.DataFrame | None) -> dict[str, str]:
    if cadastro is None or "nome_comercial" not in cadastro:
        return {}
    return {
        str(linha.ticker): str(linha.nome_comercial or linha.razao_social)
        for linha in cadastro.itertuples()
    }


def _ao_escolher() -> None:
    """Num callback: o valor volta a vazio, e voltar ao início não reabre o ativo."""
    escolhido = st.session_state.get(CHAVE_BUSCA)
    if escolhido:
        st.query_params.clear()
        st.query_params["ticker"] = escolhido
    st.session_state[CHAVE_BUSCA] = None


def _ir_para_inicio() -> None:
    st.query_params.clear()


def mostrar() -> None:
    nomes = _nomes(dados.cadastro())
    tickers = [e.ticker for e in dados.universo()]
    with st.sidebar:
        st.selectbox(
            "Buscar ativo",
            tickers,
            index=None,
            placeholder="Digite o ticker ou o nome",
            format_func=lambda t: f"{t} — {nomes[t]}" if t in nomes else t,
            key=CHAVE_BUSCA,
            on_change=_ao_escolher,
        )
        st.button("Início", key="ir_inicio", width="stretch", on_click=_ir_para_inicio)
