"""`analise/serie_multiplos.py` e `analise/anomalias.py`: valores calculados à mão."""

import datetime as dt
import math

import numpy as np
import pandas as pd
import pytest

from valuation.analise import anomalias as an
from valuation.analise import serie_multiplos as sm
from valuation.modelos import multiplos as mt
from valuation.modelos import ponte as pt

D = pd.Timestamp


def _splits(*pares: tuple[str, float]) -> pd.Series:
    return pd.Series([f for _, f in pares], index=pd.DatetimeIndex([d for d, _ in pares]))


def _composicao(*pares: tuple[str, int]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "dt_refer": [D(d) for d, _ in pares],
            "qt_acao_ordin_cap_integr": [q for _, q in pares],
            "qt_acao_pref_cap_integr": 0,
            "qt_acao_total_cap_integr": [q for _, q in pares],
            "qt_acao_ordin_tesouro": 10,
            "qt_acao_pref_tesouro": 0,
            "qt_acao_total_tesouro": 10,
        }
    )


def test_fator_splits_so_conta_o_que_vem_depois_da_data() -> None:
    s = _splits(("2018-04-25", 1.3), ("2021-04-28", 2.0))
    assert sm.fator_splits(s, D("2017-12-31")) == pytest.approx(2.6)
    assert sm.fator_splits(s, D("2020-12-31")) == pytest.approx(2.0)
    assert sm.fator_splits(s, D("2021-04-28")) == 1.0  # o próprio dia não conta
    assert sm.fator_splits(s.iloc[:0], D("2020-12-31")) == 1.0


def test_grupamento_tem_fator_menor_que_um() -> None:
    assert sm.fator_splits(_splits(("2024-05-27", 0.1)), D("2023-12-31")) == pytest.approx(0.1)


def test_acoes_vao_para_a_base_de_hoje_pela_data_da_composicao() -> None:
    """WEGE3: 2:1 em 28/04/2021. A composição de 31/03 dobra; a de 30/06 já está na base nova."""
    comp = _composicao(("2021-03-31", 2_098_658_999), ("2021-06-30", 4_197_317_998))
    df = sm.acoes_na_base_atual(comp, _splits(("2021-04-28", 2.0)))
    assert df["qt_acao_ordin_cap_integr"].tolist() == [4_197_317_998, 4_197_317_998]
    assert df["qt_acao_ordin_tesouro"].tolist() == [20, 10]


def test_conferir_splits_avisa_nos_dois_sentidos() -> None:
    comp = _composicao(("2020-12-31", 100), ("2021-12-31", 200), ("2022-12-31", 200))
    assert sm.conferir_splits(comp, _splits(("2021-04-28", 2.0))) == []
    sem_split = sm.conferir_splits(comp, _splits())
    assert len(sem_split) == 1 and "2.00x" in sem_split[0] and "1.00x" in sem_split[0]
    so_split = sm.conferir_splits(
        _composicao(("2020-12-31", 100), ("2021-12-31", 100)), _splits(("2021-04-28", 2.0))
    )
    assert len(so_split) == 1


def test_conferir_splits_tolera_recompra_pequena() -> None:
    comp = _composicao(("2020-12-31", 1000), ("2021-12-31", 970))
    assert sm.conferir_splits(comp, _splits()) == []


def test_pontos_mensais_pega_o_ultimo_pregao_ate_a_base() -> None:
    indice = pd.DatetimeIndex(
        ["2016-10-31", "2025-01-30", "2025-01-31", "2025-02-27", "2025-03-03"]
    )
    pontos = sm.pontos_mensais(indice, dt.date(2025, 3, 1), anos=10)
    assert list(pontos) == [D("2016-10-31"), D("2025-01-31"), D("2025-02-27")]
    assert sm.pontos_mensais(indice, dt.date(2000, 1, 1), anos=1).empty


