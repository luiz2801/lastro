"""Tabelas de sensibilidade do valor por ação (seção 12 do CLAUDE.md e ADR 0008).

- WACC x g: só a taxa de desconto e o g da perpetuidade mudam; a projeção explícita é a mesma.
- Margem EBITDA terminal x crescimento da receita: deltas somados a todos os anos explícitos,
  como nos cenários; linhas rotuladas pela margem do último ano e colunas pelo crescimento médio.

Financeiras (DDM):

- Ke x g: a taxa e o g da perpetuidade (o payout final, 1 - g / ROE_LP, acompanha o g).
- ROE de longo prazo x Ke: o delta do ROE entra em rampa (zero no primeiro ano, inteiro no
  último), mudando o ponto de chegada da trajetória e não o ponto de partida.

Célula impossível (g >= WACC ou Ke, RONIC <= g, ROE_LP <= g) fica vazia (NaN).
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from valuation.modelos import ErroModelo, dcf, ddm
from valuation.projecao import ErroProjecao
from valuation.projecao import financeira as pf
from valuation.projecao import projetor as pj


def eixo(centro: float, passo: float, faixa: float) -> tuple[float, ...]:
    """De centro - faixa a centro + faixa, de `passo` em `passo` (o centro sempre incluso)."""
    n = round(faixa / passo)
    return tuple(round(centro + k * passo, 10) for k in range(-n, n + 1))


def _valor(
    premissas: pj.PremissasResolvidas, dados: dcf.DadosAvaliacao, wacc: float, ronic: dcf.Ronic
) -> float:
    try:
        return dcf.avaliar(premissas, dados, wacc=wacc, ronic=ronic).valor_por_acao
    except (ErroModelo, ErroProjecao):
        return float("nan")


def wacc_x_g(
    premissas: pj.PremissasResolvidas,
    dados: dcf.DadosAvaliacao,
    *,
    wacc: float,
    ronic: dcf.Ronic,
    passo_wacc: float,
    faixa_wacc: float,
    passo_g: float,
    faixa_g: float,
) -> pd.DataFrame:
    """Valor por ação (BRL): índice `wacc`, colunas `g`."""
    taxas = eixo(wacc, passo_wacc, faixa_wacc)
    gs = eixo(premissas.g_terminal, passo_g, faixa_g)
    valores = [
        [
            _valor(replace(premissas, g_terminal=g), dados, w, ronic) if w > g else float("nan")
            for g in gs
        ]
        for w in taxas
    ]
    return pd.DataFrame(
        np.array(valores), index=pd.Index(taxas, name="wacc"), columns=pd.Index(gs, name="g")
    )


def margem_x_crescimento(
    premissas: pj.PremissasResolvidas,
    dados: dcf.DadosAvaliacao,
    *,
    wacc: float,
    ronic: dcf.Ronic,
    passo_margem: float,
    faixa_margem: float,
    passo_crescimento: float,
    faixa_crescimento: float,
) -> pd.DataFrame:
    """Valor por ação (BRL): índice `margem_ebitda_terminal`, colunas `crescimento_medio`."""
    deltas_m = eixo(0.0, passo_margem, faixa_margem)
    deltas_g = eixo(0.0, passo_crescimento, faixa_crescimento)
    valores = [
        [
            _valor(
                pj.aplicar_cenario(
                    premissas,
                    pj.DeltaResolvido(crescimento=dg, margem_ebitda=dm),
                    premissas.cenario,
                ),
                dados,
                wacc,
                ronic,
            )
            for dg in deltas_g
        ]
        for dm in deltas_m
    ]
    margem = premissas.margem_ebitda[-1]
    crescimento = float(np.mean(premissas.crescimento))
    return pd.DataFrame(
        np.array(valores),
        index=pd.Index([round(margem + d, 10) for d in deltas_m], name="margem_ebitda_terminal"),
        columns=pd.Index([round(crescimento + d, 10) for d in deltas_g], name="crescimento_medio"),
    )


def _valor_ddm(premissas: pf.PremissasFinanceiras, dados: ddm.DadosDDM, ke: float) -> float:
    try:
        return ddm.avaliar(premissas, dados, ke=ke).valor_por_acao
    except (ErroModelo, ErroProjecao):
        return float("nan")


def ke_x_g(
    premissas: pf.PremissasFinanceiras,
    dados: ddm.DadosDDM,
    *,
    ke: float,
    passo_ke: float,
    faixa_ke: float,
    passo_g: float,
    faixa_g: float,
) -> pd.DataFrame:
    """Valor por ação (BRL) pelo DDM: índice `ke`, colunas `g`."""
    taxas = eixo(ke, passo_ke, faixa_ke)
    gs = eixo(premissas.g_terminal, passo_g, faixa_g)
    valores = [
        [
            _valor_ddm(replace(premissas, g_terminal=g), dados, k) if k > g else float("nan")
            for g in gs
        ]
        for k in taxas
    ]
    return pd.DataFrame(
        np.array(valores), index=pd.Index(taxas, name="ke"), columns=pd.Index(gs, name="g")
    )


def rampa_roe(premissas: pf.PremissasFinanceiras, delta: float) -> pf.PremissasFinanceiras:
    """Soma `delta` ao ROE de longo prazo, em rampa a partir de zero no primeiro ano."""
    n = len(premissas.roe)
    pesos = np.linspace(0.0, 1.0, n) if n > 1 else np.ones(1)
    roe = tuple(float(r + delta * w) for r, w in zip(premissas.roe, pesos, strict=True))
    return replace(premissas, roe=roe)


def roe_x_ke(
    premissas: pf.PremissasFinanceiras,
    dados: ddm.DadosDDM,
    *,
    ke: float,
    passo_roe: float,
    faixa_roe: float,
    passo_ke: float,
    faixa_ke: float,
) -> pd.DataFrame:
    """Valor por ação (BRL) pelo DDM: índice `roe_longo_prazo`, colunas `ke`."""
    deltas = eixo(0.0, passo_roe, faixa_roe)
    taxas = eixo(ke, passo_ke, faixa_ke)
    valores = [[_valor_ddm(rampa_roe(premissas, d), dados, k) for k in taxas] for d in deltas]
    roe_lp = premissas.roe_longo_prazo
    return pd.DataFrame(
        np.array(valores),
        index=pd.Index([round(roe_lp + d, 10) for d in deltas], name="roe_longo_prazo"),
        columns=pd.Index(taxas, name="ke"),
    )
