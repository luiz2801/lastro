import pandas as pd
import pytest

from sintetico import ano, contas_padronizadas, saldo, ytd
from valuation.contabil import ErroContabil
from valuation.contabil import periodos as per


@pytest.fixture
def contas() -> pd.DataFrame:
    """Exercícios 2024-2025, ITR de 2025 e 1S26; receita cresce, caixa é saldo."""
    return contas_padronizadas(
        [
            ano("receita_liquida", 2024, 90),
            ano("receita_liquida", 2025, 100),
            ytd("receita_liquida", "2025-03-31", 20),
            ytd("receita_liquida", "2025-06-30", 50),
            ytd("receita_liquida", "2025-09-30", 75),
            ytd("receita_liquida", "2026-03-31", 28),
            ytd("receita_liquida", "2026-06-30", 60),
            # Trimestre isolado da DRE (abr-jun) não entra nas visões: tudo parte do YTD.
            ("receita_liquida", "2026-04-01", "2026-06-30", 999),
            saldo("caixa", "2024-12-31", 5),
            saldo("caixa", "2025-06-30", 6),
            saldo("caixa", "2025-12-31", 8),
            saldo("caixa", "2026-06-30", 7),
        ]
    )


def test_anual(contas: pd.DataFrame) -> None:
    a = per.anual(contas)
    assert list(a.index) == [2024, 2025]
    assert a.loc[2025, "receita_liquida"] == 100
    assert a.loc[2024, "caixa"] == 5


def test_acumulado_no_ano(contas: pd.DataFrame) -> None:
    y = per.acumulado_no_ano(contas)
    assert y.loc[pd.Timestamp("2026-06-30"), "receita_liquida"] == 60
    assert y.loc[pd.Timestamp("2025-12-31"), "receita_liquida"] == 100


def test_ltm_meio_do_ano(contas: pd.DataFrame) -> None:
    serie = per.ltm(contas)
    assert serie.name == pd.Timestamp("2026-06-30")
    assert serie["receita_liquida"] == 100 + 60 - 50
    assert serie["caixa"] == 7


def test_ltm_em_dezembro_e_o_exercicio(contas: pd.DataFrame) -> None:
    serie = per.ltm(contas, pd.Timestamp("2025-12-31"))
    assert serie["receita_liquida"] == 100
    assert serie["caixa"] == 8


def test_ltm_falha_sem_componentes(contas: pd.DataFrame) -> None:
    sem_1s25 = contas[contas["dt_fim"] != pd.Timestamp("2025-06-30")]
    with pytest.raises(ErroContabil, match="2025-06-30"):
        per.ltm(sem_1s25, pd.Timestamp("2026-06-30"))
    with pytest.raises(ErroContabil, match="Sem balanço"):
        per.ltm(contas, pd.Timestamp("2025-09-30"))


def test_data_mais_recente_exige_fluxo_e_balanco() -> None:
    so_fluxo = contas_padronizadas([ano("receita_liquida", 2025, 1)])
    with pytest.raises(ErroContabil, match="balanço"):
        per.data_mais_recente(so_fluxo)


def test_trimestral(contas: pd.DataFrame) -> None:
    t = per.trimestral(contas)
    receita = t["receita_liquida"].dropna().to_dict()
    assert receita == {
        pd.Timestamp("2025-03-31"): 20,
        pd.Timestamp("2025-06-30"): 30,
        pd.Timestamp("2025-09-30"): 25,
        pd.Timestamp("2025-12-31"): 25,
        pd.Timestamp("2026-03-31"): 28,
        pd.Timestamp("2026-06-30"): 32,
    }
    assert t.loc[pd.Timestamp("2026-06-30"), "caixa"] == 7
    # 4T24 sem o 9M24: NaN (não inventa trimestre).
    assert pd.isna(t.loc[pd.Timestamp("2024-12-31"), "receita_liquida"])
