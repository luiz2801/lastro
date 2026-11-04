"""Cache em disco das séries e das medidas: mesmo resultado, sem recalcular, e invalida sozinho."""

import datetime as dt
import os
from pathlib import Path

import pandas as pd
import pytest

from sintetico import dfp_completa, juntar
from valuation.config import Settings, carregar_settings
from valuation.data import cvm
from valuation.servicos import comparacao as scmp
from valuation.servicos import derivados as drv
from valuation.servicos import empresa as emp
from valuation.servicos import historico_mercado as hm

BASE = dt.date(2026, 4, 30)
CADASTRO = pd.DataFrame(
    [
        {
            "ticker": "XXXX3",
            "cnpj": "1",
            "cd_cvm": 1234,
            "razao_social": "X",
            "nome_comercial": "X",
            "setor_cvm": "s",
            "tipo_modelo": "nao_financeira",
            "escala_acoes": 1,
            "especie": "ON",
            "acoes_por_unit": 0,
        }
    ]
)


@pytest.fixture
def settings() -> Settings:
    return carregar_settings()


@pytest.fixture
def raiz(tmp_path: Path) -> Path:
    pasta = tmp_path / "processed" / "cvm" / "1234"
    pasta.mkdir(parents=True)
    juntar(dfp_completa(2023), dfp_completa(2024), dfp_completa(2025)).to_parquet(
        pasta / "demonstracoes.parquet", index=False
    )
    composicao = pd.DataFrame(
        {
            "dt_refer": [pd.Timestamp("2025-12-31")],
            "qt_acao_ordin_cap_integr": [9],
            "qt_acao_pref_cap_integr": [0],
            "qt_acao_total_cap_integr": [9],
            "qt_acao_ordin_tesouro": [0],
            "qt_acao_pref_tesouro": [0],
            "qt_acao_total_tesouro": [0],
        }
    )
    composicao.to_parquet(pasta / cvm.ARQUIVO_SERIES_COMPOSICAO, index=False)
    composicao.to_parquet(pasta / "composicao_capital.parquet", index=False)
    pd.DataFrame(
        {
            "fonte": "DFP",
            "dt_refer": [pd.Timestamp("2024-12-31")],
            "dt_receb": [pd.Timestamp("2025-03-01")],
        }
    ).to_parquet(pasta / cvm.ARQUIVO_DIVULGACOES, index=False)
    precos = tmp_path / "raw" / "precos"
    precos.mkdir(parents=True)
    valores = [10.0, 20.0, 30.0]
    indice = pd.DatetimeIndex(["2026-01-30", "2026-02-27", "2026-03-31"], name="data")
    pd.DataFrame({"close": valores, "adj_close": valores, "volume": 1.0}, index=indice).to_parquet(
        precos / "yf_XXXX3.SA_20160430_20260430.parquet"
    )
    pd.DataFrame({"fator": [2.0]}, index=pd.DatetimeIndex(["2010-01-01"], name="data")).to_parquet(
        precos / "splits_XXXX3.SA.parquet"
    )
    return tmp_path


def _series(raiz: Path, settings: Settings, base: dt.date = BASE) -> hm.SeriesMercado:
    r = hm.series_com_cache(
        "XXXX3",
        CADASTRO,
        settings,
        base,
        dir_raw=raiz / "raw",
        dir_processed=raiz / "processed",
        dir_empresas=raiz / "empresas",
    )
    assert r is not None
    return r


def _sem_recalculo(monkeypatch: pytest.MonkeyPatch) -> None:
    def falha(*_: object, **__: object) -> None:
        raise AssertionError("recalculou com o cache válido")

    monkeypatch.setattr(emp, "padronizar", falha)


def test_serie_do_cache_e_igual_a_calculada_e_nao_recalcula(
    raiz: Path, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    primeira = _series(raiz, settings)
    assert primeira.multiplos["p_l"].tolist() == pytest.approx(
        [10.0, 20.0, 30.0]
    )  # 9 ações, lucro 9
    _sem_recalculo(monkeypatch)
    segunda = _series(raiz, settings)
    pd.testing.assert_frame_equal(primeira.multiplos, segunda.multiplos, check_freq=False)
    pd.testing.assert_series_equal(
        primeira.market_cap, segunda.market_cap, check_freq=False, check_names=False
    )
    pd.testing.assert_series_equal(
        primeira.vigencia, segunda.vigencia, check_freq=False, check_names=False
    )
    assert primeira.nao_positivos is not None and segunda.nao_positivos is not None
    pd.testing.assert_frame_equal(primeira.nao_positivos, segunda.nao_positivos, check_freq=False)
    assert primeira.avisos == segunda.avisos
    assert primeira.inicio_composicao == segunda.inicio_composicao


def test_entrada_alterada_invalida_o_cache(
    raiz: Path, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    _series(raiz, settings)
    chamadas: list[str] = []
    original = emp.padronizar

    def contar(*a: object, **k: object) -> emp.Padronizada:
        chamadas.append("x")
        return original(*a, **k)  # type: ignore[arg-type]

    monkeypatch.setattr(emp, "padronizar", contar)
    arquivo = raiz / "processed" / "cvm" / "1234" / "demonstracoes.parquet"
    os.utime(arquivo, ns=(1, 1))
    _series(raiz, settings)
    assert chamadas == ["x"]


def test_base_que_nao_muda_os_pontos_aproveita_o_cache(
    raiz: Path, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    _series(raiz, settings)
    _sem_recalculo(monkeypatch)
    _series(raiz, settings, dt.date(2026, 5, 15))


def test_cache_corrompido_recalcula(raiz: Path, settings: Settings) -> None:
    primeira = _series(raiz, settings)
    pasta = drv.pasta(raiz / "processed", 1234)
    (pasta / "series_XXXX3.parquet").write_text("lixo", encoding="utf-8")
    segunda = _series(raiz, settings)
    assert primeira.market_cap.tolist() == segunda.market_cap.tolist()


def test_sem_cotacao_devolve_none(tmp_path: Path, settings: Settings) -> None:
    assert (
        hm.series_com_cache(
            "XXXX3",
            CADASTRO,
            settings,
            BASE,
            dir_raw=tmp_path,
            dir_processed=tmp_path,
            dir_empresas=tmp_path,
        )
        is None
    )


def _medir(
    raiz: Path, settings: Settings, tickers: tuple[str, ...] = ("XXXX3",)
) -> list[scmp.Medida]:
    return scmp.medir_com_cache(
        tickers,
        CADASTRO,
        settings,
        BASE,
        dir_raw=raiz / "raw",
        dir_processed=raiz / "processed",
        dir_empresas=raiz / "empresas",
    )


def test_medida_do_cache_e_igual_a_calculada(
    raiz: Path, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    primeira = _medir(raiz, settings)[0]
    assert primeira.fundamentos is not None
    assert primeira.fundamentos.lucro_liquido == 9  # DFP sintética
    _sem_recalculo(monkeypatch)
    segunda = _medir(raiz, settings)[0]
    assert repr(primeira) == repr(segunda)


def test_medida_sem_cadastro_guarda_o_motivo(raiz: Path, settings: Settings) -> None:
    medidas = _medir(raiz, settings, ("ZZZZ3",))
    assert medidas[0].fundamentos is None and "ZZZZ3" in str(medidas[0].motivo)
