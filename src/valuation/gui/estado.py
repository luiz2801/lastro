"""Barra de estado: data-base, idade do cache por fonte e avisos."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

import streamlit as st

from valuation.servicos.cache import FonteCache


def texto_fonte(fonte: FonteCache, agora: dt.datetime) -> str:
    idade = fonte.idade_dias(agora)
    if idade is None:
        return f"{fonte.nome}: sem cache"
    return f"{fonte.nome}: hoje" if idade == 0 else f"{fonte.nome}: há {idade} d"


def mostrar(
    base: dt.date, fontes: Sequence[FonteCache], agora: dt.datetime, avisos: Sequence[str] = ()
) -> None:
    partes = [f"Data-base {base:%d/%m/%Y}", *(texto_fonte(f, agora) for f in fontes)]
    st.caption(" · ".join(partes))
    if avisos:
        with st.expander(f"Avisos ({len(avisos)})"):
            for aviso in avisos:
                st.warning(aviso)
