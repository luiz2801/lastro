import dataclasses
import datetime as dt

import pandas as pd
import pytest

from valuation.modelos import ErroModelo, dcf
from valuation.modelos import ponte as pt
from valuation.projecao import projetor as pj

FIM_2025 = dt.date(2025, 12, 31)


def projecao(fracoes: tuple[float, ...] = (1.0, 1.0)) -> pd.DataFrame:
    """2026 e 2027: FCFF 100 e 110; NOPAT e EBITDA de 2027 = 120 e 200."""
    return pd.DataFrame(
        {
            "fracao": fracoes,
            "fcff": [100.0, 110.0],
            "nopat": [90.0, 120.0],
            "ebitda": [150.0, 200.0],
        },
        index=pd.Index([2026, 2027], name="ano"),
    )


def descontar(proj: pd.DataFrame, **kw: object) -> dcf.ResultadoDCF:
    args: dict[str, object] = {
        "wacc": 0.10,
        "g": 0.05,
        "ronic": "wacc",
        "data_base": FIM_2025,
        "meio_periodo": False,
        "alerta_tv_sobre_ev": 0.75,
    }
    return dcf.descontar(proj, **{**args, **kw})  # type: ignore[arg-type]


def test_dcf_calculado_a_mao_fim_de_periodo() -> None:
    r = descontar(projecao())
    assert list(r.fluxos["tau"]) == pytest.approx([1.0, 2.0])
    # 100 / 1,1 + 110 / 1,21 = 90,909 + 90,909
    assert r.vp_fluxos == pytest.approx(181.818181818)
    # NOPAT_T+1 = 126; reinvestimento = 5% / 10% = 50% => FCFF_T+1 = 63; VT = 63 / 5% = 1.260
    assert r.nopat_terminal == pytest.approx(126)
    assert r.fcff_terminal == pytest.approx(63)
    assert r.valor_terminal == pytest.approx(1260)
    assert r.vp_terminal == pytest.approx(1260 / 1.21)
    assert r.ev == pytest.approx(181.818181818 + 1041.322314)
    assert r.ev_ebitda_terminal == pytest.approx(6.3)
    assert r.tv_sobre_ev == pytest.approx(1041.322314 / 1223.140496)
    assert r.ronic == 0.10
    assert any("Valor terminal é 85%" in a for a in r.avisos)


def test_meio_periodo_e_ronic_numerico() -> None:
    r = descontar(projecao(), meio_periodo=True, ronic=0.20)
    assert list(r.fluxos["tau"]) == pytest.approx([0.5, 1.5])
    assert r.vp_fluxos == pytest.approx(100 / 1.1**0.5 + 110 / 1.1**1.5)
    # Reinvestimento = 5% / 20% = 25% => FCFF_T+1 = 126 x 0,75; VT descontado pelo tau de 2027.
    assert r.fcff_terminal == pytest.approx(94.5)
    assert r.vp_terminal == pytest.approx(94.5 / 0.05 / 1.1**1.5)
    assert descontar(projecao(), alerta_tv_sobre_ev=0.95).avisos == ()


def test_ano_corrente_parcial_e_ano_ponte() -> None:
    data_base = dt.date(2026, 10, 30)
    # 2026 tem 62 dias por vir (30/10 a 31/12): fluxo de 62/365 e tau no meio do trecho.
    r = descontar(projecao((62 / 365, 1.0)), data_base=data_base, meio_periodo=True)
    assert r.fluxos.loc[2026, "fluxo"] == pytest.approx(100 * 62 / 365)
    assert r.fluxos.loc[2026, "tau"] == pytest.approx(31 / 365)
    assert r.fluxos.loc[2027, "tau"] == pytest.approx((62 + 365) / 365 - 0.5)
    # Exercício encerrado sem DFP (fração 0) não entra no desconto.
    ponte_ = descontar(projecao((0.0, 1.0)), data_base=dt.date(2027, 2, 10))
    assert list(ponte_.fluxos.index) == [2027]


def test_erros_de_convergencia() -> None:
    with pytest.raises(ErroModelo, match="não converge"):
        descontar(projecao(), wacc=0.05)
    with pytest.raises(ErroModelo, match="RONIC"):
        descontar(projecao(), ronic=0.04)
    with pytest.raises(ErroModelo, match="nenhum ano"):
        descontar(projecao((0.0, 0.0)))


def test_avisos_de_nopat_e_ev_negativos() -> None:
    proj = projecao().assign(fcff=[-100.0, -100.0], nopat=[-10.0, -10.0], ebitda=[-5.0, -5.0])
    r = descontar(proj)
    assert r.ev < 0
    assert pd.isna(r.tv_sobre_ev)
    assert pd.isna(r.ev_ebitda_terminal)
    assert len(r.avisos) == 2


