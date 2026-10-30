import dataclasses
import datetime as dt

import numpy as np
import pandas as pd
import pytest

from valuation.modelos import ErroModelo, dcf
from valuation.modelos import multiplos as mt
from valuation.modelos import ponte as pt

DATA = dt.date(2026, 9, 30)
SEM_ITENS = pt.ItensPonte(0.0, 0.0, 0.0, 0.0, 0.0, 100, DATA)
# EV = 1.000 + 300 - 100 + 50 - 20 + 10 = 1.240
ALVO = mt.Fundamentos(
    ticker="ALVO",
    market_cap=1000.0,
    itens=pt.ItensPonte(300.0, 100.0, 50.0, 20.0, 10.0, 100, DATA),
    lucro_liquido=100.0,
    ebitda=200.0,
    ebit=150.0,
    receita_liquida=1000.0,
    patrimonio_liquido=500.0,
    fcff=80.0,
    dividendos=50.0,
)


def par(ticker: str, lucro: float, ebitda: float, dividendos: float) -> mt.Fundamentos:
    """Par sem dívida nem caixa (EV = market cap = 1.000)."""
    return mt.Fundamentos(
        ticker=ticker,
        market_cap=1000.0,
        itens=SEM_ITENS,
        lucro_liquido=lucro,
        ebitda=ebitda,
        ebit=100.0,
        receita_liquida=500.0,
        patrimonio_liquido=400.0,
        fcff=50.0,
        dividendos=dividendos,
    )


# P/L 5, 10, 15, 100; EV/EBITDA 4, 6, 8 e indefinido; DY 5%, indefinido, 10%, 2%.
PARES = [
    par("A", 200.0, 250.0, 50.0),
    par("B", 100.0, 1000 / 6, 0.0),
    par("C", 1000 / 15, 125.0, 100.0),
    par("D", 10.0, -5.0, 20.0),
]


def test_ev_e_multiplos_calculados_a_mao() -> None:
    assert ALVO.ev == pytest.approx(1240)
    esperados = {
        "p_l": 10.0,
        "ev_ebitda": 6.2,
        "ev_ebit": 1240 / 150,
        "ev_receita": 1.24,
        "p_vp": 2.0,
        "ev_fcf": 15.5,
        "dividend_yield": 0.05,
    }
    for nome, valor in esperados.items():
        assert mt.multiplo(ALVO, nome) == pytest.approx(valor), nome  # type: ignore[arg-type]


def test_multiplo_indefinido() -> None:
    prejuizo = dataclasses.replace(ALVO, lucro_liquido=-10.0, patrimonio_liquido=float("nan"))
    assert np.isnan(mt.multiplo(prejuizo, "p_l"))
    assert np.isnan(mt.multiplo(prejuizo, "p_vp"))
    ev_negativo = dataclasses.replace(ALVO, market_cap=10.0)  # EV = 250 - 1.000 + ... < 0
    ev_negativo = dataclasses.replace(
        ev_negativo, itens=dataclasses.replace(ALVO.itens, caixa_e_aplicacoes=2000.0)
    )
    assert ev_negativo.ev < 0
    assert np.isnan(mt.multiplo(ev_negativo, "ev_ebitda"))


def test_fundamentos_converte_e_usa_controladora() -> None:
    ltm = pd.Series(
        {
            "lucro_liquido_controladora": 10.0,
            "ebitda_ajustado": 30.0,
            "ebit_ajustado": 20.0,
            "receita_liquida": 100.0,
            "patrimonio_liquido_total": 60.0,
            "minoritarios": 5.0,
            "fcff": 8.0,
            "dividendos_pagos": 4.0,
        }
    )
    itens = pt.ItensPonte(40.0, 10.0, 5.0, 2.0, 1.0, 10, DATA)
    f = mt.fundamentos("X", ltm, itens=itens, market_cap=500.0, cambio=2.0)
    assert f.patrimonio_liquido == pytest.approx(110.0)  # (60 - 5) x 2
    assert f.ebitda == 60.0
    assert f.itens.divida_bruta == 80.0
    assert f.itens.acoes == 10
    assert f.market_cap == 500.0  # já em BRL
    # EV = 500 + 80 - 20 + 10 - 4 + 2
    assert f.ev == pytest.approx(568.0)
    sem_minoritarios = mt.fundamentos(
        "X", ltm.drop("minoritarios").drop("dividendos_pagos"), itens=itens, market_cap=1.0
    )
    assert sem_minoritarios.patrimonio_liquido == 60.0
    assert np.isnan(sem_minoritarios.dividendos)


def test_winsorizar() -> None:
    v = mt.winsorizar(pd.Series([5.0, 10.0, 15.0, 100.0, np.nan]), 0.1, 0.9)
    # P10 = 5 + 0,3 x 5 = 6,5; P90 = 15 + 0,7 x 85 = 74,5
    assert list(v) == pytest.approx([6.5, 10.0, 15.0, 74.5])
    assert mt.winsorizar(pd.Series([np.nan]), 0.1, 0.9).empty


