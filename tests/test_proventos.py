"""DPA e dividend yield por ano e o adaptador de dividendos do yfinance, sem rede."""

import datetime as dt
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sintetico import dfp_completa, juntar
from valuation.analise import proventos as prv
from valuation.config import carregar_settings
from valuation.contabil import ErroContabil
from valuation.contabil import padronizacao as pad
from valuation.data import precos as prc
from valuation.data.cadastro import ClasseAcao, Empresa
from valuation.data.precos import ErroPrecos
from valuation.projecao import premissas as pm
from valuation.servicos import empresa as emp
from valuation.servicos import proventos as sprv

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


def test_dpa_12m_janela_aberta_no_inicio_e_fechada_na_data_base() -> None:
    datas = ["2025-10-01", "2025-10-02", "2026-10-01", "2026-10-02"]
    div = pd.Series([1.0, 2.0, 4.0, 8.0], index=pd.DatetimeIndex(datas))
    dpa, y = prv.dpa_12m(div, _historico(), dt.date(2026, 10, 1))
    assert dpa == 2.0 + 4.0  # 2025-10-01 fica fora (janela aberta); 2026-10-02 é futuro
    assert y == pytest.approx(6.0 / 30.0)  # último adj_close até a data-base
    vazio = pd.DataFrame({"adj_close": []}, index=pd.DatetimeIndex([]))
    assert pd.isna(prv.dpa_12m(div, vazio, dt.date(2026, 10, 1))[1])


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


def test_mediana_do_grupo_ignora_nan_e_conta_n() -> None:
    nan = float("nan")
    yields = {
        "A": pd.Series([0.02, 0.04], index=[2025, 2026]),
        "B": pd.Series([0.06, nan], index=[2025, 2026]),
        "C": pd.Series([0.10, 0.08], index=[2025, 2026]),
    }
    g = prv.mediana_do_grupo(yields)
    assert g["valor"].tolist() == pytest.approx([0.06, 0.06])  # 2026: mediana de 0,04 e 0,08
    assert g["n"].tolist() == [3, 2]
    assert prv.mediana_do_grupo({}).empty


def _grava(raiz: Path, simbolo: str, dividendos: bool, cotacao: bool) -> None:
    pasta = raiz / "precos"
    pasta.mkdir(parents=True, exist_ok=True)
    if dividendos:
        indice = pd.DatetimeIndex(["2025-03-10", "2026-03-10"], name="data")
        pd.DataFrame({"valor": [1.0, 2.0]}, index=indice).to_parquet(
            pasta / f"dividendos_{simbolo}.parquet"
        )
    if cotacao:
        indice = pd.DatetimeIndex(["2025-12-30", "2026-09-30"], name="data")
        pd.DataFrame({"close": 10.0, "adj_close": 10.0, "volume": 1.0}, index=indice).to_parquet(
            pasta / f"yf_{simbolo}_20160101_20261030.parquet"
        )


def test_yield_do_grupo_so_com_o_que_esta_em_disco(tmp_path: Path) -> None:
    _grava(tmp_path, "AAAA3.SA", dividendos=True, cotacao=True)
    _grava(tmp_path, "BBBB3.SA", dividendos=False, cotacao=True)
    _grava(tmp_path, "CCCC3.SA", dividendos=True, cotacao=False)
    g = sprv.yield_do_grupo(["AAAA3", "BBBB3", "CCCC3"], dt.date(2026, 10, 1), 2, dir_raw=tmp_path)
    assert list(g.por_empresa) == ["AAAA3"]
    assert g.faltam == {"BBBB3": "sem proventos em disco", "CCCC3": "sem cotação em disco"}
    assert g.serie["valor"].tolist() == pytest.approx([0.1, 0.2])  # 1/10 em 2025; 2/10 em 2026
    assert g.serie["n"].tolist() == [1, 1]


