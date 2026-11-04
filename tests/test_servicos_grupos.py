"""Série de um grupo: corte por mês à mão, lacunas, balanço defasado e quem fica de fora."""

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sintetico import dfp_completa, juntar
from valuation.analise import anomalias as an
from valuation.analise import serie_multiplos as sm
from valuation.config import Settings, carregar_settings
from valuation.data import cvm
from valuation.servicos import comparacao as scmp
from valuation.servicos import grupos as grp

BASE = dt.date(2026, 4, 30)
MESES = pd.to_datetime(["2026-01-31", "2026-02-28", "2026-03-31"])


def _empresa(ticker: str, cd: int) -> dict[str, object]:
    return {
        "ticker": ticker,
        "cnpj": str(cd),
        "cd_cvm": cd,
        "razao_social": ticker,
        "nome_comercial": ticker,
        "setor_cvm": "s",
        "tipo_modelo": "nao_financeira",
        "escala_acoes": 1,
        "especie": "ON",
        "acoes_por_unit": 0,
    }


CADASTRO = pd.DataFrame(
    [_empresa("AAAA3", 1), _empresa("BBBB3", 2), _empresa("CCCC3", 3), _empresa("DDDD3", 4)]
)


@pytest.fixture
def settings() -> Settings:
    return carregar_settings()


def _com_serie(raiz: Path, ticker: str, cd: int, preco: float) -> None:
    pasta = raiz / "processed" / "cvm" / str(cd)
    pasta.mkdir(parents=True)
    juntar(dfp_completa(2024), dfp_completa(2025)).to_parquet(
        pasta / "demonstracoes.parquet", index=False
    )
    pd.DataFrame(
        {
            "dt_refer": [pd.Timestamp("2024-12-31")],
            "qt_acao_ordin_cap_integr": [9],
            "qt_acao_pref_cap_integr": [0],
            "qt_acao_total_cap_integr": [9],
            "qt_acao_ordin_tesouro": [0],
            "qt_acao_pref_tesouro": [0],
            "qt_acao_total_tesouro": [0],
        }
    ).to_parquet(pasta / cvm.ARQUIVO_SERIES_COMPOSICAO, index=False)
    precos = raiz / "raw" / "precos"
    precos.mkdir(parents=True, exist_ok=True)
    indice = pd.DatetimeIndex(["2026-01-30", "2026-02-27", "2026-03-31"], name="data")
    pd.DataFrame({"close": preco, "adj_close": preco, "volume": 1.0}, index=indice).to_parquet(
        precos / f"yf_{ticker}.SA_20160430_20260430.parquet"
    )
    pd.DataFrame({"fator": [1.0]}, index=pd.DatetimeIndex(["2010-01-01"], name="data")).to_parquet(
        precos / f"splits_{ticker}.SA.parquet"
    )


def _painel(raiz: Path, settings: Settings, *tickers: str) -> grp.PainelGrupo:
    return grp.montar_painel(
        tickers,
        CADASTRO,
        settings,
        BASE,
        dir_raw=raiz / "raw",
        dir_processed=raiz / "processed",
        dir_empresas=raiz / "empresas",
    )


def test_serie_do_grupo_a_mao() -> None:
    painel = pd.DataFrame(
        {
            "A": [10.0, 10.0, np.nan],
            "B": [20.0, 20.0, 20.0],
            "C": [30.0, 90.0, np.nan],  # 90 está acima do corte de 80x em fevereiro
        },
        index=MESES,
    )
    r = sm.serie_do_grupo(painel, an.Classe.POSITIVO, "mediana", 80.0, 2)
    assert r["valor"].iloc[0] == 20.0  # mediana de 10, 20, 30
    assert r["valor"].iloc[1] == 15.0  # 90 fora: mediana de 10 e 20
    assert r["n"].tolist() == [3, 2, 1]
    assert np.isnan(r["valor"].iloc[2])  # 1 empresa, menos que o mínimo de 2: lacuna


def test_serie_do_grupo_media_simples_e_negativa_entra() -> None:
    painel = pd.DataFrame({"A": [-1.0], "B": [3.0]}, index=MESES[:1])
    r = sm.serie_do_grupo(painel, an.Classe.PODE_NEGATIVO, "media_simples", None, 2)
    assert r["valor"].iloc[0] == 1.0


