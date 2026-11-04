"""Perfil do investidor na tela: validade, parâmetros e questionário (GUI-70).

A pontuação, os vetos e a validade são os de `perfil/`; aqui só se coletam as respostas.
"""

from __future__ import annotations

import datetime as dt

import streamlit as st

from valuation import config as cfg
from valuation.gui import dados
from valuation.perfil import ErroPerfil, NomePerfil
from valuation.perfil import registro as reg
from valuation.perfil.parametros import parametros_do_perfil
from valuation.perfil.questionario import QUESTIONARIO
from valuation.saida import formato as fo

CHAVE_REFAZER = "refazer_perfil"


def _parametros(perfil: NomePerfil) -> None:
    p = parametros_do_perfil(perfil, dados.settings().perfil)
    colunas = st.columns(4)
    colunas[0].metric("Margem de segurança", fo.formatar(p.margem_seguranca, "%", 2))
    colunas[1].metric(
        "Pesos (pess. / base / ot.)",
        " / ".join(
            fo.formatar(x, "%", 2) for x in (p.peso_pessimista, p.peso_base, p.peso_otimista)
        ),
    )
    colunas[2].metric("Horizonte", f"{p.horizonte_anos} anos")
    colunas[3].metric("Retorno mínimo", f"Selic + {fo.formatar(p.hurdle_spread_selic, '%', 2)}")
    st.caption(
        "Parâmetros do `settings.yaml`. O perfil não muda fatos contábeis nem o custo de capital."
    )


def _gravado(hoje: dt.date) -> reg.RegistroPerfil | None:
    try:
        atual = reg.ler(cfg.CAMINHO_PERFIL)
    except FileNotFoundError:
        st.info("Nenhum perfil gravado: responda ao questionário abaixo.")
        return None
    except ErroPerfil as e:
        st.warning(f"O perfil gravado não vale: {e}")
        return None
    if atual.vencido(hoje):
        st.warning(f"O perfil venceu em {atual.valido_ate:%d/%m/%Y}: responda de novo.")
        return None
    st.subheader(f"Perfil {atual.perfil}")
    vetos = (
        f" Vetos aplicados: {', '.join(atual.vetos_aplicados)}." if atual.vetos_aplicados else ""
    )
    st.caption(
        f"Respondido em {atual.data:%d/%m/%Y}, válido até {atual.valido_ate:%d/%m/%Y}. "
        f"Pontuação {atual.pontuacao} de 50.{vetos}"
    )
    _parametros(atual.perfil)
    return atual


def _questionario(hoje: dt.date) -> None:
    with st.form("questionario_perfil"):
        escolhas: dict[str, int | None] = {}
        for i, pergunta in enumerate(QUESTIONARIO, start=1):
            textos = [a.texto for a in pergunta.alternativas]
            escolhida = st.radio(
                f"{i}. {pergunta.enunciado}", textos, index=None, key=f"resposta_{pergunta.chave}"
            )
            escolhas[pergunta.chave] = None if escolhida is None else textos.index(escolhida) + 1
        enviado = st.form_submit_button("Gravar perfil")
    if not enviado:
        return
    faltam = [p.chave for p in QUESTIONARIO if escolhas[p.chave] is None]
    if faltam:
        numeros = ", ".join(str(int(c.removeprefix("q"))) for c in faltam)
        st.error(f"Responda a todas as perguntas. Faltam: {numeros}. Nada foi gravado.")
        return
    respostas = {c: v for c, v in escolhas.items() if v is not None}
    reg.gravar(reg.criar_registro(respostas, hoje), cfg.CAMINHO_PERFIL)
    st.session_state[CHAVE_REFAZER] = False
    st.rerun()


def mostrar(hoje: dt.date) -> None:
    st.title("Perfil do investidor")
    atual = _gravado(hoje)
    if atual is None or st.session_state.get(CHAVE_REFAZER):
        _questionario(hoje)
    elif st.button("Refazer o questionário"):
        st.session_state[CHAVE_REFAZER] = True
        st.rerun()
    st.caption(
        "O perfil só ajusta desconto, pesos, horizonte e retorno mínimo. Não é recomendação."
    )
