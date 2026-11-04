"""Aba Geral: cartões, cotação, múltiplos em série, indicadores e médias de comparação."""

from __future__ import annotations

import datetime as dt
from typing import cast

import pandas as pd
import streamlit as st

from valuation.analise import anomalias as an
from valuation.analise import serie_multiplos as sm
from valuation.contabil import ErroContabil
from valuation.gui import dados, grafico
from valuation.modelos import multiplos as mt
from valuation.saida import formato as fo
from valuation.saida import glossario as gl
from valuation.servicos import comparacao as scmp
from valuation.servicos import empresa as emp
from valuation.servicos import historico_mercado as hm

JANELAS = {"10 anos": 10, "5 anos": 5}
TRACO = "—"


def _ajuda(chave: str) -> str | None:
    termos = [t for t in gl.TERMOS if t.chave == chave]
    return f"{termos[0].definicao} {termos[0].interpretacao}" if termos else None


def _cartoes(series: hm.SeriesMercado, base: dt.date) -> None:
    c = hm.cartoes(series, base)
    if c is None:
        st.info(f"{TRACO} sem fechamento até {base:%d/%m/%Y} em disco.")
        return
    faixa = c.faixa_52_semanas
    colunas = st.columns(4)
    colunas[0].metric("Preço", fo.brl(c.preco), help=f"Fechamento de {c.data_preco:%d/%m/%Y}.")
    colunas[1].metric(
        "Mín./máx. 52 semanas",
        f"{fo.brl(faixa[0])} / {fo.brl(faixa[1])}" if faixa else TRACO,
    )
    colunas[2].metric("Market cap (R$ mi)", fo.formatar(c.market_cap, "mi"))
    colunas[3].metric(
        "Dividend yield", fo.formatar(c.dividend_yield, "%"), help=_ajuda("dividend_yield")
    )


def _grafico_cotacao(series: hm.SeriesMercado, base: dt.date) -> None:
    st.subheader("Cotação")
    periodo = st.radio(
        "Período",
        sm.PERIODOS,
        index=3,
        horizontal=True,
        key="periodo_cotacao",
        label_visibility="collapsed",
    )
    trecho = sm.cortar_periodo(series.cotacao, periodo, base)
    if trecho.empty:
        st.info(f"{TRACO} sem cotação em disco neste período.")
        return
    st.plotly_chart(grafico.cotacao(trecho, series.ticker), key="grafico_cotacao")
    st.caption("Fechamento ajustado por desdobramentos e grupamentos (não por dividendos).")


def _grafico_multiplos(series: hm.SeriesMercado, base: dt.date) -> None:
    st.subheader("Múltiplos na série histórica")
    nomes = [str(n) for n in series.multiplos.columns]
    esquerda, meio, direita = st.columns(3)
    nome = cast(
        mt.NomeMultiplo,
        esquerda.selectbox(
            "Indicador",
            nomes,
            format_func=lambda n: mt.ROTULOS[cast(mt.NomeMultiplo, n)],
            key="indicador_serie",
        ),
    )
    tipo = meio.selectbox(
        "Referência",
        list(an.ROTULOS_REFERENCIA),
        format_func=lambda r: an.ROTULOS_REFERENCIA[r],
        key="referencia_serie",
    )
    janela = direita.radio("Janela", list(JANELAS), horizontal=True, key="janela_serie")
    a = hm.analisar_multiplo(series, nome, JANELAS[janela], tipo, dados.settings(), base)
    if a.aviso_referencia:
        st.warning(a.aviso_referencia)
    if a.serie.notna().sum() == 0 and a.descartados.empty:
        st.info(f"{TRACO} sem pontos deste múltiplo na janela.")
        return
    rotulo = mt.ROTULOS[nome]
    figura = grafico.multiplo(a, rotulo, an.ROTULOS_REFERENCIA[tipo])
    st.plotly_chart(figura, key="grafico_multiplo")
    st.caption(
        f"Hoje: {fo.multiplo(nome, a.atual)} · {an.ROTULOS_REFERENCIA[tipo]}: "
        f"{fo.multiplo(nome, a.referencia)} · {len(a.descartados)} ponto(s) fora da referência · "
        f"{a.lacunas} mês(es) sem dado"
    )
    if len(a.descartados):
        with st.expander(f"Pontos fora da referência ({len(a.descartados)})"):
            motivos = a.descartados.value_counts()
            for motivo, quantos in motivos.items():
                st.write(
                    f"{quantos} ponto(s): {motivo}. Veja: {an.sugestao_alternativa(str(motivo))}."
                )
    if len(a.filtro.marcados):
        st.caption(f"{len(a.filtro.marcados)} ponto(s) fora de 1,5·IQR, mantidos no cálculo.")


