"""Indicadores por ativo (Etapa C3, ADR 0020): valores calculados à mão."""

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from valuation.analise import indicadores as ind
from valuation.modelos import multiplos as mt
from valuation.modelos import ponte as pt

# Dois exercícios: o 2º reproduz os números de tests/test_nao_financeiras.py (ANUAL, 2025).
M = pd.DataFrame(
    {
        "receita_liquida": [1000.0, 1200.0],
        "lucro_liquido_controladora": [120.0, 140.0],
        "margem_ebitda": [0.25, 320 / 1200],
        "divida_liquida": [150.0, 255.0],
        "ebitda_ajustado": [250.0, 315.0],
        "pl_controladora_inicio": [np.nan, 470.0],
        "roic": [np.nan, 0.2],
    },
    index=pd.Index([2024, 2025], name="ano"),
)


def test_historicos_calculados_a_mao() -> None:
    h = ind.historicos(M)
    assert h.loc[2025, "margem_liquida"] == pytest.approx(140 / 1200)
    assert h.loc[2025, "divida_liquida_ebitda"] == pytest.approx(255 / 315)
    assert h.loc[2025, "roe"] == pytest.approx(140 / 470)
    assert h.loc[2025, "margem_ebitda"] == pytest.approx(320 / 1200)  # reexposta
    assert h.loc[2025, "roic"] == 0.2  # reexposta
    assert pd.isna(h.loc[2024, "roe"])  # sem PL do início
    assert list(h.columns) == list(ind.HISTORICOS)


def test_razao_com_denominador_nao_positivo_e_nan() -> None:
    m = M.copy()
    m.loc[2025, ["receita_liquida", "ebitda_ajustado", "pl_controladora_inicio"]] = [0.0, -5.0, 0.0]
    h = ind.historicos(m)
    assert h.loc[2025, ["margem_liquida", "divida_liquida_ebitda", "roe"]].isna().all()


def test_caixa_liquido_da_divida_liquida_negativa() -> None:
    m = M.copy()
    m.loc[2025, "divida_liquida"] = -63.0
    assert ind.historicos(m).loc[2025, "divida_liquida_ebitda"] == pytest.approx(-0.2)


def test_ltm_como_linha_unica() -> None:
    h = ind.historicos(M.loc[[2025]].rename(index={2025: pd.Timestamp("2026-06-30")}))
    assert h.iloc[0]["roe"] == pytest.approx(140 / 470)


def test_historicos_financeira_reexpoe_sem_mudar_valor() -> None:
    m = pd.DataFrame(
        {
            "roe": [np.nan, 0.2],
            "payout": [0.4, 0.5],
            "roa": [0.02, 0.03],
            "alavancagem": [9.0, 10.0],
            "lucro_liquido": [1.0, 2.0],
        },
        index=[2024, 2025],
    )
    h = ind.historicos_financeira(m)
    assert list(h.columns) == list(ind.HISTORICOS_FINANCEIRA)
    assert h.loc[2025, "roe"] == 0.2 and h.loc[2025, "payout"] == 0.5


def _fundamentos() -> mt.Fundamentos:
    itens = pt.ItensPonte(300.0, 100.0, 0.0, 0.0, 0.0, 100, dt.date(2025, 12, 31))
    return mt.Fundamentos(
        ticker="SINT3",
        market_cap=1000.0,
        itens=itens,
        lucro_liquido=100.0,
        ebitda=300.0,
        ebit=200.0,
        receita_liquida=1000.0,
        patrimonio_liquido=500.0,
        fcff=80.0,
        dividendos=40.0,
    )


def test_de_mercado_calculado_a_mao() -> None:
    r = ind.de_mercado(_fundamentos())
    # EV = 1000 + 300 - 100 = 1200
    assert r["p_l"] == pytest.approx(10.0)
    assert r["p_vp"] == pytest.approx(2.0)
    assert r["dividend_yield"] == pytest.approx(0.04)
    assert r["ev_ebitda"] == pytest.approx(4.0)
    assert r["ev_ebit"] == pytest.approx(6.0)
    assert tuple(r) == ind.MERCADO


def test_de_mercado_financeira_so_equity() -> None:
    r = ind.de_mercado(_fundamentos(), financeira=True)
    assert tuple(r) == ("p_l", "p_vp", "dividend_yield")


def test_de_mercado_lucro_negativo_e_indefinido() -> None:
    f = _fundamentos()
    r = ind.de_mercado(mt.Fundamentos(**{**f.__dict__, "lucro_liquido": -1.0}))
    assert np.isnan(r["p_l"])
