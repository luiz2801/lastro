"""Aba Dividendos: DPA por ano, total de 12 meses e proventos por data ex (só lê o disco).

Fonte: yfinance (`series TICKER` baixa). O Yahoo não separa dividendo de JCP nem informa a data de
pagamento. O yield usa o `Adj Close`, como o comando `proventos`.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from valuation import config as cfg
from valuation.analise import proventos as prv
from valuation.gui import acoes, cartoes, dados, grafico
from valuation.saida import formato as fo
from valuation.servicos import atualizacao as atu
from valuation.servicos import comparacao as scmp
from valuation.servicos import empresa as emp
from valuation.servicos import historico_mercado as hm
from valuation.servicos import proventos as sprv

TRACO = "—"
ANOS = 10


def _contra_pares(ticker: str, p: emp.Padronizada, base: dt.date) -> None:
    st.subheader("Dividend yield por ano: ativo e pares do setor")
    setor = dados.setor(p.premissas.pares.setor)
    pares = scmp.tickers_pares(p.premissas, p.empresa.tickers, setor)
    if not pares:
        st.info(f"{TRACO} {ticker} sem pares definidos (`pares.setor` no YAML da empresa).")
        return
    ativo, _ = sprv.yield_por_ano(ticker, base, ANOS, dir_raw=cfg.DIR_RAW)
    grupo = sprv.yield_do_grupo(pares, base, ANOS, dir_raw=cfg.DIR_RAW)
    if ativo is not None and grupo.por_empresa:
        st.plotly_chart(grafico.yield_contra_pares(ativo, grupo.serie, ticker), width="stretch")
        st.caption(
            f"Mediana de {len(grupo.por_empresa)} de {len(pares)} pares com proventos em disco "
            f"(n por ano ao passar o mouse). O ano de {base.year} é parcial para todos. Mesmo "
            "método do ativo: DPA do Yahoo ÷ Adj Close."
        )
    else:
        st.info(f"{TRACO} sem proventos dos pares em disco para a comparação.")
    if grupo.faltam:
        with st.expander(f"Pares sem proventos em disco ({len(grupo.faltam)})"):
            for par, razao in grupo.faltam.items():
                st.write(f"{par}: {razao}")
        if st.button("Baixar proventos dos pares", key=f"baixar_proventos_{ticker}"):
            execucao = acoes.executar(
                "Baixando proventos dos pares", atu.baixar_proventos(list(grupo.faltam), ANOS)
            )
            if execucao.ok:
                st.rerun()
            acoes.mostrar_falha(execucao)


def _payout(ticker: str, p: emp.Padronizada, cadastro: pd.DataFrame, base: dt.date) -> None:
    st.subheader("Payout por exercício")
    historico = sprv.payout_por_ano(p, dados.settings(), base, ANOS)
    if historico["payout"].notna().any():
        setor = dados.setor(p.premissas.pares.setor)
        pares = scmp.tickers_pares(p.premissas, p.empresa.tickers, setor)
        grupo = dados.payout_grupo(pares, cadastro, base, ANOS) if pares else None
        com_pares = grupo is not None and bool(grupo.por_empresa)
        st.plotly_chart(
            grafico.payout_por_ano(
                historico["payout"], grupo.serie if grupo and com_pares else None, ticker
            ),
            width="stretch",
        )
        st.caption(
            "Payout = dividendos e JCP pagos (DFC) ÷ lucro da controladora; exercícios encerrados "
            "até a data-base. Lucro não positivo fica em lacuna; em não financeiras, exercício "
            "sem a linha de dividendos na DFC conta como zero."
        )
        if com_pares and grupo is not None:
            st.caption(
                f"Mediana de {len(grupo.por_empresa)} de {len(pares)} pares com demonstrações "
                "em disco (n por ano ao passar o mouse)."
            )
        _pares_sem_demonstracoes(grupo, cadastro)
    else:
        st.info(f"{TRACO} {ticker} sem payout calculável (sem dividendo ou lucro não positivo).")
    tabela = pd.DataFrame(
        {
            "Exercício": [str(a) for a in historico.index],
            "Dividendos pagos (R$ mi)": [
                fo.formatar(v, "mi", 1) for v in historico["dividendos_pagos"]
            ],
            "Lucro da controladora (R$ mi)": [
                fo.formatar(v, "mi", 1) for v in historico["lucro_controladora"]
            ],
            "Payout": [fo.formatar(v, "%", 1) for v in historico["payout"]],
        }
    ).iloc[::-1]
    st.dataframe(tabela, hide_index=True, width="stretch")


def _pares_sem_demonstracoes(grupo: sprv.PayoutDoGrupo | None, cadastro: pd.DataFrame) -> None:
    if grupo is None or not grupo.faltam:
        return
    with st.expander(f"Pares sem payout ({len(grupo.faltam)})"):
        for par, razao in grupo.faltam.items():
            st.write(f"{par}: {razao}")
    sem_dados = [t for t in grupo.faltam if not dados.ticker_tem_demonstracoes(t, cadastro)]
    if sem_dados and st.button("Baixar demonstrações dos pares", key="baixar_demonstracoes_pares"):
        execucao = acoes.executar(
            "Baixando demonstrações dos pares", atu.baixar_demonstracoes(sem_dados)
        )
        if execucao.ok:
            st.rerun()
        acoes.mostrar_falha(execucao)


def mostrar(
    ticker: str,
    series: hm.SeriesMercado | None,
    base: dt.date,
    p: emp.Padronizada,
    cadastro: pd.DataFrame,
) -> None:
    dividendos = hm.dividendos_em_disco(ticker, dir_raw=cfg.DIR_RAW)
    if series is None or dividendos is None:
        st.info(
            f"{TRACO} sem proventos de {ticker} em disco. Clique em **Atualizar** para baixá-los."
        )
        return
    historico = series.cotacao
    dpa12, yield12 = prv.dpa_12m(dividendos, historico, base)
    st.markdown(
        cartoes.secao(
            "Últimos 12 meses",
            [
                cartoes.cartao("Dividendo por ação", fo.brl(dpa12)),
                cartoes.cartao("Dividend yield", fo.formatar(yield12, "%", 2)),
            ],
            f"Datas ex de {base - dt.timedelta(days=365):%d/%m/%Y} a {base:%d/%m/%Y}. Yield sobre "
            "o Adj Close (ajustado por dividendos).",
        ),
        unsafe_allow_html=True,
    )
    por_ano = prv.dpa_anual(dividendos, historico, base, ANOS)
    st.subheader("Dividendo por ação por ano")
    st.plotly_chart(grafico.dpa_anual(por_ano), width="stretch")
    st.caption(f"Ano de {base.year} parcial (em cinza), até {base:%d/%m/%Y}.")
    tabela = pd.DataFrame(
        {
            "Ano": [f"{a} (parcial)" if p else str(a) for a, p in por_ano["parcial"].items()],
            "DPA": [fo.brl(v) for v in por_ano["dpa"]],
            "Proventos": por_ano["n_proventos"].astype(int).to_numpy(),
            "Adj Close": [fo.brl(v) for v in por_ano["preco"]],
            "Dividend yield": [fo.formatar(v, "%", 2) for v in por_ano["dividend_yield"]],
        }
    ).iloc[::-1]
    st.dataframe(tabela, hide_index=True, width="stretch")

    _contra_pares(ticker, p, base)
    _payout(ticker, p, cadastro, base)

    st.subheader("Proventos por data ex")
    ate_base = dividendos[dividendos.index <= pd.Timestamp(base)]
    detalhe = pd.DataFrame(
        {
            "Data ex": [pd.Timestamp(str(d)).strftime("%d/%m/%Y") for d in ate_base.index[::-1]],
            "Valor por ação": [fo.brl(float(v)) for v in ate_base.to_numpy()[::-1]],
        }
    )
    st.dataframe(detalhe, hide_index=True, width="stretch")
    st.caption(
        "Fonte: yfinance. Sem tipo (dividendo ou JCP) nem data de pagamento: o Yahoo não traz. "
        "O Adj Close deixa o yield dos anos antigos acima do yield sobre o preço da época."
    )