def _indicadores(p: emp.Padronizada, ticker: str, base: dt.date) -> None:
    st.subheader("Indicadores")
    visao = st.radio("Visão", ["Hoje", "Histórico"], horizontal=True, key="visao_indicadores")
    try:
        serie = dados.serie_indicadores(p, ticker, base, 10 if visao == "Histórico" else 1)
    except ErroContabil as e:
        st.error(f"Indicadores indisponíveis: {e}")
        return
    if visao == "Histórico":
        linhas = {
            rotulo: [fo.formatar(v, unidade) for v in serie.tabela[chave]]
            for chave, (rotulo, unidade, _) in serie.definicoes.items()
        }
        st.dataframe(
            pd.DataFrame.from_dict(linhas, orient="index", columns=serie.colunas), width="stretch"
        )
        return
    st.caption(serie.colunas[-1])
    colunas = st.columns(len(serie.definicoes))
    for coluna, (chave, (rotulo, unidade, termo)) in zip(
        colunas, serie.definicoes.items(), strict=True
    ):
        coluna.metric(
            rotulo, fo.formatar(float(serie.tabela[chave].iloc[-1]), unidade), help=_ajuda(termo)
        )


def _medidas_validas(medidas: list[scmp.Medida]) -> int:
    return sum(m.fundamentos is not None for m in medidas)


def _tabela_comparacao(
    series: hm.SeriesMercado,
    pares: list[scmp.Medida],
    ibovespa: list[scmp.Medida] | None,
    tipo: an.Referencia,
) -> pd.DataFrame:
    coluna_pares = f"Pares do setor (n = {_medidas_validas(pares)})"
    linhas: list[dict[str, str]] = []
    for coluna in series.multiplos.columns:
        nome = cast(mt.NomeMultiplo, str(coluna))
        ultimo = float(series.multiplos[coluna].iloc[-1]) if len(series.multiplos) else float("nan")
        do_par = scmp.referencia_do_grupo(pares, nome, tipo, dados.settings())
        linha = {
            "Múltiplo": mt.ROTULOS[nome],
            series.ticker: fo.multiplo(nome, ultimo),
            coluna_pares: fo.multiplo(nome, do_par.valor),
        }
        if ibovespa is not None:
            do_ibov = scmp.referencia_do_grupo(ibovespa, nome, tipo, dados.settings())
            linha[f"Ibovespa (n = {_medidas_validas(ibovespa)})"] = fo.multiplo(nome, do_ibov.valor)
        linhas.append(linha)
    return pd.DataFrame(linhas)


def _comparacao(
    series: hm.SeriesMercado,
    p: emp.Padronizada,
    cadastro: pd.DataFrame,
    base: dt.date,
) -> None:
    st.subheader("Médias de comparação (valor de hoje)")
    tipo = cast(an.Referencia, st.session_state.get("referencia_serie", "mediana"))
    setor = dados.setor(p.premissas.pares.setor)
    tickers = scmp.tickers_pares(p.premissas, p.empresa.tickers, setor)
    if not tickers:
        st.info(f"{TRACO} {series.ticker} sem pares definidos (`pares.setor` no YAML da empresa).")
    pares = dados.medidas(tickers, cadastro, base) if tickers else []
    financeira = p.plano.tipo == "financeira"
    chave = f"ibovespa_{series.ticker}"
    ibovespa = None
    if st.session_state.get(chave):
        universo = scmp.tickers_ibovespa(dados.universo(), financeira)
        with st.spinner("Medindo as empresas em disco..."):
            ibovespa = dados.medidas(universo, cadastro, base)
    elif st.button("Comparar com o Ibovespa", key=f"botao_{chave}"):
        st.session_state[chave] = True
        st.rerun()
    tabela = _tabela_comparacao(series, pares, ibovespa, tipo)
    st.dataframe(tabela, hide_index=True, width="stretch")
    grupo = "financeiras" if financeira else "não financeiras"
    st.caption(
        f"{an.ROTULOS_REFERENCIA[tipo]} só das empresas já em disco, {grupo}, com o mesmo "
        "tratamento de anomalias. O n conta as empresas medidas; em cada múltiplo, as anomalias "
        "saem da conta."
    )
    sem_dado = [m for m in [*pares, *(ibovespa or [])] if m.fundamentos is None]
    if sem_dado:
        with st.expander(f"Empresas fora da conta ({len(sem_dado)})"):
            for m in sem_dado:
                st.write(f"{m.ticker}: {m.motivo}")


def mostrar(
    ticker: str,
    p: emp.Padronizada,
    cadastro: pd.DataFrame,
    base: dt.date,
) -> None:
    series = dados.series(p, ticker, base)
    if series is None:
        st.info(f"{TRACO} sem cotação de {ticker} em disco. Clique em **Atualizar** para baixá-la.")
        _indicadores(p, ticker, base)
        return
    _cartoes(series, base)
    for aviso in series.avisos:
        st.warning(aviso)
    _grafico_cotacao(series, base)
    _grafico_multiplos(series, base)
    _indicadores(p, ticker, base)
    _comparacao(series, p, cadastro, base)
