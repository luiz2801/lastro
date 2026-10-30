"""DDM em dois estágios, lucro residual, cenários e sensibilidade das financeiras."""

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from valuation.analise import cenarios as cen
from valuation.analise import sensibilidade as sens
from valuation.custo_capital import beta as bt
from valuation.custo_capital import wacc as wc
from valuation.custo_capital.capm import custo_capital_proprio
from valuation.modelos import ErroModelo, ddm
from valuation.perfil.parametros import ParametrosPerfil
from valuation.projecao import financeira as pf

# Data-base no fim do ano: dois anos inteiros por vir e tau = 1 e 2 (o caso da fórmula do guia).
BASE = dt.date(2025, 12, 31)
PREMISSAS = pf.PremissasFinanceiras(
    anos=(2026, 2027), roe=(0.20, 0.20), payout_inicio=0.5, g_terminal=0.05
)
DADOS = ddm.DadosDDM(
    pl_inicial=100.0,
    acoes=10.0,
    data_balanco=BASE,
    data_base=BASE,
    alerta_vt_sobre_valor=0.9,  # com 2 anos explícitos o terminal é ~86% do valor
)


def tau(ano: int, base: dt.date = BASE) -> float:
    return (dt.date(ano, 12, 31) - base).days / 365


def test_ddm_calculado_a_mao() -> None:
    av = ddm.avaliar(PREMISSAS, DADOS, ke=0.15)
    r = av.ddm
    # 2026: lucro 20, payout 0,5 => dividendos 10, PL 110. 2027: payout 1 - 0,05/0,2 = 0,75,
    # lucro 22, dividendos 16,5, PL 115,5. Terminal: P/VP = (0,2 - 0,05) / (0,15 - 0,05) = 1,5.
    d1, d2 = (1.15) ** -tau(2026), (1.15) ** -tau(2027)
    assert r.fluxos["dividendos"].tolist() == pytest.approx([10.0, 16.5])
    assert r.pvp_justificado == pytest.approx(1.5)
    assert r.pl_final == pytest.approx(115.5)
    assert r.vp_dividendos == pytest.approx(10 * d1 + 16.5 * d2)
    assert r.vp_terminal == pytest.approx(1.5 * 115.5 * d2)
    assert av.valor_por_acao == pytest.approx((10 * d1 + 16.5 * d2 + 173.25 * d2) / 10)
    # Lucro residual: PL_0 + (20 - c1 x 100) d1 + (22 - c2 x 110) d2 + d2 x 115,5 x 0,05 / 0,10.
    c1, c2 = 1 / d1 - 1, d1 / d2 - 1
    residual = 100 + (20 - c1 * 100) * d1 + (22 - c2 * 110) * d2 + d2 * 115.5 * 0.5
    assert r.valor_lucro_residual == pytest.approx(residual)
    assert r.divergencia == pytest.approx(0.0, abs=1e-12)
    assert r.avisos == ()
    assert r.pvp_implicito == pytest.approx(r.valor / 100)
    assert list(ddm.tabela(av).columns[:2]) == ["ano", "fracao"]


def test_ano_parcial_e_lucro_residual_coincidem() -> None:
    base = dt.date(2026, 10, 30)
    premissas = pf.PremissasFinanceiras(
        anos=(2026, 2027, 2028), roe=(0.21, 0.2, 0.19), payout_inicio=0.3, g_terminal=0.05
    )
    dados = ddm.DadosDDM(217.0, 10.0, dt.date(2026, 6, 30), base, 0.75)
    r = ddm.avaliar(premissas, dados, ke=0.2).ddm
    fracao = (dt.date(2026, 12, 31) - base).days / 365
    assert r.fluxos["tau"].tolist() == pytest.approx([tau(a, base) for a in (2026, 2027, 2028)])
    assert r.fluxos["tau"].iloc[0] == pytest.approx(fracao)
    assert r.fluxos.loc[2026, "dividendos"] == pytest.approx(0.3 * 0.21 * 217 * fracao)
    assert r.divergencia == pytest.approx(0.0, abs=1e-12)
    assert any("abaixo do Ke" in a for a in r.avisos)  # ROE_LP 19% < Ke 20%


def test_erros_e_avisos() -> None:
    with pytest.raises(ErroModelo, match="não é maior que o g"):
        ddm.avaliar(PREMISSAS, DADOS, ke=0.05)
    with pytest.raises(ErroModelo, match="não supera o g"):
        ddm.avaliar(pf.PremissasFinanceiras((2026,), (0.04,), 0.5, 0.05), DADOS, ke=0.15)
    with pytest.raises(ErroModelo, match="ações"):
        ddm.avaliar(PREMISSAS, ddm.DadosDDM(100, 0, BASE, BASE, 0.75), ke=0.15)
    longo = pf.PremissasFinanceiras((2026,), (0.30,), 0.0, 0.05)
    avisos = ddm.avaliar(longo, DADOS, ke=0.10).avisos
    assert any("Valor terminal é" in a for a in avisos)


