"""DPA e dividend yield por ano e o adaptador de dividendos do yfinance, sem rede."""

import datetime as dt
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

from valuation.analise import proventos as prv
from valuation.data import precos as prc
from valuation.data.precos import ErroPrecos

AGORA = dt.datetime(2026, 11, 4, 12, tzinfo=dt.UTC)
TTL = dt.timedelta(hours=12)


def _dividendos() -> pd.Series:
    datas = ["2024-03-10", "2024-09-10", "2025-06-10", "2026-03-10", "2026-12-10"]
    indice = pd.DatetimeIndex(datas)
    return pd.Series([1.0, 0.5, 2.0, 3.0, 9.0], index=indice)


def _historico() -> pd.DataFrame:
    datas = ["2024-06-03", "2024-12-30", "2025-12-30", "2026-08-03", "2026-12-30"]
    indice = pd.DatetimeIndex(datas)
    return pd.DataFrame({"adj_close": [10.0, 15.0, 20.0, 30.0, 99.0]}, index=indice)


def test_dpa_anual_a_mao() -> None:
    t = prv.dpa_anual(_dividendos(), _historico(), dt.date(2026, 10, 1), 3)
    assert t.index.tolist() == [2024, 2025, 2026]
    assert t["dpa"].tolist() == [1.5, 2.0, 3.0]  # o de 2026-12-10 é posterior à data-base
    assert t["n_proventos"].tolist() == [2, 1, 1]
    assert t["preco"].tolist() == [15.0, 20.0, 30.0]  # ano corrente: último até a data-base
    assert t["dividend_yield"].tolist() == pytest.approx([0.1, 0.1, 0.1])
    assert t["parcial"].tolist() == [False, False, True]


def test_ano_sem_provento_tem_dpa_zero_e_sem_historico_yield_nan() -> None:
    div = pd.Series([1.0], index=pd.DatetimeIndex(["2026-03-10"]))
    t = prv.dpa_anual(div, _historico(), dt.date(2026, 10, 1), 4)
    assert t.loc[2025, "dpa"] == 0.0 and t.loc[2025, "dividend_yield"] == 0.0
    assert pd.isna(t.loc[2023, "preco"]) and pd.isna(t.loc[2023, "dividend_yield"])


def test_dpa_anual_sem_proventos_e_anos_invalido() -> None:
    vazio = pd.Series([], index=pd.DatetimeIndex([]), dtype="float64")
    t = prv.dpa_anual(vazio, _historico(), dt.date(2026, 10, 1), 1)
    assert t["dpa"].tolist() == [0.0]
    with pytest.raises(ValueError):
        prv.dpa_anual(vazio, _historico(), dt.date(2026, 10, 1), 0)


def _yf_falso(monkeypatch: pytest.MonkeyPatch, dividendos: object) -> list[str]:
    chamadas: list[str] = []

    class Ticker:
        def __init__(self, simbolo: str) -> None:
            chamadas.append(simbolo)

        @property
        def dividends(self) -> object:
            if isinstance(dividendos, Exception):
                raise dividendos
            return dividendos

    monkeypatch.setitem(sys.modules, "yfinance", types.SimpleNamespace(Ticker=Ticker))
    return chamadas


def _provedor(tmp_path: Path, agora: dt.datetime = AGORA) -> prc.YFinanceProvider:
    return prc.YFinanceProvider(tmp_path, TTL, agora)


def _serie_yahoo() -> pd.Series:
    indice = pd.DatetimeIndex(["2026-03-10 00:00:00"], tz="America/Sao_Paulo")
    return pd.Series([0.25], index=indice, name="Dividends")


def test_dividendos_baixa_normaliza_data_e_cacheia(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chamadas = _yf_falso(monkeypatch, _serie_yahoo())
    s = _provedor(tmp_path).dividendos("WEGE3.SA")
    assert s.loc[pd.Timestamp("2026-03-10")] == 0.25
    assert s.index.tz is None
    _provedor(tmp_path).dividendos("WEGE3.SA")
    assert chamadas == ["WEGE3.SA"]  # dentro do TTL, não consulta


def test_dividendos_falha_usa_copia_vencida_ou_erro(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _yf_falso(monkeypatch, RuntimeError("fora do ar"))
    with pytest.raises(ErroPrecos, match="fora do ar"):
        _provedor(tmp_path).dividendos("WEGE3.SA")
    _yf_falso(monkeypatch, _serie_yahoo())
    _provedor(tmp_path).dividendos("WEGE3.SA")
    _yf_falso(monkeypatch, RuntimeError("fora do ar"))
    depois = AGORA + dt.timedelta(days=30)
    assert _provedor(tmp_path, depois).dividendos("WEGE3.SA").iloc[0] == 0.25
