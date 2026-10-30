import pytest

from test_dcf import FIM_2025, HISTORICO, ITENS, PREMISSAS
from valuation.analise import cenarios as cen
from valuation.custo_capital import beta as bt
from valuation.custo_capital import capm
from valuation.custo_capital import kd as kd_mod
from valuation.custo_capital import wacc as wc
from valuation.modelos import ErroModelo, dcf
from valuation.perfil.parametros import ParametrosPerfil
from valuation.projecao import projetor as pj

DADOS = dcf.DadosAvaliacao(HISTORICO, ITENS, FIM_2025, False, 0.75)
DELTAS = {
    "pessimista": pj.DeltaResolvido(crescimento=-0.02, margem_ebitda=-0.05, capex=0.01),
    "base": pj.DeltaResolvido(),
    "otimista": pj.DeltaResolvido(crescimento=0.02, margem_ebitda=0.05, capex=-0.01),
}
PERFIL = ParametrosPerfil("moderado", 0.20, 0.25, 0.50, 0.25, 7, 0.05)


def custo_capital(ke: float = 0.12, kd: float = 0.10, peso_divida: float = 0.25) -> wc.CustoCapital:
    est = wc.Estrutura("manual", 25.0, 75.0, peso_divida)
    return wc.montar(
        data_base=FIM_2025,
        beta=bt.manual(1.0),
        ke=capm.CustoCapitalProprio("brl_direto", "BRL", ke, 1.0, 0.05, 0.07),
        kd=kd_mod.manual(kd),
        aliquota=0.34,
        estrutura=est,
        data_balanco=FIM_2025,
    )


def test_pesos_e_ponderacao() -> None:
    p = cen.pesos(PERFIL, pj.CENARIOS)
    assert p == {"pessimista": 0.25, "base": 0.5, "otimista": 0.25}
    assert cen.ponderar({"pessimista": 10, "base": 20, "otimista": 40}, p) == 22.5
    assert cen.pesos(PERFIL, ("otimista",)) == {"otimista": 1.0}
    with pytest.raises(ErroModelo, match="três cenários"):
        cen.pesos(PERFIL, ("base", "otimista"))


def test_taxa_implicita() -> None:
    # 1 / x = 8  =>  x = 12,5%
    assert cen.taxa_implicita(lambda x: 1 / x, 8, minimo=0.01) == pytest.approx(0.125)
    # 1 / x = 0,5 => x = 200%, fora de [1%, 100%]
    assert cen.taxa_implicita(lambda x: 1 / x, 0.5, minimo=0.01) is None
    assert cen.taxa_implicita(lambda x: 1 / x, 10, minimo=0.1) == 0.1


def test_analisar_pondera_e_acha_taxas_implicitas() -> None:
    cc = custo_capital()
    r = cen.analisar(
        PREMISSAS,
        DELTAS,
        DADOS,
        custo_capital=cc,
        ronic="wacc",
        perfil=PERFIL,
        preco=10.0,
        selic=0.15,
    )
    valores = {c: av.valor_por_acao for c, av in r.avaliacoes.items()}
    assert valores["pessimista"] < valores["base"] < valores["otimista"]
    assert r.valor_ponderado == pytest.approx(
        0.25 * valores["pessimista"] + 0.5 * valores["base"] + 0.25 * valores["otimista"]
    )
    assert r.preco_maximo_compra == pytest.approx(0.8 * r.valor_ponderado)
    assert r.upside == pytest.approx(r.valor_ponderado / 10 - 1)
    assert r.hurdle == pytest.approx(0.20)

    def ponderado(wacc: float) -> float:
        por = cen.avaliar_cenarios(PREMISSAS, DELTAS, DADOS, wacc=wacc, ronic="wacc")
        return cen.ponderar({c: av.valor_por_acao for c, av in por.items()}, r.pesos)

    assert r.wacc_implicito is not None
    assert ponderado(r.wacc_implicito) == pytest.approx(10.0, rel=1e-5)
    assert r.ke_implicito is not None
    wacc_do_ke = wc.wacc(r.ke_implicito, 0.10, 0.34, 0.25)
    assert ponderado(wacc_do_ke) == pytest.approx(10.0, rel=1e-5)
    assert r.preco < r.preco_maximo_compra
    assert "R$ 10,00; abaixo do preço máximo" in cen.mensagem(r, "XPTO3")


def test_analisar_um_cenario_e_preco_inalcancavel() -> None:
    r = cen.analisar(
        PREMISSAS,
        DELTAS,
        DADOS,
        custo_capital=custo_capital(),
        ronic="wacc",
        perfil=PERFIL,
        preco=0.01,
        selic=0.15,
        cenarios=("base",),
    )
    assert list(r.avaliacoes) == ["base"]
    assert r.valor_ponderado == r.avaliacoes["base"].valor_por_acao
    # Nem 100% a.a. leva o valor a R$ 0,01: sem solução, com aviso.
    assert r.ke_implicito is None
    assert any("sem solução" in a for a in r.avisos)
    assert "R$ 0,01; abaixo" in cen.mensagem(r, "XPTO3")
    caro = cen.ResultadoCenarios(**{**r.__dict__, "preco": 1e6})
    assert "acima do preço máximo" in cen.mensagem(caro, "XPTO3")
    with pytest.raises(ErroModelo, match="Preço"):
        cen.analisar(
            PREMISSAS,
            DELTAS,
            DADOS,
            custo_capital=custo_capital(),
            ronic="wacc",
            perfil=PERFIL,
            preco=0,
            selic=0.15,
        )
