"""`servicos/comparacao.py` e a análise de um múltiplo: à mão, sem rede."""

import datetime as dt
import math
from pathlib import Path

import pandas as pd
import pytest

from sintetico import dfp_completa, juntar
from valuation.config import Setor, Settings, carregar_settings
from valuation.contabil import padronizacao as pad
from valuation.data import cadastro as cad
from valuation.data.cadastro import ClasseAcao, Empresa
from valuation.modelos import multiplos as mt
from valuation.modelos import ponte as pt
from valuation.projecao import premissas as pm
from valuation.servicos import comparacao as scmp
from valuation.servicos import empresa as emp
from valuation.servicos import historico_mercado as hm
from valuation.universo import EmpresaUniverso, SetorCVM

BASE = dt.date(2026, 4, 30)


@pytest.fixture
def settings() -> Settings:
    return carregar_settings()


def _fund(ticker: str, cap: float, lucro: float = 10.0, dividendos: float = 1.0) -> mt.Fundamentos:
    return mt.Fundamentos(
        ticker=ticker,
        market_cap=cap,
        itens=pt.ItensPonte(0.0, 0.0, 0.0, 0.0, 0.0, 1, dt.date(2026, 1, 1)),
        lucro_liquido=lucro,
        ebitda=10.0,
        ebit=10.0,
        receita_liquida=100.0,
        patrimonio_liquido=100.0,
        fcff=1.0,
        dividendos=dividendos,
    )


def _medida(ticker: str, pl: float) -> scmp.Medida:
    return scmp.Medida(ticker, _fund(ticker, pl * 10.0))


def test_tickers_pares_tira_a_propria_empresa() -> None:
    premissas = pm.premissas_padrao("PETR4", "nao_financeira", ("PETR3", "PETR4"))
    premissas = premissas.model_copy(
        update={"pares": pm.Pares(incluir=("VALE3",), excluir=("RECV3",))}
    )
    setor = Setor(
        descricao="x",
        tipo_modelo="nao_financeira",
        commodity=True,
        pares=("PETR4", "PRIO3", "RECV3"),
    )
    assert scmp.tickers_pares(premissas, ("PETR3", "PETR4"), setor) == ["PRIO3", "VALE3"]
    assert scmp.tickers_pares(premissas, ("PETR3",), None) == ["VALE3"]


def test_corte_fixo_vem_do_settings(settings: Settings) -> None:
    assert scmp.corte_fixo(settings, "p_l") == 80
    assert scmp.corte_fixo(settings, "p_vp") == 15
    assert scmp.corte_fixo(settings, "ev_ebitda") == 40
    assert scmp.corte_fixo(settings, "ev_ebit") == 60
    assert scmp.corte_fixo(settings, "dividend_yield") is None


def test_referencia_de_poucos_pares_usa_corte_fixo_e_guarda_o_motivo(settings: Settings) -> None:
    medidas = [
        _medida("AAAA3", 10.0),
        _medida("BBBB3", 20.0),
        _medida("CCCC3", 90.0),  # acima dos 80x
        scmp.Medida("DDDD3", _fund("DDDD3", 100.0, lucro=-5.0)),  # prejuízo
        scmp.Medida("EEEE3", None, "sem cotação em disco"),
    ]
    r = scmp.referencia_do_grupo(medidas, "p_l", "mediana", settings)
    assert r.valor == pytest.approx(15.0)
    assert r.n == 2
    assert "80,0x" in r.descartadas["CCCC3"]
    assert r.descartadas["DDDD3"] == "múltiplo ≤ 0"
    assert "EEEE3" not in r.descartadas


def test_referencia_sem_ninguem_valido_e_nan(settings: Settings) -> None:
    r = scmp.referencia_do_grupo([scmp.Medida("A", None, "x")], "p_l", "mediana", settings)
    assert math.isnan(r.valor)
    assert r.n == 0


def test_ibovespa_separa_financeiras_e_tira_holdings() -> None:
    setor = next(iter(SetorCVM))
    universo = [
        EmpresaUniverso("AAAA3", setor, "nao_financeira"),
        EmpresaUniverso("BANK4", setor, "financeira"),
        EmpresaUniverso("HOLD4", setor, "holding"),
    ]
    assert scmp.tickers_ibovespa(universo, False) == ["AAAA3"]
    assert scmp.tickers_ibovespa(universo, True) == ["BANK4"]


def _padronizada(raiz: Path) -> emp.Padronizada:
    empresa = Empresa(
        cnpj="1",
        cd_cvm=1,
        razao_social="X",
        nome_comercial="X",
        setor_cvm="s",
        tipo_modelo="nao_financeira",
        escala_acoes=1,
        classes=(ClasseAcao("XXXX3", "ON"),),
    )
    premissas = pm.premissas_padrao("XXXX3", "nao_financeira", empresa.tickers)
    plano = pad.carregar_mapeamento(tipo="nao_financeira")
    dados = juntar(dfp_completa(2024), dfp_completa(2025))
    selecionadas = pad.selecionar_reapresentacoes(dados, consolidado=True)
    contas = pad.padronizar(selecionadas, plano, ticker="XXXX3")
    return emp.Padronizada(empresa, plano, selecionadas, contas, "BRL", premissas, raiz / "x.yaml")


