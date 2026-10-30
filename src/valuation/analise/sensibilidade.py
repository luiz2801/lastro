"""Tabelas de sensibilidade do valor por ação (seção 12 do CLAUDE.md e ADR 0008).

- WACC x g: só a taxa de desconto e o g da perpetuidade mudam; a projeção explícita é a mesma.
- Margem EBITDA terminal x crescimento da receita: deltas somados a todos os anos explícitos,
  como nos cenários; linhas rotuladas pela margem do último ano e colunas pelo crescimento médio.

Célula impossível (g >= WACC, RONIC <= g) fica vazia (NaN).
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from valuation.modelos import ErroModelo, dcf
from valuation.projecao import ErroProjecao
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
