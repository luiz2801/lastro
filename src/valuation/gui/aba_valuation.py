"""Aba Valuation: só lê a última rodada de `saida/`, sem recalcular nada (GUI-40 a 43).

Três visuais sobre os mesmos números (ADR 0026): cartões por seção (o principal), faixa de preço e
gráficos. O alternador "Comparar com setor e mercado" põe, em cada cartão, a referência dos pares,
do setor CVM e do Ibovespa, lida das rodadas que já estão em `saida/` e dos múltiplos em disco.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from html import escape
from typing import cast

import pandas as pd
import streamlit as st

from valuation.analise import anomalias as an
from valuation.gui import acoes, cartoes, dados, grafico, navegacao
from valuation.modelos import multiplos as mt
from valuation.perfil import NomePerfil
from valuation.perfil.parametros import parametros_do_perfil
from valuation.saida import formato as fo
from valuation.servicos import atualizacao as atu
from valuation.servicos import comparacao as scmp
from valuation.servicos import comparacao_valuation as scv
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
VISUAIS = ("Cartões", "Faixa de preço", "Gráficos")
MULTIPLOS_CARTOES: tuple[mt.NomeMultiplo, ...] = (
    "p_l",
    "ev_ebitda",
    "ev_ebit",
    "p_vp",
    "dividend_yield",
)
TOM_RECOMENDACAO = {"compra": "ok", "manter": "warn", "venda": "bad"}
TOM_CONFIANCA = {"baixa": "bad", "media": "warn", "média": "warn"}
AJUDAS = {
    "pessimista": "Valor por ação no cenário pessimista.",
    "base": "Valor por ação no cenário base.",
    "otimista": "Valor por ação no cenário otimista.",
    "ponderado": "Soma dos cenários pelos pesos do perfil.",
    "maximo": "Valor ponderado menos a margem de segurança do perfil.",
    "retorno": "Ke implícito no preço contra o mínimo exigido pelo perfil (Selic + spread).",
    "beta": "Sensibilidade da ação ao Ibovespa (regressão semanal, com ajuste de Blume se ligado).",
    "ke": "Custo do capital próprio: taxa livre de risco + beta x prêmio de risco.",
    "kd": "Custo da dívida antes do imposto.",
    "wacc": "Custo médio ponderado de capital: Ke e Kd líquido pelos pesos de equity e dívida.",
    "g": "Crescimento nominal perpétuo do valor terminal.",
}


@dataclass(frozen=True)
class Comparacao:
    """O que a tela precisa para pôr a referência dos grupos em cada cartão."""

    grupos: dict[str, list[str]]
    rodadas: dict[str, scv.RodadaLida | None]
    medidas: dict[str, list[scmp.Medida]]
    perfil: str
    modelo: str
    tipo: an.Referencia

    def referencia(self, grupo: str, chave: str) -> scv.ReferenciaValuation:
        rodadas = {t: self.rodadas.get(t) for t in self.grupos[grupo]}
        return scv.referencia_valuation(
            rodadas, scv.POR_CHAVE[chave], self.perfil, self.modelo, self.tipo
        )


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


def _texto(resumo: pd.Series, coluna: str) -> str:
    valor = resumo.get(coluna)
    return "" if valor is None or pd.isna(valor) else str(valor)


# ---------------------------------------------------------------------------------------------
# Comparação com pares, setor CVM e Ibovespa
# ---------------------------------------------------------------------------------------------


def _formatar(i: scv.Indicador, valor: float) -> str:
    if pd.isna(valor):
        return cartoes.TRACO
    return fo.taxa(valor) if i.unidade == "%" else fo.componente_wacc(i.coluna, valor)


def _rotulo_grupo(grupo: str, n: int) -> str:
    return f"{scv.ROTULOS_GRUPO[grupo]} (n = {n})"


def _subs_valuation(c: Comparacao | None, chave: str) -> list[tuple[str, str]]:
    if c is None:
        return []
    indicador = scv.POR_CHAVE[chave]
    linhas = []
    for grupo in c.grupos:
        ref = c.referencia(grupo, chave)
        linhas.append(cartoes.sub(_rotulo_grupo(grupo, ref.n), _formatar(indicador, ref.valor)))
    return linhas


def _subs_multiplo(c: Comparacao | None, nome: mt.NomeMultiplo) -> list[tuple[str, str]]:
    if c is None:
        return []
    linhas = []
    for grupo in c.grupos:
        medidas = c.medidas.get(grupo, [])
        ref = scmp.referencia_do_grupo(medidas, nome, c.tipo, dados.settings())
        linhas.append(cartoes.sub(_rotulo_grupo(grupo, ref.n), fo.multiplo(nome, ref.valor, 2)))
    return linhas


def _montar_comparacao(
    ticker: str, r: res.Resultado, base: dt.date, padronizada: emp.Padronizada | None
) -> Comparacao | None:
    """Grupos, rodadas em disco e múltiplos de hoje; `None` sem o que identifica o ativo."""
    if padronizada is None:
        return None
    grupos = scv.grupos_de_comparacao(
        ticker,
        padronizada.empresa.tickers,
        padronizada.premissas,
        dados.setor(padronizada.premissas.pares.setor),
        dados.universo(),
    )
    todos = list(dict.fromkeys(t for lista in grupos.values() for t in lista))
    cadastro = dados.cadastro()
    medidas: dict[str, list[scmp.Medida]] = {}
    if cadastro is not None:
        with st.spinner("Lendo as empresas em disco..."):
            medidas = {g: dados.medidas(ts, cadastro, base) for g, ts in grupos.items() if ts}
    tipo = cast(an.Referencia, st.session_state.get("referencia_serie", "mediana"))
    return Comparacao(
        grupos=grupos,
        rodadas=dados.rodadas(todos),
        medidas=medidas,
        perfil=_texto(r.resumo, "perfil"),
        modelo=r.modelo,
        tipo=tipo,
    )


def _situacao_dos_grupos(c: Comparacao, ticker: str, setor_nome: str | None) -> None:
    """Quantas empresas de cada grupo têm rodada e o que dá para rodar a partir daqui."""
    partes = []
    for grupo, tickers in c.grupos.items():
        com = sum(c.rodadas.get(t) is not None for t in tickers)
        partes.append(f"{scv.ROTULOS_GRUPO[grupo]}: {com} de {len(tickers)} com rodada")
    st.caption(
        f"{an.ROTULOS_REFERENCIA[c.tipo]} das empresas já em disco. " + " · ".join(partes) + ". "
        "Upside, retorno esperado e VT só contam as rodadas com o mesmo perfil do ativo."
    )
    perfil = c.perfil or None
    faltam_pares = [t for t in c.grupos[scv.GRUPO_PARES] if c.rodadas.get(t) is None]
    faltam_setor = [t for t in c.grupos[scv.GRUPO_SETOR] if c.rodadas.get(t) is None]
    if not (faltam_pares or faltam_setor):
        return
    with st.expander("Rodar o valuation de quem falta"):
        st.caption(
            "Roda `rodar` (ou `rodar-setor`) com o perfil da rodada do ativo e sobrescreve a "
            "pasta de hoje de cada empresa. Pode baixar dados e leva alguns minutos."
        )
        cadastro = dados.cadastro()
        if faltam_pares and st.button(
            f"Rodar os {len(faltam_pares)} pares sem rodada", key="rodar_pares"
        ):
            sem_dem = [
                t
                for t in faltam_pares
                if cadastro is None or not dados.ticker_tem_demonstracoes(t, cadastro)
            ]
            execucao = acoes.executar(
                f"Rodando os pares de {ticker}", atu.rodar_varios(faltam_pares, sem_dem, perfil)
            )
            if execucao.ok:
                st.rerun()
            acoes.mostrar_falha(execucao)
        if (
            faltam_setor
            and setor_nome
            and st.button(f"Rodar o setor CVM ({len(faltam_setor)} sem rodada)", key="rodar_setor")
        ):
            execucao = acoes.executar(
                f"Rodando o setor {setor_nome}", atu.rodar_setor(setor_nome, perfil)
            )
            if execucao.ok:
                st.rerun()
            acoes.mostrar_falha(execucao)
        st.caption(
            "O Ibovespa só usa as rodadas que já existem; para ampliar, rode os outros setores "
            "(`valuation setores` lista os nomes)."
        )


# ---------------------------------------------------------------------------------------------
# Cartões
# ---------------------------------------------------------------------------------------------


def _vs_preco(valor: float, preco: float) -> tuple[str, str]:
    diferenca = valor / preco - 1 if pd.notna(valor) and pd.notna(preco) and preco else float("nan")
    return "vs. preço", cartoes.texto_com_sinal(diferenca)


def _cartoes_valor(r: res.Resultado) -> list[str]:
    resumo = r.resumo
    preco = res.numero(resumo, "preco")
    itens = (
        ("Pessimista", "valor_pessimista", "pessimista", False),
        ("Base", "valor_base", "base", False),
        ("Otimista", "valor_otimista", "otimista", False),
        ("Valor ponderado", "valor_ponderado", "ponderado", True),
    )
    saida = [
        cartoes.cartao(
            rotulo,
            fo.reais(res.numero(resumo, coluna)),
            ajuda=AJUDAS[ajuda],
            subs=[_vs_preco(res.numero(resumo, coluna), preco)],
            destaque=destaque,
        )
        for rotulo, coluna, ajuda, destaque in itens
    ]
    saida.append(cartoes.cartao("Preço da rodada", fo.reais(preco)))
    maximo = res.numero(resumo, "preco_maximo_compra")
    saida.append(
        cartoes.cartao(
            "Preço máximo de compra",
            fo.reais(maximo),
            ajuda=AJUDAS["maximo"],
            subs=[_vs_preco(maximo, preco)],
        )
    )
    return saida


def _cartoes_decisao(r: res.Resultado, c: Comparacao | None) -> list[str]:
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
    ajuda_sinal = f"Critério: {criterio}." + (
        " Compra rebaixada para manter pela confiança baixa." if rebaixada else ""
    )
    confianca = _texto(resumo, "confianca")
    yield_minimo = res.numero(resumo, "yield_minimo_bazin")
    ke_implicito = res.numero(resumo, "ke_implicito")
    hurdle = res.numero(resumo, "hurdle")
    diferenca = ke_implicito - hurdle
    return [
        cartoes.cartao(
            "Recomendação",
            cartoes.selo(fo.sinal(sinal), TOM_RECOMENDACAO.get(sinal, "warn"))
            if sinal
            else cartoes.TRACO,
            bruto=True,
            ajuda=ajuda_sinal,
        ),
        cartoes.cartao(
            "Confiança",
            cartoes.selo(confianca.capitalize(), TOM_CONFIANCA.get(confianca, "ok"))
            if confianca
            else cartoes.TRACO,
            bruto=True,
            ajuda="; ".join(motivos)
            if motivos
            else "Sem erro de QA, VT/valor no limite, pares e R² do beta suficientes.",
        ),
        cartoes.cartao(
            "Upside",
            cartoes.texto_com_sinal(res.numero(resumo, "upside")),
            bruto=True,
            subs=_subs_valuation(c, "upside"),
        ),
        cartoes.cartao(
            "Retorno esperado x hurdle",
            fo.taxa(ke_implicito),
            pequeno=f"x {fo.taxa(hurdle)}",
            ajuda=AJUDAS["retorno"],
            subs=[
                ("Diferença", cartoes.texto_com_sinal(diferenca)),
                *_subs_valuation(c, "ke_implicito"),
            ],
        ),
        cartoes.cartao(
            "Preço teto Bazin",
            fo.reais(res.numero(resumo, "preco_teto_bazin")),
            ajuda="Dividendo médio por ação dos últimos exercícios (DFC) / yield mínimo de "
            f"{fo.formatar(yield_minimo, '%', 2)}. Informativo: a recomendação usa o preço "
            "máximo de compra do perfil.",
        ),
        cartoes.cartao(
            "Dividendo médio por ação", fo.reais(res.numero(resumo, "dividendo_por_acao_bazin"))
        ),
    ]


def _componentes(r: res.Resultado) -> dict[str, float]:
    if r.wacc is None:
        return {}
    tabela = r.wacc[r.wacc["componente"] != "aviso"]
    valores = pd.to_numeric(tabela["valor"], errors="coerce")
    return {
        str(n): float(v) for n, v in zip(tabela["componente"], valores, strict=True) if pd.notna(v)
    }


def _cartoes_custo(r: res.Resultado, c: Comparacao | None) -> list[str]:
    comp = _componentes(r)
    comp.setdefault("ke", res.numero(r.resumo, "ke"))

    def valor(nome: str) -> float:
        return comp.get(nome, float("nan"))

    def com(chave: str, rotulo: str, nome: str, destaque: bool = False) -> str:
        i = scv.POR_CHAVE[chave]
        return cartoes.cartao(
            rotulo,
            _formatar(i, valor(nome)),
            ajuda=AJUDAS.get(chave, ""),
            subs=_subs_valuation(c, chave),
            destaque=destaque,
        )

    saida = [
        cartoes.cartao("Taxa livre de risco (Rf)", fo.taxa(valor("rf"))),
        cartoes.cartao("Prêmio de risco (ERP)", fo.taxa(valor("erp"))),
        com("beta", "Beta", "beta"),
        com("ke", "Custo do equity (Ke)", "ke", destaque=True),
    ]
    if r.modelo == "dcf":
        saida += [
            com("kd", "Custo da dívida (Kd)", "kd"),
            cartoes.cartao("Kd após imposto", fo.taxa(valor("kd_liquido"))),
            cartoes.cartao(
                "Peso da dívida",
                fo.taxa(valor("peso_divida")),
                subs=[cartoes.sub("Peso do equity", fo.taxa(valor("peso_equity")))],
            ),
            cartoes.cartao(
                "WACC",
                fo.taxa(res.numero(r.resumo, "wacc")),
                ajuda=AJUDAS["wacc"],
                subs=_subs_valuation(c, "wacc"),
                destaque=True,
            ),
        ]
    saida.append(
        cartoes.cartao(
            "Crescimento (g)",
            fo.taxa(res.numero(r.resumo, "g")),
            ajuda=AJUDAS["g"],
            subs=_subs_valuation(c, "g"),
        )
    )
    return saida


def _cartoes_multiplos(series: hm.SeriesMercado | None, c: Comparacao | None) -> list[str]:
    if series is None or series.multiplos.empty:
        return []
    saida = []
    for coluna in series.multiplos.columns:
        nome = cast(mt.NomeMultiplo, str(coluna))
        if nome not in MULTIPLOS_CARTOES:
            continue
        ultimo = float(series.multiplos[coluna].iloc[-1])
        saida.append(
            cartoes.cartao(
                mt.ROTULOS[nome], fo.multiplo(nome, ultimo, 2), subs=_subs_multiplo(c, nome)
            )
        )
    return saida


def _cartoes_checagens(r: res.Resultado, c: Comparacao | None) -> list[str]:
    saida = []
    for ch in res.checagens(r, dados.settings()):
        tom = "warn" if ch.ok is False else "ok"
        selo = (
            cartoes.selo("Atenção" if ch.ok is False else "Ok", tom)
            if ch.ok is not None
            else cartoes.TRACO
        )
        chave = "vt" if ch.nome == "VT / EV" else "vt_ddm" if ch.nome == "VT / valor" else ""
        saida.append(
            cartoes.cartao(
                ch.nome,
                selo,
                bruto=True,
                subs=[cartoes.sub("Valor", ch.valor), *_subs_valuation(c, chave)]
                if chave
                else [cartoes.sub("Valor", ch.valor)],
            )
        )
    return saida


def _cartoes_ponte(itens: pd.Series) -> list[str]:
    rotulos = grafico.ROTULOS_PONTE
    return [
        cartoes.cartao(
            rotulos.get(str(i), str(i)),
            fo.formatar(float(v), "mi", 0) + " mi",
            destaque=str(i) in ("valor_da_firma", "equity"),
        )
        for i, v in itens.items()
    ]


def _html(*blocos: str) -> None:
    st.html("".join(blocos))


def _avisos_custo(r: res.Resultado) -> None:
    if r.wacc is None:
        st.info("— `wacc.csv` não está nesta rodada.")
        return
    for aviso in r.wacc.loc[r.wacc["componente"] == "aviso", "detalhe"].dropna():
        st.warning(str(aviso))


# ---------------------------------------------------------------------------------------------
# Gráficos
# ---------------------------------------------------------------------------------------------


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
    cartoes_52 = None if series is None else hm.cartoes(series, base)
    faixas = res.faixas_football(r, cartoes_52.faixa_52_semanas if cartoes_52 else None)
    if not faixas:
        st.info("— sem faixas de valor nesta rodada.")
        return
    preco = res.numero(r.resumo, "preco")
    maximo = res.numero(r.resumo, "preco_maximo_compra")
    bazin = res.numero(r.resumo, "preco_teto_bazin")
    st.plotly_chart(grafico.football(faixas, preco, maximo, bazin), key="grafico_football")
    if any(f.aviso for f in faixas):
        st.caption("* Múltiplo de baixa confiança: menos pares válidos do que o mínimo.")


def _grupos_do_grafico(
    r: res.Resultado, c: Comparacao | None
) -> list[tuple[str, dict[str, float]]]:
    """Ke, Kd, WACC, g, upside e retorno esperado: ativo e referência de cada grupo."""
    comp = _componentes(r)
    comp.setdefault("ke", res.numero(r.resumo, "ke"))
    do_ativo = {
        "ke": comp.get("ke", float("nan")),
        "kd": comp.get("kd", float("nan")),
        "wacc": res.numero(r.resumo, "wacc"),
        "g": res.numero(r.resumo, "g"),
        "upside": res.numero(r.resumo, "upside"),
        "ke_implicito": res.numero(r.resumo, "ke_implicito"),
    }
    linhas = []
    for chave, valor in do_ativo.items():
        indicador = scv.POR_CHAVE[chave]
        if r.modelo not in indicador.modelos or pd.isna(valor):
            continue
        pontos = {"Ativo": valor}
        if c is not None:
            for grupo in c.grupos:
                ref = c.referencia(grupo, chave)
                if pd.notna(ref.valor):
                    pontos[scv.ROTULOS_GRUPO[grupo]] = ref.valor
        linhas.append((indicador.rotulo, pontos))
    return linhas


# ---------------------------------------------------------------------------------------------
# Visuais
# ---------------------------------------------------------------------------------------------


def _visual_cartoes(
    ticker: str,
    r: res.Resultado,
    base: dt.date,
    padronizada: emp.Padronizada | None,
    c: Comparacao | None,
    series: hm.SeriesMercado | None,
) -> None:
    _html(
        cartoes.secao("Valor por ação", _cartoes_valor(r)),
        cartoes.secao("Decisão", _cartoes_decisao(r, c)),
        cartoes.secao(
            "Custo de capital" if r.modelo == "dcf" else "Custo do capital próprio",
            _cartoes_custo(r, c),
        ),
    )
    _avisos_custo(r)
    multiplos = _cartoes_multiplos(series, c)
    if multiplos:
        _html(cartoes.secao("Múltiplos de mercado", multiplos))
    _html(cartoes.secao("Checagens", _cartoes_checagens(r, c)))
    _football(ticker, r, base, padronizada)
    _ponte(r)


def _visual_faixa(
    ticker: str,
    r: res.Resultado,
    base: dt.date,
    padronizada: emp.Padronizada | None,
    c: Comparacao | None,
    series: hm.SeriesMercado | None,
) -> None:
    resumo = r.resumo
    sinal = _texto(resumo, "recomendacao")
    ke_implicito = res.numero(resumo, "ke_implicito")
    resumo_topo = [
        ("Valor ponderado", escape(fo.reais(res.numero(resumo, "valor_ponderado"))), True),
        ("Upside", cartoes.texto_com_sinal(res.numero(resumo, "upside")), False),
        (
            "Recomendação",
            cartoes.selo(fo.sinal(sinal), TOM_RECOMENDACAO.get(sinal, "warn"))
            if sinal
            else cartoes.TRACO,
            False,
        ),
        (
            "Retorno x hurdle",
            escape(f"{fo.taxa(ke_implicito)} x {fo.taxa(res.numero(resumo, 'hurdle'))}"),
            False,
        ),
    ]
    _html(
        cartoes.faixa_de_preco(
            pessimista=res.numero(resumo, "valor_pessimista"),
            base=res.numero(resumo, "valor_base"),
            otimista=res.numero(resumo, "valor_otimista"),
            ponderado=res.numero(resumo, "valor_ponderado"),
            preco=res.numero(resumo, "preco"),
            maximo=res.numero(resumo, "preco_maximo_compra"),
            resumo=resumo_topo,
        )
    )
    esquerda, direita = st.columns(2)
    with esquerda:
        _html(
            cartoes.secao(
                "Custo de capital" if r.modelo == "dcf" else "Custo do capital próprio",
                _cartoes_custo(r, c),
            )
        )
        _avisos_custo(r)
    with direita:
        _html(cartoes.secao("Checagens", _cartoes_checagens(r, c)))
        multiplos = _cartoes_multiplos(series, c)
        if multiplos:
            _html(cartoes.secao("Múltiplos de mercado", multiplos))
    if r.ponte is not None:
        itens = res.ponte_de_cenario(r, "base")
        if itens is not None:
            _html(
                cartoes.secao(
                    "Ponte EV → equity (cenário base, R$ milhões)",
                    _cartoes_ponte(itens.reindex([i for i in ITENS_PONTE if i in itens.index])),
                )
            )
    _football(ticker, r, base, padronizada)


def _visual_graficos(
    ticker: str,
    r: res.Resultado,
    base: dt.date,
    padronizada: emp.Padronizada | None,
    c: Comparacao | None,
    series: hm.SeriesMercado | None,
) -> None:
    resumo = r.resumo
    comp = _componentes(r)
    esquerda, direita = st.columns(2)
    with esquerda:
        st.subheader("O preço embute menos ou mais que o perfil exige?")
        st.plotly_chart(
            grafico.retorno_contra_hurdle(
                res.numero(resumo, "ke_implicito"), res.numero(resumo, "hurdle")
            ),
            key="grafico_retorno",
        )
    with direita:
        st.subheader("Como o custo de capital se monta")
        st.plotly_chart(
            grafico.montagem_custo(
                comp.get("rf", float("nan")),
                comp.get("beta", float("nan")),
                comp.get("erp", float("nan")),
                comp.get("ke", res.numero(resumo, "ke")),
                res.numero(resumo, "wacc"),
                comp.get("kd_liquido", float("nan")),
                comp.get("peso_equity", float("nan")),
            ),
            key="grafico_montagem_custo",
        )
    _avisos_custo(r)
    linhas = _grupos_do_grafico(r, c)
    if linhas:
        st.subheader("O ativo contra setor e mercado" if c else "Taxas do ativo")
        st.plotly_chart(grafico.comparacao_taxas(linhas), key="grafico_comparacao")
        if c is None:
            st.caption("Ligue “Comparar com setor e mercado” para ver pares, setor CVM e Ibovespa.")
    _html(cartoes.secao("Checagens", _cartoes_checagens(r, c)))
    _football(ticker, r, base, padronizada)
    _ponte(r)


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
    topo_visual, topo_comparar = st.columns([3, 2])
    visual = topo_visual.radio(
        "Visual", VISUAIS, horizontal=True, key="visual_valuation", label_visibility="collapsed"
    )
    comparar = topo_comparar.toggle("Comparar com setor e mercado", key="comparar_valuation")
    for aviso in [*r.avisos_rodada, *r.avisos]:
        st.warning(aviso)
    comparacao = _montar_comparacao(ticker, r, base, padronizada) if comparar else None
    if comparacao is not None:
        setor = scv.setor_do_ativo(ticker, dados.universo())
        _situacao_dos_grupos(comparacao, ticker, None if setor is None else setor.name)
    series = None if padronizada is None else dados.series(padronizada, ticker, base)
    corpo = {"Cartões": _visual_cartoes, "Faixa de preço": _visual_faixa}.get(
        str(visual), _visual_graficos
    )
    corpo(ticker, r, base, padronizada, comparacao, series)
    if st.button("Rodar valuation de novo", key="rodar_valuation"):
        execucao = acoes.executar(f"Rodando {ticker}", atu.rodar_valuation(ticker))
        if execucao.ok:
            st.rerun()
        acoes.mostrar_falha(execucao)