def test_medir_de_hoje_a_mao_e_com_motivos(tmp_path: Path, settings: Settings) -> None:
    p = _padronizada(tmp_path)
    r = scmp.medir_de_hoje(
        p, settings, BASE, dir_raw=tmp_path / "raw", dir_processed=tmp_path / "proc"
    )
    assert r.fundamentos is None and r.motivo == "sem composição do capital em disco"
    pasta = tmp_path / "proc" / "cvm" / "1"
    pasta.mkdir(parents=True)
    pd.DataFrame(
        {
            "dt_refer": [pd.Timestamp("2025-12-31")],
            "qt_acao_ordin_cap_integr": [9],
            "qt_acao_pref_cap_integr": [0],
            "qt_acao_ordin_tesouro": [0],
            "qt_acao_pref_tesouro": [0],
        }
    ).to_parquet(pasta / "composicao_capital.parquet")
    r = scmp.medir_de_hoje(
        p, settings, BASE, dir_raw=tmp_path / "raw", dir_processed=tmp_path / "proc"
    )
    assert r.motivo == "sem cotação em disco"
    precos = tmp_path / "raw" / "precos"
    precos.mkdir(parents=True)
    pd.DataFrame(
        {"close": [10.0, 99.0]},
        index=pd.DatetimeIndex(["2026-04-29", "2026-05-29"], name="data"),  # o 2º é futuro
    ).to_parquet(precos / "yf_XXXX3.SA_20160430_20260430.parquet")
    r = scmp.medir_de_hoje(
        p, settings, BASE, dir_raw=tmp_path / "raw", dir_processed=tmp_path / "proc"
    )
    assert r.fundamentos is not None
    assert mt.multiplo(r.fundamentos, "p_l") == pytest.approx(10.0)  # 9 ações a R$ 10 sobre lucro 9


def test_medir_varios_devolve_o_motivo_sem_parar(tmp_path: Path, settings: Settings) -> None:
    cadastro = pd.DataFrame(columns=["ticker", "cnpj"])
    medidas = scmp.medir_varios(
        ["ZZZZ3"],
        cadastro,
        settings,
        BASE,
        dir_raw=tmp_path,
        dir_processed=tmp_path,
        dir_empresas=tmp_path,
    )
    assert medidas[0].fundamentos is None
    assert "ZZZZ3" in str(medidas[0].motivo)
    assert cad.normalizar_ticker("zzzz3") == medidas[0].ticker.upper()


def _series(valores: list[float], nao_positivos: list[bool] | None = None) -> hm.SeriesMercado:
    indice = pd.date_range(end="2026-04-30", periods=len(valores), freq="ME")
    multiplos = pd.DataFrame({"p_l": valores, "dividend_yield": 0.05}, index=indice)
    marcas = nao_positivos or [False] * len(valores)
    return hm.SeriesMercado(
        "XXXX3",
        pd.DataFrame(
            {"close": [10.0, 12.0, 11.0]},
            index=pd.DatetimeIndex(["2025-01-02", "2026-04-29", "2026-05-29"]),
        ),
        multiplos,
        pd.Series(100.0, index=indice),
        pd.Series(pd.NaT, index=indice, dtype="datetime64[ns]"),
        None,
        [],
        pd.DataFrame({"p_l": marcas, "dividend_yield": False}, index=indice),
    )


def test_analise_conta_descartes_e_lacunas_e_olha_a_janela(settings: Settings) -> None:
    base = [10.0] * 11 + [11.0] * 10 + [float("nan"), float("nan"), 900.0, 12.0]
    marcas = [False] * 21 + [True, False, False, False]
    a = hm.analisar_multiplo(_series(base, marcas), "p_l", 10, "mediana", settings, BASE)
    assert a.atual == 12.0
    assert a.referencia == pytest.approx(10.5)  # 11 x 10, 10 x 11 e um 12: entre o 11º e o 12º
    assert len(a.descartados) == 2  # 900x e o mês de prejuízo
    assert "múltiplo ≤ 0" in set(a.descartados)
    assert a.lacunas == 1  # o outro NaN não tem motivo: é lacuna
    assert a.aviso_referencia is None
    curta = hm.analisar_multiplo(_series(base, marcas), "p_l", 1, "media_simples", settings, BASE)
    assert len(curta.serie) == 12
    assert curta.aviso_referencia is not None


def test_atual_em_prejuizo_fica_nan(settings: Settings) -> None:
    a = hm.analisar_multiplo(
        _series([10.0, float("nan")], [False, True]), "p_l", 10, "mediana", settings, BASE
    )
    assert math.isnan(a.atual)


def test_cartoes_usam_o_ultimo_fechamento_ate_a_base(settings: Settings) -> None:
    c = hm.cartoes(_series([10.0, 12.0]), BASE)
    assert c is not None
    assert c.preco == 12.0
    assert c.data_preco == dt.date(2026, 4, 29)
    assert c.faixa_52_semanas == (12.0, 12.0)  # o de 2025-01 está fora dos 52 semanas
    assert c.market_cap == 100.0
    assert c.dividend_yield == 0.05
    assert hm.cartoes(_series([10.0]), dt.date(2000, 1, 1)) is None
