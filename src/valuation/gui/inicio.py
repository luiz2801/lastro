"""Página inicial: busca de ativo e favoritas, a partir do que já está em disco."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from valuation.gui import acoes, dados
from valuation.saida import formato as fo
from valuation.servicos import atualizacao as atu


def abrir(ticker: str) -> None:
    st.query_params["ticker"] = ticker
    st.rerun()


def _busca() -> None:
    tickers = [e.ticker for e in dados.universo()]
    escolhido = st.selectbox(
        "Buscar ativo", tickers, index=None, placeholder="Digite o ticker (ex.: PETR4)"
    )
    if escolhido:
        abrir(escolhido)


def _tabela_favoritas(tickers: list[str], hoje: dt.date) -> pd.DataFrame:
    linhas = []
    for ticker in tickers:
        r = dados.resumo_favorito(ticker)
        if r is None:
            linhas.append({"Ticker": ticker, "Última rodada": "sem rodada"})
            continue
        linhas.append(
            {
                "Ticker": ticker,
                "Última rodada": f"{r.data_base:%d/%m/%Y} (há {r.idade_dias(hoje)} d)",
                "Perfil": r.perfil,
                "Preço": fo.preco_curto(r.preco),
                "Valor ponderado": fo.preco_curto(r.valor_ponderado),
                "Preço máx. de compra": fo.preco_curto(r.preco_maximo_compra),
                "Upside": fo.pct(r.upside),
                "Avisos": str(r.n_avisos),
            }
        )
    colunas = [
        "Ticker",
        "Última rodada",
        "Perfil",
        "Preço",
        "Valor ponderado",
        "Preço máx. de compra",
        "Upside",
        "Avisos",
    ]
    return pd.DataFrame(linhas, columns=colunas).fillna("—")


def _favoritas(hoje: dt.date) -> None:
    st.subheader("Favoritas")
    tickers = dados.favoritos()
    if not tickers:
        st.info("Nenhuma favorita. Use `valuation favoritos adicionar TICKER`.")
        return
    st.dataframe(_tabela_favoritas(tickers, hoje), hide_index=True, width="stretch")
    colunas = st.columns(min(len(tickers), 6))
    for i, ticker in enumerate(tickers):
        if colunas[i % len(colunas)].button(ticker, key=f"abrir_{ticker}"):
            abrir(ticker)
    if st.button("Atualizar favoritas"):
        execucao = acoes.executar("Atualizando favoritas", atu.atualizar_favoritas())
        if execucao.ok:
            st.rerun()
        acoes.mostrar_falha(execucao)


def mostrar() -> None:
    st.title("Lastro")
    _busca()
    _favoritas(dt.date.today())