def test_estatisticas_a_mao() -> None:
    tab = mt.tabela_pares(PARES)
    assert list(tab.index) == ["A", "B", "C", "D"]
    assert tab.loc["C", "p_l"] == pytest.approx(15.0)
    assert np.isnan(tab.loc["D", "ev_ebitda"])
    e = mt.estatisticas(tab, inferior=0.1, superior=0.9, min_pares=3)
    pl = e.loc["p_l"]
    assert pl["n"] == 4
    assert pl["mediana"] == pytest.approx(12.5)
    assert pl["media"] == pytest.approx(26.5)
    assert pl["p25"] == pytest.approx(9.125)
    assert pl["p75"] == pytest.approx(29.875)
    assert (pl["minimo"], pl["maximo"]) == pytest.approx((6.5, 74.5))
    ev = e.loc["ev_ebitda"]
    assert (ev["n"], ev["mediana"], ev["confianca"]) == (3, pytest.approx(6.0), "normal")
    sem_winsor = mt.estatisticas(tab, inferior=0.0, superior=1.0, min_pares=4)
    assert sem_winsor.loc["p_l", "media"] == pytest.approx(32.5)
    assert sem_winsor.loc["ev_ebitda", "confianca"] == "baixa"


def test_valor_por_acao_a_mao() -> None:
    assert mt.valor_por_acao(ALVO, "p_l", 12.5) == pytest.approx(12.5)
    # EV = 6 x 200 = 1.200 -> equity = 1.200 - 300 + 100 - 50 + 20 - 10 = 960
    assert mt.valor_por_acao(ALVO, "ev_ebitda", 6.0) == pytest.approx(9.6)
    assert mt.valor_por_acao(ALVO, "p_vp", 1.5) == pytest.approx(7.5)
    assert mt.valor_por_acao(ALVO, "dividend_yield", 0.05) == pytest.approx(10.0)
    assert np.isnan(mt.valor_por_acao(ALVO, "p_l", float("nan")))
    sem_lucro = dataclasses.replace(ALVO, lucro_liquido=0.0)
    assert np.isnan(mt.valor_por_acao(sem_lucro, "p_l", 10.0))


def test_avaliar() -> None:
    r = mt.avaliar(ALVO, [*PARES, ALVO], inferior=0.1, superior=0.9, min_pares=3)
    assert "ALVO" not in r.pares.index
    assert r.mediana("ev_ebitda") == pytest.approx(6.0)
    impl = r.implicitos
    assert impl.loc["p_l", "valor_mediana"] == pytest.approx(12.5)
    assert impl.loc["p_l", "multiplo_alvo"] == pytest.approx(10.0)
    assert impl.loc["ev_ebitda", "valor_mediana"] == pytest.approx(9.6)
    assert impl.loc["ev_ebitda", "metrica"] == "ebitda"
    # DY dos pares 2%, 5%, 10% (winsorizados a 2,6% e 9%): mediana 5% -> 50 / 0,05 / 100
    assert impl.loc["dividend_yield", "valor_mediana"] == pytest.approx(10.0)
    assert impl.loc["dividend_yield", "valor_p25"] > impl.loc["dividend_yield", "valor_p75"]
    assert r.avisos == ()


def test_avaliar_avisos_e_erros() -> None:
    prejuizo = dataclasses.replace(ALVO, lucro_liquido=-1.0)
    r = mt.avaliar(prejuizo, PARES[:2], inferior=0.1, superior=0.9, min_pares=3)
    texto = " ".join(r.avisos)
    assert "baixa confiança" in texto
    assert "p_l (2)" in texto
    assert "ALVO sem métrica positiva para p_l" in texto
    assert np.isnan(r.implicitos.loc["p_l", "valor_mediana"])
    with pytest.raises(ErroModelo, match="sem pares"):
        mt.avaliar(ALVO, [ALVO], inferior=0.1, superior=0.9, min_pares=3)


def test_avaliar_exclui_par_com_escala_implausivel() -> None:
    # Market cap 1.000 vezes menor: P/VP = 1 / 400 = 0,0025.
    milhares = dataclasses.replace(PARES[0], ticker="MIL3", market_cap=1.0)
    r = mt.avaliar(ALVO, [*PARES, milhares], inferior=0.1, superior=0.9, min_pares=3)
    assert "MIL3" not in r.pares.index
    assert "MIL3: P/VP de 0.003" in r.avisos[0]
    assert "excluído dos pares" in r.avisos[0]
    alvo_milhares = dataclasses.replace(ALVO, market_cap=1.0)
    r = mt.avaliar(alvo_milhares, PARES, inferior=0.1, superior=0.9, min_pares=3)
    assert "ALVO: P/VP" in r.avisos[0]
    with pytest.raises(ErroModelo, match="sem pares válidos"):
        mt.avaliar(ALVO, [milhares], inferior=0.1, superior=0.9, min_pares=3)


def test_g_implicito() -> None:
    # RONIC = WACC: VT = NOPAT x (1 + g) / WACC = 100 x 1,05 / 0,1 = 1.050 = 5,25 x 200
    kw = {"ebitda_t": 200.0, "nopat_t": 100.0, "wacc": 0.1}
    assert dcf.g_implicito(5.25, ronic="wacc", **kw) == pytest.approx(0.05)
    # RONIC 20%: VT = 100 x 1,05 x (1 - 0,25) / 0,05 = 1.575 = 7,875 x 200
    assert dcf.g_implicito(7.875, ronic=0.2, **kw) == pytest.approx(0.05)
    assert dcf.g_implicito(5.5, ronic="wacc", **kw) is None  # g = WACC
    assert dcf.g_implicito(7.875, ronic=0.05, **kw) is None
    assert dcf.g_implicito(-1.0, ronic="wacc", **kw) is None
    assert dcf.g_implicito(5.0, ronic="wacc", ebitda_t=200.0, nopat_t=-1.0, wacc=0.1) is None