def test_entrada_usa_a_divulgacao_e_o_fallback() -> None:
    divulgacoes = pd.DataFrame(
        {
            "dt_refer": [D("2020-03-31"), D("2020-03-31")],
            "dt_receb": [D("2020-05-05"), D("2020-06-20")],
        }
    )
    e = sm.datas_de_entrada([D("2020-03-31"), D("2020-06-30"), D("2020-12-31")], divulgacoes)
    assert e[D("2020-03-31")] == D("2020-05-05")  # a 1ª divulgação
    assert e[D("2020-06-30")] == D("2020-06-30") + pd.Timedelta(days=45)
    assert e[D("2020-12-31")] == D("2020-12-31") + pd.Timedelta(days=90)


def test_vigencia_nao_olha_o_futuro() -> None:
    entradas = pd.Series({D("2019-12-31"): D("2020-03-20"), D("2020-03-31"): D("2020-05-05")})
    v = sm.vigencia(pd.DatetimeIndex(["2020-02-28", "2020-04-30", "2020-05-29"]), entradas)
    assert pd.isna(v.iloc[0])  # nada divulgado ainda
    assert v.iloc[1] == D("2019-12-31")  # o 1T já encerrou, mas não foi divulgado
    assert v.iloc[2] == D("2020-03-31")


def _fund(lucro: float = 10.0, pl: float = 50.0, ebitda: float = 20.0) -> mt.Fundamentos:
    itens = pt.ItensPonte(30.0, 10.0, 0.0, 0.0, 0.0, 1, dt.date(2020, 1, 1))
    return mt.Fundamentos(
        ticker="X",
        market_cap=float("nan"),
        itens=itens,
        lucro_liquido=lucro,
        ebitda=ebitda,
        ebit=ebitda,
        receita_liquida=100.0,
        patrimonio_liquido=pl,
        fcff=5.0,
        dividendos=2.0,
    )


def test_serie_multiplo_a_mao_com_lacunas() -> None:
    datas = pd.DatetimeIndex(["2020-01-31", "2020-02-28", "2020-03-31", "2020-04-30"])
    caps = pd.Series([100.0, 200.0, float("nan"), 400.0], index=datas)
    fim = D("2019-12-31")
    vigentes = pd.Series([pd.NaT, fim, fim, D("2020-03-31")], index=datas)
    fund = {fim: _fund()}
    pl = sm.serie_multiplo("p_l", caps, vigentes, fund)
    assert math.isnan(pl.iloc[0])  # sem LTM
    assert pl.iloc[1] == pytest.approx(20.0)  # 200 / 10
    assert math.isnan(pl.iloc[2])  # sem market cap
    assert math.isnan(pl.iloc[3])  # LTM vigente indisponível: lacuna, não zero
    ev = sm.serie_multiplo("ev_ebitda", caps, vigentes, fund)
    assert ev.iloc[1] == pytest.approx((200 + 30 - 10) / 20)  # EV pela ponte do balanço
    dy = sm.serie_multiplo("dividend_yield", caps, vigentes, fund)
    assert dy.iloc[1] == pytest.approx(0.01)


def test_prejuizo_vira_lacuna() -> None:
    datas = pd.DatetimeIndex(["2020-02-28"])
    fim = D("2019-12-31")
    pl = sm.serie_multiplo(
        "p_l", pd.Series([100.0], index=datas), pd.Series([fim], index=datas), {fim: _fund(-1.0)}
    )
    assert math.isnan(pl.iloc[0])


def test_cortar_periodo() -> None:
    indice = pd.date_range("2015-01-01", "2026-11-04", freq="MS")
    df = pd.DataFrame({"close": np.arange(len(indice))}, index=indice)
    base = dt.date(2026, 11, 4)
    assert sm.cortar_periodo(df, "YTD", base).index[0] == D("2026-01-01")
    assert sm.cortar_periodo(df, "1 ano", base).index[0] == D("2025-12-01")
    assert sm.cortar_periodo(df, "1 mês", base).index[0] == D("2026-11-01")
    assert sm.cortar_periodo(df, "Máximo", base).index[0] == D("2015-01-01")
    assert sm.cortar_periodo(df, "Máximo", dt.date(2020, 1, 1)).index[-1] == D("2020-01-01")


def _serie(valores: list[float]) -> pd.Series:
    return pd.Series(valores, index=range(len(valores)), dtype="float64")


