"""Barra lateral de todas as páginas: busca, Início, Perfil e o perfil usado nesta sessão."""

from __future__ import annotations

from typing import get_args

import pandas as pd
import streamlit as st

from valuation.gui import dados
from valuation.perfil import NomePerfil

CHAVE_BUSCA = "busca_ativo"
CHAVE_OVERRIDE = "perfil_override"
SEM_OVERRIDE = "questionario"
PAGINA_PERFIL = "perfil"


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


def _ir_para(pagina: str | None) -> None:
    st.query_params.clear()
    if pagina:
        st.query_params["pagina"] = pagina


def override() -> NomePerfil | None:
    """Perfil escolhido na barra lateral: vale só na sessão e nunca toca o JSON."""
    valor = st.session_state.get(CHAVE_OVERRIDE, SEM_OVERRIDE)
    return None if valor == SEM_OVERRIDE else valor


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
        st.button("Início", key="ir_inicio", width="stretch", on_click=_ir_para, args=(None,))
        st.button(
            "Perfil do investidor",
            key="ir_perfil",
            width="stretch",
            on_click=_ir_para,
            args=(PAGINA_PERFIL,),
        )
        opcoes = [SEM_OVERRIDE, *get_args(NomePerfil)]
        st.selectbox(
            "Perfil nesta sessão",
            opcoes,
            format_func=lambda o: "Do questionário" if o == SEM_OVERRIDE else str(o).capitalize(),
            key=CHAVE_OVERRIDE,
            help="Só nesta sessão, sem alterar o questionário gravado.",
        )
