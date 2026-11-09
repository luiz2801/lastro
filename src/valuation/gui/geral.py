"""Aba Geral: cartões, cotação, múltiplos em série, indicadores e médias de comparação."""

from __future__ import annotations

import datetime as dt
from typing import cast

import pandas as pd
import streamlit as st

from valuation.analise import anomalias as an
from valuation.analise import indicadores as ind
from valuation.analise import serie_multiplos as sm
from valuation.contabil import ErroContabil
from valuation.gui import acoes, dados, grafico
from valuation.modelos import multiplos as mt
from valuation.saida import formato as fo
from valuation.saida import glossario as gl
from valuation.servicos import atualizacao as atu
from valuation.servicos import comparacao as scmp
from valuation.servicos import empresa as emp
from valuation.servicos import grupos as grp
from valuation.servicos import historico_mercado as hm
from valuation.servicos import indicadores as sind

JANELAS = {"10 anos": 10, "5 anos": 5}
TRACO = "—"
COLUNAS_POR_LINHA = 4
ROTULO_PARES = "Pares do setor"
ROTULO_IBOV = "Empresas do Ibovespa de hoje"
MOTIVO_BASILEIA = "índice regulatório não consta na DFP (fonte IF.data ainda não validada)"


def _ajuda(chave: str) -> str | None:
    termos = [t for t in gl.TERMOS if t.chave == chave]
    return f"{termos[0].definicao} {termos[0].interpretacao}" if termos else None