def test_log_iqr_a_mao_e_nao_conta_lacuna() -> None:
    # 15 positivos: ln de 10 a 24 (Q1 e Q3 lineares sobre ln), mais NaN e negativos.
    valores = [float(v) for v in range(10, 25)]
    s = _serie([*valores, 500.0, -3.0, 0.0, float("nan")])
    f = an.filtrar(s, an.Classe.POSITIVO, corte_fixo=80.0)
    logs = np.log([*valores, 500.0])
    q1, q3 = np.quantile(logs, [0.25, 0.75])
    corte = float(np.exp(q3 + 1.5 * (q3 - q1)))
    assert f.metodo == "log_iqr"
    assert f.limite_superior == pytest.approx(corte)
    assert 500.0 not in f.validos.to_numpy()
    assert len(f.validos) == 15
    assert f.descartados.loc[16] == "múltiplo ≤ 0"
    assert f.descartados.loc[17] == "múltiplo ≤ 0"
    assert "acima do corte" in f.descartados.loc[15]
    assert len(f.descartados) == 3  # a lacuna não é descarte


def test_com_menos_de_15_usa_o_corte_fixo() -> None:
    f = an.filtrar(_serie([10.0, 20.0, 30.0, 90.0, -1.0]), an.Classe.POSITIVO, corte_fixo=80.0)
    assert f.metodo == "corte_fixo"
    assert f.limite_superior == 80.0
    assert f.validos.tolist() == [10.0, 20.0, 30.0]
    assert an.referencia(f, "mediana") == 20.0
    assert an.referencia(f, "media_simples") == 20.0
    assert an.referencia(f, "media_winsorizada") == pytest.approx((10 + 20 + 30 + 80) / 4)


def test_positivo_sem_corte_fixo_so_tira_negativos() -> None:
    f = an.filtrar(_serie([10.0, 900.0, -1.0]), an.Classe.POSITIVO)
    assert f.metodo == "sem_corte"
    assert f.validos.tolist() == [10.0, 900.0]


def test_tukey_corta_nos_dois_lados_na_escala_linear() -> None:
    s = _serie([-100.0, 1.0, 2.0, 3.0, 4.0, 5.0, 100.0])
    f = an.filtrar(s, an.Classe.PODE_NEGATIVO)
    q1, q3 = 1.5, 4.5  # quantis lineares de 7 pontos
    assert f.metodo == "tukey"
    assert f.limite_inferior == pytest.approx(q1 - 1.5 * (q3 - q1))
    assert f.limite_superior == pytest.approx(q3 + 1.5 * (q3 - q1))
    assert f.validos.tolist() == [1.0, 2.0, 3.0, 4.0, 5.0]
    assert an.referencia(f, "media_winsorizada") == pytest.approx(
        (f.limite_inferior + 15 + f.limite_superior) / 7
    )


def test_negativo_legitimo_fica() -> None:
    f = an.filtrar(_serie([-5.0, -4.0, -3.0, -2.0, -1.0]), an.Classe.PODE_NEGATIVO)
    assert len(f.validos) == 5
    assert f.descartados.empty


def test_dividend_yield_so_marca() -> None:
    s = _serie([0.05, 0.05, 0.06, 0.06, 0.07, 0.40])
    f = an.filtrar(s, an.Classe.SO_MARCAR)
    assert len(f.validos) == 6
    assert f.descartados.empty
    assert f.marcados.tolist() == [0.40]


def test_poucos_pontos_nao_calcula_quartil() -> None:
    assert an.filtrar(_serie([1.0, 99.0]), an.Classe.PODE_NEGATIVO).metodo == "sem_corte"
    assert an.filtrar(_serie([1.0, 99.0]), an.Classe.SO_MARCAR).marcados.empty


def test_sem_ponto_valido_a_referencia_e_nan_nao_zero() -> None:
    f = an.filtrar(_serie([-1.0, float("nan")]), an.Classe.POSITIVO, corte_fixo=80.0)
    assert math.isnan(an.referencia(f, "mediana"))
    assert math.isnan(an.referencia(f, "media_winsorizada"))


def test_sugestao_alternativa_do_guia() -> None:
    assert "EV/EBITDA" in an.sugestao_alternativa("múltiplo ≤ 0")
    assert "PEG" in an.sugestao_alternativa("acima do corte (80,0x)")
