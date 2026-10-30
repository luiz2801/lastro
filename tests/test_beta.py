import datetime as dt

import numpy as np
import pandas as pd
import pytest

from valuation.custo_capital import ErroCustoCapital
from valuation.custo_capital import beta as bt

DATA_BASE = dt.date(2026, 10, 30)  # sexta-feira


def precos(retornos: np.ndarray, fim: dt.date = DATA_BASE) -> pd.Series:
    """Série de preços semanais (sextas) que gera exatamente os `retornos` dados."""
    datas = pd.date_range(end=pd.Timestamp(fim), periods=len(retornos) + 1, freq="W-FRI")
    return pd.Series(100 * np.cumprod(np.r_[1.0, 1 + retornos]), index=datas)


def mercado(n: int, semente: int = 1) -> np.ndarray:
    return np.random.default_rng(semente).normal(0.002, 0.03, n)


def test_regressao_recupera_beta_conhecido() -> None:
    rm = mercado(300)
    r = bt.regressao(
        precos(0.001 + 1.2 * rm),
        precos(rm),
        data_base=DATA_BASE,
        janela_semanas=260,
        ajuste_blume=False,
        min_r2_aviso=0.1,
        ticker="TEST3",
    )
    assert r.beta == pytest.approx(1.2)
    assert r.beta_bruto == pytest.approx(1.2)
    assert r.r2 == pytest.approx(1.0)
    assert r.n_obs == 260
    assert r.fim == DATA_BASE
    assert r.avisos == ()


def test_regressao_com_blume_e_janela_curta() -> None:
    rm = mercado(100)
    r = bt.regressao(
        precos(1.2 * rm),
        precos(rm),
        data_base=DATA_BASE,
        janela_semanas=260,
        ajuste_blume=True,
        min_r2_aviso=0.1,
    )
    assert r.beta_bruto == pytest.approx(1.2)
    assert r.beta == pytest.approx(0.67 * 1.2 + 0.33)
    assert r.n_obs == 100
    assert any("janela incompleta (100 de 260" in a for a in r.avisos)


def test_regressao_ignora_precos_depois_da_data_base() -> None:
    rm = mercado(300)
    acao = precos(1.5 * rm, fim=dt.date(2026, 12, 25))
    indice = precos(rm, fim=dt.date(2026, 12, 25))
    r = bt.regressao(
        acao, indice, data_base=DATA_BASE, janela_semanas=52, ajuste_blume=False, min_r2_aviso=0
    )
    assert r.fim == DATA_BASE
    assert r.n_obs == 52


def test_regressao_avisa_r2_baixo_e_baixa_liquidez() -> None:
    rm = mercado(260)
    ruido = np.random.default_rng(7).normal(0, 0.03, 260)
    ruido[::5] = 0.0  # 20% das semanas sem variação
    r = bt.regressao(
        precos(ruido), precos(rm), data_base=DATA_BASE, janela_semanas=260,
        ajuste_blume=False, min_r2_aviso=0.10, ticker="XPTO3",
    )  # fmt: skip
    assert any("R²" in a for a in r.avisos)
    assert any("baixa liquidez" in a for a in r.avisos)


def test_regressao_exige_minimo_de_semanas() -> None:
    rm = mercado(30)
    with pytest.raises(ErroCustoCapital, match="só 30 semanas"):
        bt.regressao(
            precos(rm), precos(rm), data_base=DATA_BASE, janela_semanas=260,
            ajuste_blume=False, min_r2_aviso=0,
        )  # fmt: skip


def test_hamada_ida_e_volta() -> None:
    # 1,2 / (1 + 0,66 x 0,5) = 1,2 / 1,33
    assert bt.desalavancar(1.2, 0.5, 0.34) == pytest.approx(1.2 / 1.33)
    assert bt.realavancar(bt.desalavancar(1.2, 0.5, 0.34), 0.5, 0.34) == pytest.approx(1.2)


def test_comparaveis_mediana_desalavancada() -> None:
    pares = {"A": (1.33, 0.5), "B": (1.0, 0.0), "C": (2.0, 1.0 / 0.66)}  # beta_u = 1, 1, 1
    r = bt.comparaveis(pares, divida_sobre_equity_alvo=0.25, aliquota=0.34)
    assert r.beta_bruto == pytest.approx(1.0)
    assert r.beta == pytest.approx(1.165)
    assert r.avisos == ()
    assert bt.comparaveis({"A": (1.0, 0.0)}, divida_sobre_equity_alvo=0, aliquota=0.34).avisos
    with pytest.raises(ErroCustoCapital, match="sem pares"):
        bt.comparaveis({}, divida_sobre_equity_alvo=0, aliquota=0.34)


def test_classe_mais_liquida() -> None:
    datas = pd.date_range(end="2026-10-30", periods=10, freq="B")
    on = pd.DataFrame({"close": 40.0, "volume": 1e6}, index=datas)
    pn = pd.DataFrame({"close": 38.0, "volume": 3e6}, index=datas)
    assert bt.classe_mais_liquida({"PETR3": on, "PETR4": pn}, DATA_BASE, 260) == "PETR4"
    with pytest.raises(ErroCustoCapital):
        bt.classe_mais_liquida({"PETR3": on.iloc[:0]}, DATA_BASE, 260)


def test_manual() -> None:
    assert bt.manual(0.9).beta == 0.9
