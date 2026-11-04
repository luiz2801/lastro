"""Indicadores por ativo (Etapa C3, ADR 0020): valores calculados à mão."""

import datetime as dt
import math

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


def _balanco() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Um período, com contas redondas: dá para conferir cada razão de cabeça."""
    largo = pd.DataFrame(
        {
            "ativo_total": [1000.0],
            "ativo_circulante": [400.0],
            "passivo_circulante": [200.0],
            "passivo_nao_circulante": [300.0],
            "estoques": [100.0],
            "realizavel_lp": [100.0],
            "emprestimos_cp": [50.0],
            "arrendamento_cp_em_emprestimos": [10.0],
            "arrendamento_cp_outros": [20.0],
            "despesas_financeiras": [-40.0],
        }
    )
    m = pd.DataFrame(
        {
            "patrimonio_liquido_total": [500.0],
            "caixa_e_aplicacoes": [150.0],
            "divida_financeira": [220.0],
            "divida_bruta": [250.0],
            "divida_liquida": [100.0],
            "ebitda_ajustado": [125.0],
            "ebit_ajustado": [80.0],
            "cfo": [100.0],
            "fcf_caixa": [60.0],
            "lucro_liquido_controladora": [30.0],
        }
    )
    return largo, m


def test_balanco_e_caixa_a_mao() -> None:
    largo, m = _balanco()
    v, motivos = ind.balanco_e_caixa(largo, m)
    esperado = {
        "divida_bruta_pl": 0.5,  # 250 / 500
        "divida_liquida_pl": 0.2,  # 100 / 500
        "divida_bruta_ebitda": 2.0,  # 250 / 125
        "divida_liquida_ebit": 1.25,  # 100 / 80
        "cobertura_juros": 2.0,  # 80 / 40
        "passivos_ativos": 0.5,  # (200 + 300) / 1000, e não a conta 2
        "pl_ativos": 0.5,
        "perfil_divida": 0.28,  # (50 - 10 + 10 + 20) / 250
        "liquidez_corrente": 2.0,
        "liquidez_seca": 1.5,  # (400 - 100) / 200
        "liquidez_imediata": 0.75,  # 150 / 200
        "liquidez_geral": 1.0,  # (400 + 100) / 500
        "caixa_aplicacoes": 150.0,
        "caixa_divida_cp": 150 / 70,
        "caixa_ativo": 0.15,
        "conversao_cfo_ebitda": 0.8,  # 100 / 125
        "conversao_fcf_lucro": 2.0,  # 60 / 30
    }
    for nome, valor in esperado.items():
        assert v[nome].iloc[0] == pytest.approx(valor), nome
    assert motivos.isna().all().all()


def test_balanco_sem_arrendamento_na_divida() -> None:
    largo, m = _balanco()
    v, _ = ind.balanco_e_caixa(largo, m, ifrs16="ignorar")
    assert v["perfil_divida"].iloc[0] == pytest.approx(40 / 250)  # só 50 - 10


def test_balanco_tem_todos_os_indicadores_do_catalogo_e_classes() -> None:
    from valuation.analise import anomalias as an

    largo, m = _balanco()
    v, _ = ind.balanco_e_caixa(largo, m)
    nomes = {n for grupo in ind.BALANCO.values() for n in grupo}
    assert set(v.columns) == nomes
    assert nomes - set(an.CLASSES) == {"caixa_aplicacoes"}  # valor em R$: sem tratamento
    assert an.CLASSES["cobertura_juros"] is an.Classe.PODE_NEGATIVO
    assert an.CLASSES["liquidez_seca"] is an.Classe.SO_MARCAR


def test_balanco_denominador_nao_positivo_vira_lacuna_com_motivo() -> None:
    largo, m = _balanco()
    m["patrimonio_liquido_total"] = -1.0
    m["ebit_ajustado"] = -5.0
    largo["despesas_financeiras"] = 0.0
    v, motivos = ind.balanco_e_caixa(largo, m)
    assert math.isnan(v["divida_bruta_pl"].iloc[0])
    assert motivos["divida_bruta_pl"].iloc[0] == "PL não positivo"
    assert motivos["divida_liquida_ebit"].iloc[0] == "EBIT não positivo"
    assert "não abre" in motivos["cobertura_juros"].iloc[0]


def test_balanco_conta_ausente_nunca_vira_zero() -> None:
    largo, m = _balanco()
    v, motivos = ind.balanco_e_caixa(largo.drop(columns=["estoques", "realizavel_lp"]), m)
    assert math.isnan(v["liquidez_seca"].iloc[0])
    assert motivos["liquidez_seca"].iloc[0] == ind.MOTIVO_CONTA_AUSENTE
    assert math.isnan(v["liquidez_geral"].iloc[0])
    assert v["liquidez_corrente"].iloc[0] == 2.0


def test_divida_zero_com_despesa_financeira_nao_mostra_zero() -> None:
    """ALOS3: debêntures em Outras Obrigações; a dívida mapeada dá zero e despesa existe."""
    largo, m = _balanco()
    m["divida_financeira"] = 0.0
    m["divida_bruta"] = 30.0  # só arrendamento
    m["divida_liquida"] = -120.0
    largo["emprestimos_cp"] = 0.0
    largo["arrendamento_cp_em_emprestimos"] = 0.0
    v, motivos = ind.balanco_e_caixa(largo, m)
    for nome in ("divida_bruta_pl", "divida_liquida_pl", "perfil_divida", "caixa_divida_cp"):
        assert math.isnan(v[nome].iloc[0]), nome
        assert motivos[nome].iloc[0] == ind.MOTIVO_DIVIDA_FORA
