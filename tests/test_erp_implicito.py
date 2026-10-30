import pytest

from valuation.custo_capital import ErroCustoCapital
from valuation.custo_capital import erp_implicito as erp


def test_crescimento_nominal_fisher() -> None:
    assert erp.crescimento_nominal(0.02, 0.04) == pytest.approx(1.02 * 1.04 - 1)


def test_trajetoria_usa_focus_e_cai_no_g_perpetuo_depois() -> None:
    pib = {2026: 0.02, 2027: 0.01}
    ipca = {2026: 0.05, 2027: 0.04, 2028: 0.03}  # 2028 sem PIB: não conta como Focus
    t = erp.trajetoria(2026, 4, pib, ipca, 0.045)
    assert t == pytest.approx((1.02 * 1.05 - 1, 1.01 * 1.04 - 1, 0.045, 0.045))


def test_gordon_quando_nao_ha_fase_explicita() -> None:
    # Sem anos explícitos: P0 = FC0 x (1 + g) / (ke - g) => ke = FC0 x (1 + g) / P0 + g.
    r = erp.resolver(1000.0, 60.0, [], 0.04, rf=0.10)
    assert r.ke == pytest.approx(60.0 * 1.04 / 1000.0 + 0.04)
    assert r.erp == pytest.approx(r.ke - 0.10)


def test_crescimento_constante_igual_ao_g_e_gordon() -> None:
    # Se o Focus e o g perpétuo coincidem, o valor é o de Gordon, qualquer que seja N.
    r = erp.resolver(1000.0, 60.0, [0.04] * 5, 0.04, rf=0.10)
    assert r.ke == pytest.approx(60.0 * 1.04 / 1000.0 + 0.04, abs=1e-8)


def test_um_ano_explicito_calculado_a_mao() -> None:
    # P0 = FC1/(1+ke) + FC1 x (1+g)/(ke-g)/(1+ke), FC1 = 100 x 1,10 = 110; g = 4%.
    # Com ke = 12%: 110/1,12 + 110 x 1,04/0,08/1,12 = 98,2143 + 1276,7857 = 1375,0.
    r = erp.resolver(1375.0, 100.0, [0.10], 0.04, rf=0.0)
    assert r.ke == pytest.approx(0.12, abs=1e-7)
    assert erp.valor_presente(0.12, 100.0, [0.10], 0.04) == pytest.approx(1375.0)


def test_valor_maior_reduz_o_ke() -> None:
    barato = erp.resolver(800.0, 60.0, [0.05] * 5, 0.04, rf=0.10)
    caro = erp.resolver(1200.0, 60.0, [0.05] * 5, 0.04, rf=0.10)
    assert barato.ke > caro.ke


def test_entradas_invalidas_e_sem_solucao() -> None:
    with pytest.raises(ErroCustoCapital, match="positivos"):
        erp.resolver(1000.0, 0.0, [0.05], 0.04, rf=0.1)
    with pytest.raises(ErroCustoCapital, match="não é maior"):
        erp.valor_presente(0.04, 60.0, [0.05], 0.04)
    with pytest.raises(ErroCustoCapital, match="sem solução"):
        erp.resolver(1e12, 1.0, [0.05], 0.04, rf=0.1)  # valor altíssimo: ke abaixo de g + folga


def _faixa(**extra: object) -> erp.FaixaErp:
    args: dict[str, object] = {
        "ano_inicial": 2026,
        "anos": 5,
        "pib_real": {2026: 0.02, 2027: 0.02},
        "ipca": {2026: 0.04, 2027: 0.04},
        "g_perpetuo": 0.04,
        "faixa_g": 0.01,
        "rf": 0.10,
    }
    args.update(extra)
    return erp.faixa(1000.0, 60.0, **args)  # type: ignore[arg-type]


def test_faixa_ordena_limites_e_avisa_recompras() -> None:
    f = _faixa()
    assert f.inferior.erp < f.central.erp < f.superior.erp
    assert f.central.crescimentos[0] == pytest.approx(1.02 * 1.04 - 1)
    assert f.central.crescimentos[-1] == pytest.approx(0.04)
    assert any("recompras" in a for a in f.avisos)


def test_faixa_sem_recompras_e_com_cobertura_baixa() -> None:
    f = _faixa(recompras_ignoradas=False, cobertura=0.5)
    assert not any("recompras" in a for a in f.avisos)
    assert any("50%" in a for a in f.avisos)


def test_erp_fora_do_limite_falha_e_fora_do_aviso_avisa() -> None:
    negativo = _faixa(rf=0.30)
    assert negativo.erro is not None and "fora de [0%, 15%]" in negativo.erro
    assert negativo.central.erp < 0  # os números continuam disponíveis
    assert _faixa().erro is None
    ke = _faixa(rf=0.0).central.ke
    f = _faixa(rf=ke - 0.005)  # ERP de 0,5%: dentro do limite, mas suspeito
    assert any("fora de [2%, 10%]" in a for a in f.avisos)


def test_piso_do_g_inferior_em_zero() -> None:
    f = _faixa(g_perpetuo=0.005, rf=0.03)
    assert f.inferior.g_perpetuo == 0.0


def test_cagr_agregado_soma_so_quem_tem_as_duas_pontas() -> None:
    series = [
        {2020: 100.0, 2025: 200.0},
        {2020: 50.0, 2025: 50.0},
        {2025: 999.0},  # sem a ponta inicial: fora
        {2020: 10.0, 2025: 0.0},  # dividendo zero na ponta final: fora
    ]
    cagr, n = erp.cagr_agregado(series, 2025, 5)
    assert n == 2
    assert cagr == pytest.approx((250 / 150) ** (1 / 5) - 1)


def test_cagr_agregado_sem_series_validas_falha() -> None:
    with pytest.raises(ErroCustoCapital, match="Nenhuma série"):
        erp.cagr_agregado([{2025: 1.0}], 2025, 5)


def test_ultimo_ano_comum_exige_metade_das_series() -> None:
    series = [{2024: 1.0, 2025: 1.0}, {2024: 1.0, 2025: 1.0}, {2024: 1.0}, {2024: 1.0}]
    assert erp.ultimo_ano_comum(series) == 2025  # 2 de 4 = 50%
    assert erp.ultimo_ano_comum(series, minimo=0.75) == 2024
    with pytest.raises(ErroCustoCapital, match="insuficientes"):
        erp.ultimo_ano_comum([{2025: 0.0}])