def test_mes_parcial_sai_so_no_fim() -> None:
    painel = pd.DataFrame({"A": [1.0, 2.0, 3.0]}, index=MESES)
    parcial = pd.Series([64, 64, 4], index=MESES)
    assert list(sm.sem_mes_parcial(painel, parcial).index) == list(MESES[:2])
    metade = pd.Series([64, 64, 32], index=MESES)
    assert len(sm.sem_mes_parcial(painel, metade)) == 3  # metade ainda conta como o mês
    no_meio = pd.Series([64, 4, 64], index=MESES)
    assert len(sm.sem_mes_parcial(painel, no_meio)) == 3  # só o último mês é candidato
    assert len(sm.sem_mes_parcial(painel, pd.Series([4], index=MESES[:1]))) == 3


def test_defasados_a_mao() -> None:
    vigentes = pd.Series(
        [pd.Timestamp("2025-12-31"), pd.Timestamp("2020-12-31"), pd.NaT],
        index=pd.to_datetime(["2026-03-31", "2026-03-31", "2026-03-31"]),
    )
    assert sm.defasados(vigentes, 12).tolist() == [False, True, False]


def test_painel_com_e_sem_serie_em_disco(tmp_path: Path, settings: Settings) -> None:
    _com_serie(tmp_path, "AAAA3", 1, 10.0)
    _com_serie(tmp_path, "BBBB3", 2, 20.0)
    r = _painel(tmp_path, settings, "AAAA3", "BBBB3", "CCCC3", "ZZZZ3")
    assert r.em_disco == 2 and len(r.tickers) == 4
    assert r.faltam["CCCC3"] == grp.MOTIVO_SEM_SERIE
    assert "ZZZZ3" in r.faltam["ZZZZ3"]
    # 9 ações, lucro 9: P/L = preço. Mediana de 10 e 20 = 15, com n = 2 < 3 pares: lacuna.
    pl = r.multiplos["p_l"]
    assert pl.loc[pd.Timestamp("2026-03-31")].tolist() == pytest.approx([10.0, 20.0])
    s = grp.referencia_em_serie(r, "p_l", "mediana", settings)
    assert s is not None
    assert s["n"].iloc[-1] == 2 and np.isnan(s["valor"].iloc[-1])


def test_tres_empresas_saem_da_lacuna(tmp_path: Path, settings: Settings) -> None:
    for ticker, cd, preco in (("AAAA3", 1, 10.0), ("BBBB3", 2, 20.0), ("CCCC3", 3, 30.0)):
        _com_serie(tmp_path, ticker, cd, preco)
    r = _painel(tmp_path, settings, "AAAA3", "BBBB3", "CCCC3")
    s = grp.referencia_em_serie(r, "p_l", "mediana", settings)
    assert s is not None
    assert s["valor"].iloc[-1] == pytest.approx(20.0)
    assert grp.referencia_em_serie(r, "ev_receita", "mediana", settings) is None


def test_preparar_calculo_avisa_quem_falta(tmp_path: Path, settings: Settings) -> None:
    _com_serie(tmp_path, "AAAA3", 1, 10.0)
    avisos = grp.preparar_calculo(
        ["AAAA3", "CCCC3"],
        CADASTRO,
        settings,
        BASE,
        dir_raw=tmp_path / "raw",
        dir_processed=tmp_path / "processed",
        dir_empresas=tmp_path / "empresas",
    )
    assert avisos == [f"CCCC3: {grp.MOTIVO_SEM_SERIE}"]


def test_medida_com_balanco_defasado_sai_da_media(tmp_path: Path, settings: Settings) -> None:
    _com_serie(tmp_path, "AAAA3", 1, 10.0)
    pasta = tmp_path / "processed" / "cvm" / "1"
    pd.read_parquet(pasta / cvm.ARQUIVO_SERIES_COMPOSICAO).to_parquet(
        pasta / "composicao_capital.parquet", index=False
    )
    medir = lambda base: scmp.medir_varios(  # noqa: E731
        ["AAAA3"],
        CADASTRO,
        settings,
        base,
        dir_raw=tmp_path / "raw",
        dir_processed=tmp_path / "processed",
        dir_empresas=tmp_path / "empresas",
    )[0]
    assert medir(BASE).fundamentos is not None
    defasada = medir(dt.date(2027, 3, 31))
    assert defasada.fundamentos is None and "mais de 12 meses" in str(defasada.motivo)
