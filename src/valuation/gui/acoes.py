"""Execução visível de um fluxo da CLI: progresso, erro na tela e cache invalidado ao fim."""

from __future__ import annotations

from collections.abc import Sequence

import streamlit as st

from valuation.gui import dados
from valuation.servicos import atualizacao as atu


def executar(rotulo: str, comandos: Sequence[atu.Comando]) -> atu.Execucao:
    """Roda `comandos` num `st.status` só com um aviso de que está carregando (sem o log ao vivo).

    A falha fica na tela, com as últimas linhas da saída, sem derrubar a página.
    """
    with st.status(rotulo, expanded=True) as painel:
        st.write("Carregando… isso pode levar alguns minutos.")
        execucao = atu.executar(comandos)
        if execucao.ok:
            painel.update(label=f"{rotulo}: concluído", state="complete", expanded=False)
        else:
            painel.update(label=f"{rotulo}: falhou", state="error", expanded=True)
    dados.invalidar()
    return execucao


def mostrar_falha(execucao: atu.Execucao) -> None:
    st.error(f"Falhou em `{execucao.falhou_em}`.")
    if execucao.saida:
        st.code("\n".join(execucao.saida[-25:]), language=None)
