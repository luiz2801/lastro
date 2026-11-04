"""Página inicial: busca de ativo e favoritas, a partir do que já está em disco."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from valuation import config as cfg
from valuation.gui import acoes, dados
from valuation.saida import formato as fo
from valuation.servicos import atualizacao as atu
from valuation.servicos import favoritas as sfav


def abrir(ticker: str) -> None:
    st.query_params["ticker"] = ticker
    st.rerun()


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
        st.info(
            "Nenhuma favorita. Use a estrela na página do ativo ou "
            "`valuation favoritos adicionar TICKER`."
        )
        return
    st.dataframe(_tabela_favoritas(tickers, hoje), hide_index=True, width="stretch")
    colunas = st.columns(min(len(tickers), 6))
    for i, ticker in enumerate(tickers):
        coluna = colunas[i % len(colunas)]
        if coluna.button(ticker, key=f"abrir_{ticker}"):
            abrir(ticker)
        if coluna.button(f"Remover {ticker}", key=f"remover_{ticker}", type="tertiary"):
            sfav.remover(ticker, cfg.CAMINHO_FAVORITOS)
            st.rerun()
    if st.button("Atualizar favoritas"):
        execucao = acoes.executar("Atualizando favoritas", atu.atualizar_favoritas(tickers))
        if execucao.ok:
            st.rerun()
        acoes.mostrar_falha(execucao)


def mostrar() -> None:
    st.title("Lastro")
    st.caption("Busque um ativo na barra lateral.")
    _favoritas(dt.date.today())