def test_resolver_ronic() -> None:
    assert dcf.resolver_ronic("wacc", roic_historico=None) == "wacc"
    assert dcf.resolver_ronic(0.12, roic_historico=None) == 0.12
    assert dcf.resolver_ronic("roic_historico", roic_historico=0.15) == 0.15
    for invalido in (None, float("nan"), -0.01):
        with pytest.raises(ErroModelo, match="ROIC"):
            dcf.resolver_ronic("roic_historico", roic_historico=invalido)


HISTORICO = pd.DataFrame({"receita_liquida": [1000.0]}, index=pd.Index([2025]))
PREMISSAS = pj.PremissasResolvidas(
    anos=(2026, 2027),
    crescimento=(0.10, 0.05),
    margem_ebitda=(0.30, 0.30),
    da_sobre_receita=0.05,
    capex_sobre_receita=0.05,
    nwc_sobre_receita=0.0,
    arrendamento_sobre_receita=0.0,
    aliquota=0.30,
    descontar_arrendamento=False,
    g_terminal=0.05,
)
ITENS = pt.ItensPonte(
    divida_bruta=300,
    caixa_e_aplicacoes=100,
    minoritarios=50,
    investimentos=20,
    divida_extra=10,
    acoes=100,
    data_balanco=dt.date(2025, 12, 31),
)


def test_avaliar_junta_projecao_desconto_e_ponte() -> None:
    dados = dcf.DadosAvaliacao(HISTORICO, ITENS, FIM_2025, False, 0.75)
    av = dcf.avaliar(PREMISSAS, dados, wacc=0.10, ronic="wacc")
    # 2026: receita 1.100, EBIT = 25% x 1.100 = 275, NOPAT 192,5, FCFF = NOPAT + D&A - capex.
    # 2027: receita 1.155, NOPAT 202,125. NOPAT_T+1 x (1 - 50%) / 5%.
    vp = 192.5 / 1.1 + 202.125 / 1.21 + 202.125 * 1.05 * 0.5 / 0.05 / 1.21
    assert av.dcf.ev == pytest.approx(vp)
    assert av.ponte.equity == pytest.approx(vp - 240)
    assert av.valor_por_acao == pytest.approx((vp - 240) / 100)
    tabela = dcf.tabela(av)
    assert list(tabela["ano"]) == [2026, 2027]
    assert {"tau", "fator", "vp", "fcff"} <= set(tabela.columns)

    em_dolar = dataclasses.replace(dados, cambio=5.0)
    assert dcf.avaliar(PREMISSAS, em_dolar, wacc=0.10, ronic="wacc").valor_por_acao == (
        pytest.approx(5 * (vp - 240) / 100)
    )


def test_ponte_calculada_a_mao() -> None:
    r = pt.ponte(1000, ITENS)
    # 1.000 - 300 + 100 - 50 + 20 - 10
    assert r.equity == 760
    assert r.valor_por_acao == pytest.approx(7.6)
    t = pt.tabela(r).set_index("item")["valor"]
    assert t["divida_bruta"] == -300
    assert t["equity"] == 760
    assert t.drop(["equity", "acoes", "valor_por_acao"]).sum() == 760


def test_itens_do_balanco() -> None:
    balanco = pd.Series(
        {
            "divida_bruta": 300.0,
            "caixa_e_aplicacoes": 100.0,
            "minoritarios": 50.0,
            "investimentos": 20.0,
            "divida_extra": float("nan"),
        }
    )
    kw = {"acoes": 100, "data_balanco": FIM_2025, "minoritarios": "contabil"}
    itens = pt.itens_do_balanco(balanco, coligadas="somar_investimento_contabil", **kw)  # type: ignore[arg-type]
    assert itens == dataclasses.replace(ITENS, divida_extra=0.0)
    no_ebit = pt.itens_do_balanco(balanco, coligadas="manter_no_ebit", **kw)  # type: ignore[arg-type]
    assert no_ebit.investimentos == 0
    with pytest.raises(ErroModelo, match="Fase 8"):
        pt.itens_do_balanco(
            balanco,
            acoes=100,
            data_balanco=FIM_2025,
            coligadas="manter_no_ebit",
            minoritarios="multiplo_pvp",
        )
    with pytest.raises(ErroModelo, match="ações"):
        pt.itens_do_balanco(
            balanco,
            acoes=0,
            data_balanco=FIM_2025,
            coligadas="manter_no_ebit",
            minoritarios="contabil",
        )
