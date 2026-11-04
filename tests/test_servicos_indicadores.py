"""`servicos/indicadores.py`: valores calculados à mão sobre as DFPs sintéticas."""

import dataclasses
import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from sintetico import dfp_banco, dfp_completa, juntar
from valuation.config import Settings, carregar_settings
from valuation.contabil import ErroContabil
from valuation.contabil import padronizacao as pad
from valuation.data import macro as mac
from valuation.data import precos as prc
from valuation.data.cadastro import ClasseAcao, Empresa
from valuation.data.validacao import manual
from valuation.projecao import premissas as pm
from valuation.servicos import empresa as emp
from valuation.servicos import indicadores as sind
from valuation.servicos import mercado as mer

BASE = dt.date(2026, 10, 30)


def _padronizada(dados: pd.DataFrame, tipo: str = "nao_financeira") -> emp.Padronizada:
    empresa = Empresa(
        cnpj="1",
        cd_cvm=1234,
        razao_social="X",
        nome_comercial="X",
        setor_cvm="s",
        tipo_modelo=tipo,
        escala_acoes=1,
        classes=(ClasseAcao("XXXX3", "ON"),),
    )
    premissas = pm.premissas_padrao("XXXX3", tipo, empresa.tickers)
    plano = pad.carregar_mapeamento(tipo=tipo)
    selecionadas = pad.selecionar_reapresentacoes(dados, consolidado=True)
    contas = pad.padronizar(selecionadas, plano, ticker="XXXX3")
    return emp.Padronizada(empresa, plano, selecionadas, contas, "BRL", premissas, Path("x.yaml"))


@pytest.fixture
def settings() -> Settings:
    return carregar_settings()


@pytest.fixture
def industria() -> emp.Padronizada:
    return _padronizada(juntar(dfp_completa(2024), dfp_completa(2025)))


def test_serie_nao_financeira_a_mao(industria: emp.Padronizada, settings: Settings) -> None:
    r = sind.serie_indicadores(industria, settings, BASE, anos=5)
    assert r.colunas == ["2024", "2025", "LTM 12/2025"]
    assert not r.financeira
    assert list(r.definicoes) == list(r.tabela.columns)
    ultimo = r.tabela.iloc[-1]
    assert ultimo["margem_liquida"] == pytest.approx(0.09)  # 9 / 100
    assert ultimo["margem_ebitda"] == pytest.approx(0.28)  # (20 + 8) / 100
    assert ultimo["roe"] == pytest.approx(9 / 95)  # PL inicial = 100 - 5


def test_serie_corta_na_data_base_e_nos_anos(
    industria: emp.Padronizada, settings: Settings
) -> None:
    so_um = sind.serie_indicadores(industria, settings, BASE, anos=1)
    assert so_um.colunas == ["2025", "LTM 12/2025"]
    tres_anos = _padronizada(juntar(dfp_completa(2023), dfp_completa(2024), dfp_completa(2025)))
    antes = sind.serie_indicadores(tres_anos, settings, dt.date(2025, 6, 30), anos=5)
    assert antes.colunas == ["2023", "2024", "LTM 12/2024"]


def test_serie_financeira_a_mao(settings: Settings) -> None:
    dados = juntar(
        dfp_banco(
            2024,
            BPP={
                "2.03": ("Passivos Financeiros ao Custo Amortizado", 890),
                "2.08": ("Patrimônio Líquido Consolidado", 110),
            },
        ),
        dfp_banco(2025),
    )
    r = sind.serie_indicadores(_padronizada(dados, "financeira"), settings, BASE, anos=5)
    assert r.financeira
    assert "margem_ebitda" not in r.tabela.columns
    assert r.tabela["roe"].iloc[1] == pytest.approx(22 / 90)
    assert r.tabela["payout"].iloc[1] == pytest.approx(0.5)


