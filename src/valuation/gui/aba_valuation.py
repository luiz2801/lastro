"""Aba Valuation: só lê a última rodada de `saida/`, sem recalcular nada (GUI-40 a 43)."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from valuation.gui import acoes, dados, grafico, navegacao
from valuation.perfil import NomePerfil
from valuation.perfil.parametros import parametros_do_perfil
from valuation.saida import formato as fo
from valuation.servicos import atualizacao as atu
from valuation.servicos import empresa as emp
from valuation.servicos import historico_mercado as hm
from valuation.servicos import resultados as res

ITENS_PONTE = (
    "valor_da_firma",
    "divida_bruta",
    "caixa_e_aplicacoes",
    "minoritarios",
    "investimentos_coligadas",
    "divida_extra",
    "equity",
)
ROTULOS_CHECAGEM = {True: "✅ ok", False: "⚠️ atenção", None: "—"}
TAXAS_WACC = ("rf", "erp", "ke", "kd", "kd_liquido", "peso_divida", "peso_equity", "wacc")


def _sem_rodada(ticker: str) -> None:
    st.info(f"— {ticker} ainda não tem valuation em `saida/`.")
    if st.button("Rodar valuation", key="rodar_valuation"):
        execucao = acoes.executar(f"Rodando {ticker}", atu.rodar_valuation(ticker))
        if execucao.ok:
            st.rerun()
        acoes.mostrar_falha(execucao)


def _rodar_com_perfil(ticker: str, perfil: NomePerfil) -> None:
    """O ponderado não é refeito na tela: o perfil muda o horizonte, e este, o de cada cenário."""
    st.warning(
        f"Para ver o valor com o perfil {perfil}, é preciso rodar de novo. Isso sobrescreve a "
        "pasta de hoje em `saida/`; o questionário gravado não muda."
    )
    if st.button(f"Rodar com perfil {perfil}", key="rodar_com_perfil"):
        execucao = acoes.executar(
            f"Rodando {ticker} com perfil {perfil}", atu.rodar_valuation(ticker, perfil)
        )
        if execucao.ok:
            st.rerun()
        acoes.mostrar_falha(execucao)


def _perfil(hoje: dt.date, r: res.Resultado, ticker: str) -> None:
    override = navegacao.override()
    efetivo, motivo = dados.perfil_efetivo(hoje, override)
    rodada = str(r.resumo.get("perfil", "—"))
    if efetivo is None:
        st.warning(f"Perfil do investidor indisponível: {motivo} A rodada usou o perfil {rodada}.")
        return
    validade = f" (válido até {efetivo.registro.valido_ate:%d/%m/%Y})" if efetivo.registro else ""
    if override is not None:
        validade = " (escolhido nesta sessão)"
    p = parametros_do_perfil(efetivo.perfil, dados.settings().perfil)
    st.caption(
        f"Perfil {efetivo.perfil}{validade}: margem de segurança {p.margem_seguranca:.0%}, pesos "
        f"{p.peso_pessimista:.0%} / {p.peso_base:.0%} / {p.peso_otimista:.0%}."
    )
    if rodada == efetivo.perfil:
        return
    if override is not None:
        st.info(f"Os valores abaixo são da rodada com o perfil {rodada}.")
        _rodar_com_perfil(ticker, override)
        return
    st.warning(f"A rodada usou o perfil {rodada}, e o atual é {efetivo.perfil}: rode de novo.")


def _cenarios(r: res.Resultado) -> None:
    resumo = r.resumo
    colunas = st.columns(4)
    for coluna, nome, chave in zip(
        colunas,
        ("Pessimista", "Base", "Otimista", "Valor ponderado"),
        ("valor_pessimista", "valor_base", "valor_otimista", "valor_ponderado"),
        strict=True,
    ):
        coluna.metric(nome, fo.reais(res.numero(resumo, chave)))
    colunas = st.columns(4)
    colunas[0].metric("Preço da rodada", fo.reais(res.numero(resumo, "preco")))
    colunas[1].metric("Preço máximo de compra", fo.reais(res.numero(resumo, "preco_maximo_compra")))
    colunas[2].metric("Upside", fo.taxa(res.numero(resumo, "upside")))
    colunas[3].metric(
        "Retorno esperado x hurdle",
        f"{fo.taxa(res.numero(resumo, 'ke_implicito'))} x {fo.taxa(res.numero(resumo, 'hurdle'))}",
        help="Ke implícito no preço contra o retorno mínimo exigido pelo perfil (Selic + spread).",
    )
    _decisao(r)


def _texto(resumo: pd.Series, coluna: str) -> str:
    valor = resumo.get(coluna)
    return "" if valor is None or pd.isna(valor) else str(valor)


def _decisao(r: res.Resultado) -> None:
    """Recomendação, confiança e preço teto de Bazin (ADR 0025); rodada antiga mostra "—"."""
    resumo = r.resumo
    sinal = _texto(resumo, "recomendacao")
    modelo = _texto(resumo, "recomendacao_modelo")
    motivos = [m for m in _texto(resumo, "motivos_confianca").split(" | ") if m]
    criterio = (
        fo.criterio_recomendacao(
            modelo,
            preco=res.numero(resumo, "preco"),
            valor_ponderado=res.numero(resumo, "valor_ponderado"),
            preco_maximo=res.numero(resumo, "preco_maximo_compra"),
            ke_implicito=res.numero(resumo, "ke_implicito"),
            hurdle=res.numero(resumo, "hurdle"),
        )
        if modelo
        else "rodada anterior à recomendação: rode de novo."
    )
    rebaixada = sinal == "manter" and modelo == "compra"
    colunas = st.columns(4)
    colunas[0].metric(
        "Recomendação",
        fo.sinal(sinal),
        help=f"Critério: {criterio}."
        + (" Compra rebaixada para manter pela confiança baixa." if rebaixada else ""),
    )
    confianca = _texto(resumo, "confianca")
    colunas[1].metric(
        "Confiança",
        confianca.capitalize() if confianca else "—",
        help="; ".join(motivos)
        if motivos
        else "Sem erro de QA, VT/valor no limite, pares e R² do beta suficientes.",
    )
    yield_minimo = res.numero(resumo, "yield_minimo_bazin")
    colunas[2].metric(
        "Preço teto Bazin",
        fo.reais(res.numero(resumo, "preco_teto_bazin")),
        help="Dividendo médio por ação dos últimos exercícios (DFC) / yield mínimo de "
        f"{fo.formatar(yield_minimo, '%', 2)}. Informativo: a recomendação usa o preço máximo "
        "de compra do perfil.",
    )
    colunas[3].metric(
        "Dividendo médio por ação",
        fo.reais(res.numero(resumo, "dividendo_por_acao_bazin")),
    )
    if rebaixada:
        st.caption(f"Compra rebaixada para manter: {'; '.join(motivos)}.")


def _custo_capital(r: res.Resultado) -> None:
    st.subheader("Custo de capital" if r.modelo == "dcf" else "Custo do capital próprio")
    if r.wacc is None:
        st.info("— `wacc.csv` não está nesta rodada.")
        return
    tabela = r.wacc
    componentes = tabela[tabela["componente"] != "aviso"]
    linhas = []
    for _, linha in componentes.iterrows():
        valor = pd.to_numeric(linha["valor"], errors="coerce")
        nome = str(linha["componente"])
        detalhe = "" if pd.isna(linha["detalhe"]) else str(linha["detalhe"])
        texto = detalhe if pd.isna(valor) else fo.componente_wacc(nome, float(valor))
        linhas.append(
            {"Componente": nome, "Valor": texto, "Detalhe": "" if pd.isna(valor) else detalhe}
        )
    # `st.table`, não `st.dataframe`: o texto quebra a linha, e nenhuma linha fica atrás de rolagem.
    st.table(pd.DataFrame(linhas).set_index("Componente"))
    for aviso in tabela.loc[tabela["componente"] == "aviso", "detalhe"].dropna():
        st.warning(str(aviso))


def _checagens(r: res.Resultado) -> None:
    st.subheader("Checagens")
    linhas = [
        {"Checagem": c.nome, "Valor": c.valor, "Resultado": ROTULOS_CHECAGEM[c.ok]}
        for c in res.checagens(r, dados.settings())
    ]
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")


def _ponte(r: res.Resultado) -> None:
    if r.ponte is None:
        return
    st.subheader("Ponte EV → equity")
    cenarios = [c for c in r.ponte.columns if c != "item"]
    cenario = st.radio(
        "Cenário",
        cenarios,
        index=cenarios.index("base") if "base" in cenarios else 0,
        horizontal=True,
        key="cenario_ponte",
    )
    itens = res.ponte_de_cenario(r, cenario)
    if itens is None:
        st.info("— ponte indisponível para este cenário.")
        return
    st.plotly_chart(
        grafico.ponte(itens.reindex([i for i in ITENS_PONTE if i in itens.index])),
        key="grafico_ponte",
    )


def _football(
    ticker: str, r: res.Resultado, base: dt.date, padronizada: emp.Padronizada | None
) -> None:
    st.subheader("Football field")
    series = None if padronizada is None else dados.series(padronizada, ticker, base)
    cartoes = None if series is None else hm.cartoes(series, base)
    faixas = res.faixas_football(r, cartoes.faixa_52_semanas if cartoes else None)
    if not faixas:
        st.info("— sem faixas de valor nesta rodada.")
        return
    preco = res.numero(r.resumo, "preco")
    maximo = res.numero(r.resumo, "preco_maximo_compra")
    bazin = res.numero(r.resumo, "preco_teto_bazin")
    st.plotly_chart(grafico.football(faixas, preco, maximo, bazin), key="grafico_football")
    if any(f.aviso for f in faixas):
        st.caption("* Múltiplo de baixa confiança: menos pares válidos do que o mínimo.")


def mostrar(ticker: str, hoje: dt.date, base: dt.date, padronizada: emp.Padronizada | None) -> None:
    r = dados.resultado(ticker)
    if r is None:
        _sem_rodada(ticker)
        return
    idade = (hoje - r.data_base).days
    st.caption(
        f"Rodada de {r.data_base:%d/%m/%Y} (há {idade} d), com o preço daquele dia. "
        f"Modelo: {r.modelo.upper()}."
    )
    _perfil(hoje, r, ticker)
    _cenarios(r)
    for aviso in [*r.avisos_rodada, *r.avisos]:
        st.warning(aviso)
    _custo_capital(r)
    _checagens(r)
    _football(ticker, r, base, padronizada)
    _ponte(r)
    if st.button("Rodar valuation de novo", key="rodar_valuation"):
        execucao = acoes.executar(f"Rodando {ticker}", atu.rodar_valuation(ticker))
        if execucao.ok:
            st.rerun()
        acoes.mostrar_falha(execucao)