def test_payout_anual_a_mao() -> None:
    nan = float("nan")
    metricas = pd.DataFrame(
        {
            "dividendos_pagos": [50.0, 30.0, nan, 40.0, 10.0],
            "lucro_liquido_controladora": [100.0, -20.0, 80.0, 40.0, 25.0],
        },
        index=[2021, 2022, 2023, 2024, 2025],
    )
    t = prv.payout_anual(metricas, dt.date(2025, 6, 30), 3)  # 2025 ainda não encerrou
    assert t.index.tolist() == [2022, 2023, 2024]
    assert pd.isna(t.loc[2022, "payout"])  # lucro <= 0
    assert pd.isna(t.loc[2023, "payout"])  # dividendo ausente não vira zero
    assert t.loc[2024, "payout"] == pytest.approx(1.0)  # payout acima de 100% é válido
    with pytest.raises(ValueError):
        prv.payout_anual(metricas, dt.date(2025, 6, 30), 0)


def _padronizada(ticker: str = "XXXX3") -> emp.Padronizada:
    empresa = Empresa(
        cnpj="1",
        cd_cvm=1234,
        razao_social="X",
        nome_comercial="X",
        setor_cvm="s",
        tipo_modelo="nao_financeira",
        escala_acoes=1,
        classes=(ClasseAcao(ticker, "ON"),),
    )
    premissas = pm.premissas_padrao(ticker, "nao_financeira", empresa.tickers)
    plano = pad.carregar_mapeamento(tipo="nao_financeira")
    pago = {"DFC": {"6.03.05": ("Dividendos e Juros sobre o Capital Próprio Pagos", -11)}}
    dados = juntar(dfp_completa(2024, **pago), dfp_completa(2025, **pago))
    selecionadas = pad.selecionar_reapresentacoes(dados, consolidado=True)
    contas = pad.padronizar(selecionadas, plano, ticker=ticker)
    return emp.Padronizada(empresa, plano, selecionadas, contas, "BRL", premissas, Path("x.yaml"))


def test_payout_do_ativo_a_mao_sobre_a_dfp_sintetica() -> None:
    t = sprv.payout_por_ano(_padronizada(), carregar_settings(), dt.date(2026, 10, 30), 5)
    assert t.index.tolist() == [2024, 2025]
    # 11 de dividendos e 9 de lucro da controladora
    assert t.loc[2025, "dividendos_pagos"] == pytest.approx(11.0)
    assert t.loc[2025, "payout"] == pytest.approx(11.0 / 9.0)


def test_payout_do_grupo_separa_quem_nao_tem_demonstracoes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def padronizar(ticker: str, *_: object, **__: object) -> emp.Padronizada:
        if ticker == "SEM3":
            raise ErroContabil("sem demonstrações")
        return _padronizada(ticker)

    monkeypatch.setattr(sprv.emp, "padronizar", padronizar)
    g = sprv.payout_do_grupo(
        ["COM3", "SEM3"], pd.DataFrame(), carregar_settings(), dt.date(2026, 10, 30), 5
    )
    assert list(g.por_empresa) == ["COM3"]
    assert g.faltam == {"SEM3": "sem demonstrações"}
    assert g.serie["valor"].tolist() == pytest.approx([11.0 / 9.0, 11.0 / 9.0])
    assert g.serie["n"].tolist() == [1, 1]


def test_sem_linha_de_dividendos_o_payout_de_nao_financeira_e_zero() -> None:
    """Contrato atual de `nf.metricas`: `dividendos_pagos` ausente conta como 0, não como NaN."""
    sem = _padronizada()
    sem = emp.Padronizada(
        sem.empresa,
        sem.plano,
        sem.selecionadas,
        sem.contas[sem.contas["conta_padrao"] != "dividendos_pagos"],
        sem.moeda,
        sem.premissas,
        sem.caminho_premissas,
    )
    t = sprv.payout_por_ano(sem, carregar_settings(), dt.date(2026, 10, 30), 5)
    assert t["payout"].tolist() == [0.0, 0.0]
    assert not np.signbit(t["payout"]).any()  # nada de -0,0 na tela
    assert not np.signbit(t["dividendos_pagos"]).any()