def test_data_balanco(industria: emp.Padronizada) -> None:
    assert sind.data_balanco(industria.contas, BASE) == pd.Timestamp("2025-12-31")
    with pytest.raises(ErroContabil, match="Nenhuma demonstração até 2020-01-01"):
        sind.data_balanco(industria.contas, dt.date(2020, 1, 1))


def _cap(valor: float, acoes: int) -> prc.MarketCap:
    classe = prc.ClasseMarketCap("XXXX3", "ON", acoes, valor / acoes)
    return prc.MarketCap(valor, (classe,), dt.date(2025, 12, 31), ())


def test_indicadores_de_mercado_a_mao(industria: emp.Padronizada, settings: Settings) -> None:
    macro = mac.Macro(
        BASE,
        selic=manual("Selic", 0.15),
        ipca_12m=manual("IPCA", 0.05),
        cambio=manual("Dólar", 5.0),
        rf_brl=manual("Rf", 0.13),
        ipca_esperado={},
        data_focus=None,
    )
    mk = mer.Mercado(
        industria.empresa,
        {"XXXX3": manual("XXXX3", 10.0)},
        manual("^BVSP", 1.0),
        macro,
        _cap(90.0, 9),
        None,  # type: ignore[arg-type]
    )
    r = sind.indicadores_de_mercado(industria, mk, settings, BASE)
    assert r.fundamentos.data_balanco == dt.date(2025, 12, 31)
    assert r.multiplos["p_l"] == pytest.approx(10.0)  # 90 / 9
    assert r.multiplos["p_vp"] == pytest.approx(90 / 95)  # PL da controladora 100 - 5


def test_fundamentos_converte_so_o_que_nao_e_brl(
    industria: emp.Padronizada, settings: Settings
) -> None:
    em_real = sind.fundamentos(industria, _cap(90.0, 9), settings, BASE, dolar=5.0)
    em_dolar = sind.fundamentos(
        dataclasses.replace(industria, moeda="USD"),
        _cap(90.0, 9),
        settings,
        BASE,
        dolar=5.0,
    )
    assert em_dolar.receita_liquida == pytest.approx(5 * em_real.receita_liquida)


def test_serie_balanco_a_mao(industria: emp.Padronizada, settings: Settings) -> None:
    r = sind.serie_balanco(industria, settings, BASE, anos=5)
    assert r is not None
    assert r.colunas == ["2024", "2025", "LTM 12/2025"]
    ultimo = r.tabela.iloc[-1]
    assert ultimo["liquidez_corrente"] == pytest.approx(
        industria.contas.query("conta_padrao == 'ativo_circulante'")["valor"].iloc[-1]
        / industria.contas.query("conta_padrao == 'passivo_circulante'")["valor"].iloc[-1]
    )
    assert list(r.motivos.columns) == list(r.tabela.columns)


def test_serie_balanco_de_financeira_e_none(settings: Settings) -> None:
    banco = _padronizada(juntar(dfp_banco(2024), dfp_banco(2025)), "financeira")
    assert sind.serie_balanco(banco, settings, BASE, anos=5) is None


def test_analisar_indicador_a_mao() -> None:
    serie = pd.Series([1.0, 1.0, 1.0, 1.0, 9.0], index=list("abcde"))
    a = sind.analisar_indicador(serie, None, "cobertura_juros", "mediana")
    assert a.atual == 9.0
    assert a.referencia == 1.0  # o 9 está acima do limite de Tukey e sai da referência
    assert list(a.descartados.index) == ["e"]
    marcado = sind.analisar_indicador(serie, None, "liquidez_corrente", "mediana")
    assert marcado.referencia == 1.0 and list(marcado.marcados.index) == ["e"]
    assert marcado.descartados.empty  # só marca, não tira
    em_reais = sind.analisar_indicador(serie, None, "caixa_aplicacoes", "mediana")
    assert em_reais.filtro is None and pd.isna(em_reais.referencia)
    assert sind.analisar_indicador(serie, None, "roe", "media_simples").aviso_referencia
