"""Indicadores por ativo (RF-004, ADR 0020, Etapa C3): a "página por ativo" em forma de tabela.

Funções puras sobre as métricas já calculadas pela camada contábil e sobre os `Fundamentos` dos
múltiplos; nenhum valor existente de DCF, DDM ou múltiplos muda. Dois grupos:

- **Históricos** (`historicos`, `historicos_financeira`): razões entre contas do mesmo período,
  por exercício e no LTM. Os que já existiam (margem EBITDA, ROIC, ROE e payout das financeiras)
  são só reexpostos; os novos são margem líquida, dívida líquida/EBITDA e ROE das não financeiras.
- **De mercado** (`de_mercado`): P/L, P/VP, dividend yield, EV/EBITDA e EV/EBIT, calculados por
  `modelos.multiplos.multiplo` (a mesma conta do `comparar`), em LTM e market cap da data-base.

Convenções: razão com denominador não positivo é NaN (margem sobre receita ≤ 0, dívida
líquida/EBITDA com EBITDA ≤ 0, ROE com PL inicial ≤ 0). A margem líquida e o ROE usam o lucro e o
PL da **controladora**; o ROE usa o PL do início do período (como o das financeiras, LL_t =
ROE_t x PL_{t-1}). Dívida líquida/EBITDA usa o EBITDA ajustado (o mesmo do EV/EBITDA) e a dívida
líquida conforme `ajustes.ifrs16` (arrendamento incluído por padrão).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from valuation.modelos import multiplos as mt

# Indicador -> (rótulo, unidade, chave do glossário).
HISTORICOS: dict[str, tuple[str, str, str]] = {
    "margem_liquida": ("Margem líquida", "%", "margem_liquida"),
    "margem_ebitda": ("Margem EBITDA", "%", "margem_ebitda"),
    "divida_liquida_ebitda": ("Dívida líquida / EBITDA", "x", "divida_liquida_ebitda"),
    "roe": ("ROE (PL inicial)", "%", "roe"),
    "roic": ("ROIC", "%", "roic"),
}
HISTORICOS_FINANCEIRA: dict[str, tuple[str, str, str]] = {
    "roe": ("ROE (PL inicial)", "%", "roe"),
    "payout": ("Payout", "%", "payout"),
    "roa": ("ROA", "%", "roa"),
    "alavancagem": ("Ativo / PL", "x", "alavancagem"),
}
# Múltiplos de mercado exibidos (todos existem em `modelos.multiplos`).
MERCADO: tuple[mt.NomeMultiplo, ...] = ("p_l", "p_vp", "dividend_yield", "ev_ebitda", "ev_ebit")
MERCADO_FINANCEIRA: tuple[mt.NomeMultiplo, ...] = mt.MULTIPLOS_FINANCEIRA


def _razao(numerador: pd.Series, denominador: pd.Series) -> pd.Series:
    """Numerador / denominador, NaN onde o denominador não é positivo."""
    return (numerador / denominador).where(denominador > 0).replace([np.inf, -np.inf], np.nan)


def historicos(m: pd.DataFrame) -> pd.DataFrame:
    """Indicadores de `contabil.nao_financeiras.metricas` (uma linha por período, ou o LTM).

    Aceita também `to_frame().T` do `metricas_ltm`. Colunas de `HISTORICOS`.
    """
    out = pd.DataFrame(index=m.index)
    out["margem_liquida"] = _razao(m["lucro_liquido_controladora"], m["receita_liquida"])
    out["margem_ebitda"] = m["margem_ebitda"].astype(float)
    out["divida_liquida_ebitda"] = _razao(m["divida_liquida"], m["ebitda_ajustado"])
    out["roe"] = _razao(m["lucro_liquido_controladora"], m["pl_controladora_inicio"])
    out["roic"] = m["roic"].astype(float)
    return out


def historicos_financeira(m: pd.DataFrame) -> pd.DataFrame:
    """Indicadores de `contabil.financeiras.metricas` (reexpostos sem mudar valor)."""
    return m.reindex(columns=list(HISTORICOS_FINANCEIRA)).astype(float)


def de_mercado(f: mt.Fundamentos, *, financeira: bool = False) -> dict[str, float]:
    """Múltiplos de mercado do ativo (NaN quando indefinidos, como no `comparar`)."""
    nomes = MERCADO_FINANCEIRA if financeira else MERCADO
    return {nome: mt.multiplo(f, nome) for nome in nomes}