def _cartoes(series: hm.SeriesMercado, base: dt.date) -> None:
    c = hm.cartoes(series, base)
    if c is None:
        st.info(f"{TRACO} sem fechamento até {base:%d/%m/%Y} em disco.")
        return
    faixa = c.faixa_52_semanas
    colunas = st.columns(5)
    colunas[0].metric("Preço", fo.brl(c.preco), help=f"Fechamento de {c.data_preco:%d/%m/%Y}.")
    # Um cartão por valor: o st.metric corta texto longo, e "R$ mín / R$ máx" sumia.
    colunas[1].metric("Mínimo 52 semanas", fo.brl(faixa[0]) if faixa else TRACO)
    colunas[2].metric("Máximo 52 semanas", fo.brl(faixa[1]) if faixa else TRACO)
    colunas[3].metric("Market cap (R$ mi)", fo.formatar(c.market_cap, "mi", 2))
    colunas[4].metric(
        "Dividend yield", fo.formatar(c.dividend_yield, "%", 2), help=_ajuda("dividend_yield")
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


def _linhas_dos_grupos(
    grupos: list[tuple[str, grp.PainelGrupo, str, str]],
    nome: mt.NomeMultiplo,
    tipo: an.Referencia,
) -> list[grafico.LinhaGrupo]:
    linhas = []
    for rotulo, painel, cor, traco in grupos:
        serie = grp.referencia_em_serie(painel, nome, tipo, dados.settings())
        if serie is not None:
            linhas.append(grafico.LinhaGrupo(rotulo, serie, cor, traco))
    return linhas


def _baixar_grupo(rotulo: str, painel: grp.PainelGrupo, cadastro: pd.DataFrame) -> None:
    """Fora da conta, com o motivo, e o único caminho de rede: o clique."""
    if not painel.faltam:
        return
    with st.expander(f"{rotulo}: {len(painel.faltam)} empresa(s) fora da série"):
        for ticker, motivo in painel.faltam.items():
            st.write(f"{ticker}: {motivo}")
    if st.button(f"Baixar séries: {rotulo}", key=f"baixar_{rotulo}"):
        sem_demonstracoes = [
            t for t, m in painel.faltam.items() if not dados.ticker_tem_demonstracoes(t, cadastro)
        ]
        execucao = acoes.executar(
            f"Baixando séries: {rotulo}",
            atu.baixar_series_grupo(list(painel.faltam), sem_demonstracoes),
        )
        if execucao.ok:
            st.rerun()
        acoes.mostrar_falha(execucao)


def _grafico_multiplos(
    series: hm.SeriesMercado,
    base: dt.date,
    grupos: list[tuple[str, grp.PainelGrupo, str, str]],
    cadastro: pd.DataFrame,
) -> None:
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
    linhas = _linhas_dos_grupos(grupos, nome, tipo)
    figura = grafico.multiplo(a, rotulo, an.ROTULOS_REFERENCIA[tipo], linhas)
    st.plotly_chart(figura, key="grafico_multiplo")
    st.caption(
        f"Hoje: {fo.multiplo(nome, a.atual, 2)} · {an.ROTULOS_REFERENCIA[tipo]}: "
        f"{fo.multiplo(nome, a.referencia, 2)} · {len(a.descartados)} ponto(s) fora da "
        f"referência · {a.lacunas} mês(es) sem dado"
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
    for rotulo_grupo, painel, _, _ in grupos:
        st.caption(
            f"{rotulo_grupo}: {painel.em_disco} de {len(painel.tickers)} empresas em disco. "
            f"Mês com menos de {dados.settings().multiplos.min_pares} válidas fica em lacuna."
        )
        _baixar_grupo(rotulo_grupo, painel, cadastro)
    if any(rotulo_grupo == ROTULO_IBOV for rotulo_grupo, *_ in grupos):
        st.caption(
            "Ibovespa com a carteira de hoje aplicada ao passado (viés de sobrevivência), sem "
            "ponderar: não há composição histórica em fonte gratuita."
        )


def _indicadores(p: emp.Padronizada, ticker: str, base: dt.date) -> str:
    st.subheader("Indicadores")
    visao = st.radio("Visão", ["Hoje", "Histórico"], horizontal=True, key="visao_indicadores")
    try:
        serie = dados.serie_indicadores(p, ticker, base, 10 if visao == "Histórico" else 1)
    except ErroContabil as e:
        st.error(f"Indicadores indisponíveis: {e}")
        return visao
    if visao == "Histórico":
        linhas = {
            rotulo: [fo.formatar(v, unidade, 2) for v in serie.tabela[chave]]
            for chave, (rotulo, unidade, _) in serie.definicoes.items()
        }
        st.dataframe(
            pd.DataFrame.from_dict(linhas, orient="index", columns=serie.colunas), width="stretch"
        )
        return visao
    st.caption(serie.colunas[-1])
    colunas = st.columns(len(serie.definicoes))
    for coluna, (chave, (rotulo, unidade, termo)) in zip(
        colunas, serie.definicoes.items(), strict=True
    ):
        coluna.metric(
            rotulo, fo.formatar(float(serie.tabela[chave].iloc[-1]), unidade, 2), help=_ajuda(termo)
        )
    return visao


def _grade_balanco(t: sind.TabelaBalanco) -> None:
    st.caption(t.colunas[-1])
    for grupo, indicadores in ind.BALANCO.items():
        st.markdown(f"**{grupo}**")
        itens = list(indicadores.items())
        for inicio in range(0, len(itens), COLUNAS_POR_LINHA):
            colunas = st.columns(COLUNAS_POR_LINHA)
            for coluna, (chave, (rotulo, unidade, termo)) in zip(
                colunas, itens[inicio : inicio + COLUNAS_POR_LINHA], strict=False
            ):
                valor = float(t.tabela[chave].iloc[-1])
                coluna.metric(rotulo, fo.formatar(valor, unidade, 2), help=_ajuda(termo))
                if pd.isna(valor):
                    coluna.caption(str(t.motivos[chave].iloc[-1]))


def _tabela_balanco(t: sind.TabelaBalanco) -> None:
    for grupo, indicadores in ind.BALANCO.items():
        st.markdown(f"**{grupo}**")
        linhas = {
            rotulo: [fo.formatar(float(v), unidade, 2) for v in t.tabela[chave]]
            for chave, (rotulo, unidade, _) in indicadores.items()
        }
        st.dataframe(
            pd.DataFrame.from_dict(linhas, orient="index", columns=t.colunas), width="stretch"
        )
    motivos = {
        rotulo: sorted({str(m) for m in t.motivos[chave].dropna()})
        for indicadores in ind.BALANCO.values()
        for chave, (rotulo, _, _) in indicadores.items()
        if t.motivos[chave].notna().any()
    }
    if motivos:
        with st.expander(f"Por que há {TRACO} ({len(motivos)} indicador(es))"):
            for rotulo, textos in motivos.items():
                st.write(f"{rotulo}: {'; '.join(textos)}.")


def _grafico_balanco(t: sind.TabelaBalanco) -> None:
    definicoes = {c: d for grupo in ind.BALANCO.values() for c, d in grupo.items()}
    chave = st.selectbox(
        "Indicador no gráfico",
        list(definicoes),
        format_func=lambda c: definicoes[c][0],
        key="indicador_balanco",
    )
    rotulo, unidade, _ = definicoes[chave]
    tipo = cast(an.Referencia, st.session_state.get("referencia_serie", "mediana"))
    serie = pd.Series(t.tabela[chave].to_numpy(dtype="float64"), index=t.colunas, name=chave)
    motivos = pd.Series(t.motivos[chave].to_numpy(dtype="object"), index=t.colunas)
    a = sind.analisar_indicador(serie, motivos, chave, tipo)
    if a.aviso_referencia:
        st.warning(a.aviso_referencia)
    if serie.notna().sum() == 0:
        st.info(f"{TRACO} sem valor deste indicador: {'; '.join(sorted(set(a.motivos)))}.")
        return
    nome_referencia = an.ROTULOS_REFERENCIA[tipo]
    st.plotly_chart(grafico.indicador(a, rotulo, unidade, nome_referencia), key="grafico_balanco")
    partes = [f"Hoje: {fo.formatar(a.atual, unidade, 2)}"]
    if a.filtro is None:
        partes.append("valor em R$, sem referência")
    else:
        partes += [
            f"{nome_referencia}: {fo.formatar(a.referencia, unidade, 2)}",
            f"{len(a.descartados)} ponto(s) fora da referência",
            f"{len(a.marcados)} marcado(s) fora de 1,5·IQR, mantidos",
        ]
    partes.append(f"{len(a.motivos)} período(s) sem dado")
    st.caption(" · ".join(partes))


def _balanco(p: emp.Padronizada, ticker: str, base: dt.date, visao: str) -> None:
    st.subheader("Endividamento, liquidez e caixa")
    try:
        t = dados.serie_balanco(p, ticker, base, 10 if visao == "Histórico" else 1)
    except ErroContabil as e:
        st.error(f"Indicadores indisponíveis: {e}")
        return
    if t is None:
        st.metric("Índice de Basileia", TRACO, help=_ajuda("alavancagem"))
        st.caption(MOTIVO_BASILEIA)
        st.caption("Dívida, liquidez e caixa não se aplicam ao plano de contas das financeiras.")
        return
    if visao == "Histórico":
        _tabela_balanco(t)
        _grafico_balanco(t)
    else:
        _grade_balanco(t)


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
            series.ticker: fo.multiplo(nome, ultimo, 2),
            coluna_pares: fo.multiplo(nome, do_par.valor, 2),
        }
        if ibovespa is not None:
            do_ibov = scmp.referencia_do_grupo(ibovespa, nome, tipo, dados.settings())
            linha[f"Ibovespa (n = {_medidas_validas(ibovespa)})"] = fo.multiplo(
                nome, do_ibov.valor, 2
            )
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
    conjunto = dados.pares(p)
    tickers = conjunto.tickers
    if not tickers:
        st.info(f"{TRACO} {series.ticker} é o único do conjunto ({conjunto.origem}).")
    else:
        st.caption(f"Pares: {conjunto.origem}.")
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


def _grupos(
    series: hm.SeriesMercado,
    p: emp.Padronizada,
    cadastro: pd.DataFrame,
    base: dt.date,
) -> list[tuple[str, grp.PainelGrupo, str, str]]:
    """Painéis dos pares e, se o usuário pediu a comparação, do Ibovespa."""
    grupos: list[tuple[str, grp.PainelGrupo, str, str]] = []
    tickers = dados.pares(p).tickers
    if tickers:
        painel = dados.painel(tickers, cadastro, base)
        grupos.append((ROTULO_PARES, painel, grafico.LARANJA, "dash"))
    if st.session_state.get(f"ibovespa_{series.ticker}"):
        universo = scmp.tickers_ibovespa(dados.universo(), p.plano.tipo == "financeira")
        with st.spinner("Lendo as séries das empresas do Ibovespa..."):
            painel = dados.painel(universo, cadastro, base)
        grupos.append((ROTULO_IBOV, painel, grafico.VERDE, "dot"))
    return grupos


def mostrar(
    ticker: str,
    p: emp.Padronizada,
    cadastro: pd.DataFrame,
    base: dt.date,
) -> None:
    series = dados.series(p, ticker, base)
    if series is None:
        st.info(f"{TRACO} sem cotação de {ticker} em disco. Clique em **Atualizar** para baixá-la.")
        _balanco(p, ticker, base, _indicadores(p, ticker, base))
        return
    _cartoes(series, base)
    if series.avisos:
        with st.expander(f"Avisos da série ({len(series.avisos)})"):
            for aviso in series.avisos:
                st.warning(aviso)
    _grafico_cotacao(series, base)
    _grafico_multiplos(series, base, _grupos(series, p, cadastro, base), cadastro)
    _balanco(p, ticker, base, _indicadores(p, ticker, base))
    _comparacao(series, p, cadastro, base)
