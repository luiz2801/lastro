"""Formatação de texto em pt-BR, única para a CLI e a GUI (GUI-92).

Sem dado, o texto é "—" (ou "sem solução", nas taxas implícitas), nunca zero.
"""

from __future__ import annotations

import pandas as pd


def formatar(valor: float, unidade: str) -> str:
    """`%` com uma casa, `x` com uma casa ou, nas demais unidades, milhões sem casas."""
    if pd.isna(valor):
        return "—"
    if unidade == "%":
        return f"{valor:.1%}".replace(".", ",")
    if unidade == "x":
        return f"{valor:.1f}x".replace(".", ",")
    return f"{valor / 1e6:,.0f}".replace(",", ".")


def multiplo(nome: str, valor: float) -> str:
    """Dividend yield em %, demais múltiplos em x."""
    return formatar(valor, "%" if nome == "dividend_yield" else "x")


def componente_wacc(componente: str, valor: float) -> str:
    """Valor de uma linha de `wacc.csv`; vazio sem número (a linha é só de texto)."""
    if pd.isna(valor):
        return ""
    if componente in ("divida_bruta", "market_cap"):
        return f"{formatar(valor, 'mi')} mi"
    if componente == "beta_n_obs":
        return f"{valor:.0f}"
    if componente.startswith("beta"):
        return f"{valor:.3f}".replace(".", ",")
    return f"{valor:.2%}".replace(".", ",")


def reais(valor: float) -> str:
    return "—" if pd.isna(valor) else f"R$ {valor:,.2f}".translate(str.maketrans(",.", ".,"))


def brl(valor: float | None, casas: int = 2) -> str:
    if valor is None:
        return "—"
    texto = f"{valor:,.{casas}f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def preco_curto(valor: float | None) -> str:
    """Preço sem separador de milhar, como na tabela de favoritos."""
    return "—" if valor is None else f"R$ {valor:.2f}".replace(".", ",")


def taxa(valor: float | None) -> str:
    """Taxa implícita com duas casas; sem valor, a equação não teve solução."""
    return "sem solução" if valor is None or pd.isna(valor) else f"{valor:.2%}".replace(".", ",")


def pct(valor: float | None) -> str:
    return "—" if valor is None else f"{valor * 100:.1f}%".replace(".", ",")