def test_valor_cai_com_ke_e_sobe_com_roe() -> None:
    valores = [ddm.avaliar(PREMISSAS, DADOS, ke=k).valor_por_acao for k in (0.12, 0.15, 0.2)]
    assert valores == sorted(valores, reverse=True)
    roes = [
        ddm.avaliar(pf.aplicar_cenario(PREMISSAS, d, "base"), DADOS, ke=0.15).valor_por_acao
        for d in (-0.02, 0.0, 0.02)
    ]
    assert roes == sorted(roes)


PERFIL = ParametrosPerfil(
    perfil="moderado",
    margem_seguranca=0.2,
    peso_pessimista=0.25,
    peso_base=0.5,
    peso_otimista=0.25,
    horizonte_anos=7,
    hurdle_spread_selic=0.05,
)
DELTAS = {"pessimista": -0.02, "base": 0.0, "otimista": 0.02}


def test_analisar_ddm_e_ke_implicito() -> None:
    r = cen.analisar_ddm(PREMISSAS, DELTAS, DADOS, ke=0.15, perfil=PERFIL, preco=15.0, selic=0.15)
    valores = {c: av.valor_por_acao for c, av in r.avaliacoes.items()}
    assert r.valor_ponderado == pytest.approx(
        0.25 * valores["pessimista"] + 0.5 * valores["base"] + 0.25 * valores["otimista"]
    )
    assert r.preco_maximo_compra == pytest.approx(0.8 * r.valor_ponderado)
    assert r.hurdle == pytest.approx(0.20)
    assert r.wacc_implicito is None
    assert r.ke_implicito is not None
    no_ke = cen.avaliar_cenarios_ddm(PREMISSAS, DELTAS, DADOS, ke=r.ke_implicito)
    assert cen.ponderar({c: a.valor_por_acao for c, a in no_ke.items()}, r.pesos) == (
        pytest.approx(15.0, rel=1e-6)
    )
    so_base = cen.analisar_ddm(
        PREMISSAS,
        DELTAS,
        DADOS,
        ke=0.15,
        perfil=PERFIL,
        preco=15.0,
        selic=0.15,
        cenarios=("base",),
    )
    assert so_base.valor_ponderado == pytest.approx(valores["base"])
    assert "abaixo do preço máximo" in cen.mensagem(
        cen.analisar_ddm(PREMISSAS, DELTAS, DADOS, ke=0.15, perfil=PERFIL, preco=1.0, selic=0.15),
        "BANC4",
    )
    with pytest.raises(ErroModelo, match="Preço"):
        cen.analisar_ddm(PREMISSAS, DELTAS, DADOS, ke=0.15, perfil=PERFIL, preco=0, selic=0.15)


def test_sensibilidade_ddm() -> None:
    base = ddm.avaliar(PREMISSAS, DADOS, ke=0.15).valor_por_acao
    ke_g = sens.ke_x_g(
        PREMISSAS, DADOS, ke=0.15, passo_ke=0.05, faixa_ke=0.10, passo_g=0.05, faixa_g=0.05
    )
    assert ke_g.shape == (5, 3)
    assert ke_g.loc[0.15, 0.05] == pytest.approx(base)
    assert np.isnan(ke_g.loc[0.05, 0.05]) and np.isnan(ke_g.loc[0.05, 0.1])
    assert ke_g.loc[0.2, 0.05] < base
    roe_ke = sens.roe_x_ke(
        PREMISSAS, DADOS, ke=0.15, passo_roe=0.01, faixa_roe=0.02, passo_ke=0.01, faixa_ke=0.01
    )
    assert list(roe_ke.index) == pytest.approx([0.18, 0.19, 0.2, 0.21, 0.22])
    assert roe_ke.loc[0.2, 0.15] == pytest.approx(base)
    assert roe_ke[0.15].is_monotonic_increasing
    rampa = sens.rampa_roe(PREMISSAS, 0.02)
    assert rampa.roe == pytest.approx((0.20, 0.22))


def test_tabela_financeira() -> None:
    beta = bt.manual(1.1)
    ke = custo_capital_proprio(
        metodo="brl_direto",
        moeda="BRL",
        beta=1.1,
        erp=0.05,
        rf_brl=0.13,
        rf_usd=0.04,
        crp=0.0,
        inflacao_usd=0.02,
        inflacao_brl=None,
    )
    cc = wc.montar_financeira(data_base=BASE, beta=beta, ke=ke, data_balanco=BASE, avisos=("x",))
    tab = wc.tabela_financeira(cc).set_index("componente")
    assert tab.loc["ke", "valor"] == pytest.approx(0.13 + 1.1 * 0.05)
    assert "wacc" not in tab.index and "kd" not in tab.index
    assert tab.loc["aviso", "detalhe"] == "x"
    assert pd.api.types.is_float_dtype(tab["valor"])
