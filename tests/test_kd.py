import pandas as pd
import pytest

from valuation.custo_capital import ErroCustoCapital, kd

ANOS = pd.Index([2020, 2021, 2022, 2023, 2024])
DIVIDA = pd.Series([100.0, 100.0, 100.0, 100.0, 100.0], index=ANOS)
DESPESAS = pd.Series([-7.0, -8.0, -9.0, -10.0, -12.0], index=ANOS)  # sinal da DRE


def test_taxas_anuais_usam_divida_media() -> None:
    divida = pd.Series([100.0, 140.0], index=pd.Index([2023, 2024]))
    despesas = pd.Series([-5.0, -12.0], index=pd.Index([2023, 2024]))
    taxas = kd.taxas_anuais(despesas, divida)
    assert taxas.to_dict() == {2024: pytest.approx(12 / 120)}  # 2023 sem dívida anterior


def test_taxas_anuais_pula_buraco() -> None:
    divida = pd.Series([100.0, 100.0, 100.0], index=pd.Index([2020, 2022, 2023]))
    despesas = pd.Series([-1.0, -2.0, -3.0], index=pd.Index([2020, 2022, 2023]))
    assert list(kd.taxas_anuais(despesas, divida).index) == [2023]


def test_historico_mediana_de_tres_anos() -> None:
    r = kd.historico(DESPESAS, DIVIDA, piso=0.05, teto=0.20)
    assert r.kd == pytest.approx(0.10)  # mediana de 9%, 10%, 12%
    assert r.anos == (2022, 2023, 2024)
    assert r.avisos == ()


def test_historico_limitado_ao_piso_e_ao_teto() -> None:
    piso = kd.historico(DESPESAS, DIVIDA, piso=0.11, teto=0.20)
    assert piso.kd == 0.11 and piso.kd_bruto == pytest.approx(0.10)
    assert any("fora de" in a for a in piso.avisos)
    assert kd.historico(DESPESAS, DIVIDA, piso=0.0, teto=0.08).kd == 0.08


def test_historico_curto_e_sem_dados() -> None:
    r = kd.historico(DESPESAS.tail(2), DIVIDA.tail(2), piso=0, teto=1)
    assert r.anos == (2024,)
    assert any("só 1 exercício" in a for a in r.avisos)
    with pytest.raises(ErroCustoCapital, match="manual"):
        kd.historico(DESPESAS, DIVIDA * 0, piso=0, teto=1)


def test_manual() -> None:
    assert kd.manual(0.13).kd == 0.13
