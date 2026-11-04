"""Formatação de texto em pt-BR, única para a CLI e a GUI (GUI-92).

Sem dado, o texto é "—" (ou "sem solução", nas taxas implícitas), nunca zero.
"""

from __future__ import annotations

import pandas as pd


def _ptbr(texto: str) -> str:
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar(valor: float, unidade: str, casas: int | None = None) -> str:
    """`%` e `x` com uma casa, milhões sem casas, salvo `casas` (a GUI usa 2)."""
    if pd.isna(valor):
        return "—"
    if unidade == "%":
        return _ptbr(f"{valor * 100:,.{1 if casas is None else casas}f}") + "%"
    if unidade == "x":
        return _ptbr(f"{valor:,.{1 if casas is None else casas}f}") + "x"
    return _ptbr(f"{valor / 1e6:,.{0 if casas is None else casas}f}")


def multiplo(nome: str, valor: float, casas: int | None = None) -> str:
    """Dividend yield em %, demais múltiplos em x."""
    return formatar(valor, "%" if nome == "dividend_yield" else "x", casas)


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
