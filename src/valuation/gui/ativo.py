"""Página de um ativo: estados vazios e de erro, cabeçalho, barra de estado e abas."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from valuation.contabil import ErroContabil
from valuation.data import cadastro as cad
from valuation.gui import aba_valuation, acoes, dados, estado, geral
from valuation.servicos import atualizacao as atu
from valuation.universo import EmpresaUniverso

TIPOS_SUPORTADOS = ("nao_financeira", "financeira")


def _do_universo(ticker: str) -> EmpresaUniverso | None:
    return next((e for e in dados.universo() if e.ticker == ticker), None)


def _voltar() -> None:
    if st.button("← Início"):
        st.query_params.clear()
        st.rerun()


def _baixar_sem_cache(ticker: str) -> bool:
    """Rede automática só para ativo sem nenhum cache; uma tentativa por sessão, salvo clique."""
    chave = f"falha_download_{ticker}"
    falha = st.session_state.get(chave)
    if falha is not None:
        acoes.mostrar_falha(falha)
        if not st.button("Tentar de novo"):
            return False
        del st.session_state[chave]
    st.info(f"{ticker} não tem dados em disco: baixando da CVM.")
    execucao = acoes.executar(f"Baixando {ticker}", atu.baixar_dados(ticker))
    if execucao.ok:
        return True
    st.session_state[chave] = execucao
    acoes.mostrar_falha(execucao)
    return False


def _cadastro_com_dados(ticker: str) -> tuple[pd.DataFrame, cad.Empresa] | None:
    """Cadastro e empresa com demonstrações em disco, baixando se não houver nenhum cache."""
    cadastro = dados.cadastro()
    empresa = None
    if cadastro is not None:
        empresa = cad.empresa_por_ticker(cadastro, ticker)
        if dados.tem_demonstracoes(empresa.cd_cvm):
            return cadastro, empresa
    if not _baixar_sem_cache(ticker):
        return None
    cadastro = dados.cadastro()
    if cadastro is None:
        st.error("O download terminou, mas o cadastro não foi gravado em data/processed/.")
        return None
    empresa = cad.empresa_por_ticker(cadastro, ticker)
    if not dados.tem_demonstracoes(empresa.cd_cvm):
        st.error(f"{ticker}: a CVM não trouxe demonstrações para esta companhia.")
        return None
    return cadastro, empresa


def _cabecalho(ticker: str, empresa: cad.Empresa, membro: EmpresaUniverso) -> None:
    especie = next((c.especie for c in empresa.classes if c.ticker == ticker), "—")
    st.title(f"{ticker} — {empresa.nome_comercial or empresa.razao_social}")
    st.caption(f"Classe {especie} · {membro.setor.value}")


def mostrar(ticker: str) -> None:
    _voltar()
    membro = _do_universo(ticker)
    if membro is None:
        st.error(
            f"{ticker} está fora do universo (`config/universo_ibovespa.csv`): — sem indicadores."
        )
        return
    if membro.tipo_modelo not in TIPOS_SUPORTADOS:
        st.warning(
            f"{ticker} é {membro.tipo_modelo}: fora da v1 (holdings exigem NAV/SOTP): "
            "— sem indicadores nem valuation."
        )
        return
    try:
        par = _cadastro_com_dados(ticker)
    except cad.ErroCadastro as e:
        st.error(str(e))
        return
    if par is None:
        return
    cadastro, empresa = par

    agora = dt.datetime.now(dt.UTC)
    base = dados.settings().resolver_data_base(agora.date())
    _cabecalho(ticker, empresa, membro)
    avisos: list[str] = []
    padronizada_ok = None
    try:
        padronizada_ok = dados.padronizada(ticker, cadastro, empresa.cd_cvm)
        avisos += padronizada_ok.avisos
    except ErroContabil as e:
        st.error(f"Sem dados contábeis utilizáveis: {e}")
    estado.mostrar(base, dados.estado_fontes(ticker, empresa.cd_cvm), agora, avisos)

    if st.button("Atualizar", key="atualizar_ativo"):
        execucao = acoes.executar(f"Atualizando {ticker}", atu.atualizar_ativo(ticker))
        if execucao.ok:
            st.rerun()
        acoes.mostrar_falha(execucao)

    aba_ger, aba_val = st.tabs(["Geral", "Valuation"])
    with aba_ger:
        if padronizada_ok is None:
            st.info("— sem dados contábeis para os indicadores.")
        else:
            geral.mostrar(ticker, padronizada_ok, cadastro, base)
    with aba_val:
        aba_valuation.mostrar(ticker, agora.date(), base, padronizada_ok)
