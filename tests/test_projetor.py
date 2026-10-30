import dataclasses
import datetime as dt

import pandas as pd
import pytest

from sintetico import historico_anual
from valuation.config import ConfigTerminal
from valuation.projecao import ErroProjecao
from valuation.projecao import premissas as pm
from valuation.projecao import projetor as pj
from valuation.projecao import sugestor as sg

DATA_BASE = dt.date(2026, 10, 30)
HISTORICO = pd.DataFrame({"receita_liquida": [900.0, 1000.0]}, index=pd.Index([2024, 2025]))

# Exemplo calculado à mão: receita 1.000 em 2025; crescimento 10% -> 4% e margem 30% -> 20% em 3
# anos; D&A 5%, capex 6%, NWC 10%, arrendamento 1% da receita; alíquota 30%.
PREMISSAS = pj.PremissasResolvidas(
    anos=(2026, 2027, 2028),
    crescimento=(0.10, 0.07, 0.04),
    margem_ebitda=(0.30, 0.25, 0.20),
    da_sobre_receita=0.05,
    capex_sobre_receita=0.06,
    nwc_sobre_receita=0.10,
    arrendamento_sobre_receita=0.01,
    aliquota=0.30,
    descontar_arrendamento=True,
    g_terminal=0.04,
)


def test_projecao_calculada_a_mao() -> None:
    t = pj.projetar(HISTORICO, PREMISSAS, data_base=DATA_BASE)
    assert list(t.index) == [2026, 2027, 2028]
    assert list(t.columns) == list(pj.COLUNAS_PROJECAO)
    a = t.loc[2026]
    assert a["fracao"] == pytest.approx(62 / 365)  # 30/10 a 31/12
    assert a["receita_liquida"] == pytest.approx(1100)
    assert a["ebitda"] == pytest.approx(330)
    assert a["da"] == pytest.approx(55)
    assert a["ebit"] == pytest.approx(275)
    assert a["imposto"] == pytest.approx(82.5)
    assert a["nopat"] == pytest.approx(192.5)
    assert a["capex"] == pytest.approx(66)
    assert a["delta_nwc"] == pytest.approx(10)  # 10% x (1.100 - 1.000)
    assert a["arrendamento"] == pytest.approx(11)
    assert a["fcff"] == pytest.approx(192.5 + 55 - 66 - 10 - 11)
    b = t.loc[2027]
    assert b["receita_liquida"] == pytest.approx(1177)
    assert b["nopat"] == pytest.approx(164.78)
    assert b["delta_nwc"] == pytest.approx(7.7)
    assert b["fcff"] == pytest.approx(133.54)
    c = t.loc[2028]
    assert c["fracao"] == 1
    assert c["receita_liquida"] == pytest.approx(1224.08)
    assert c["fcff"] == pytest.approx(99.3388)


def test_sem_desconto_de_arrendamento() -> None:
    premissas = dataclasses.replace(PREMISSAS, descontar_arrendamento=False)
    t = pj.projetar(HISTORICO, premissas, data_base=DATA_BASE)
    assert t.loc[2026, "fcff"] == pytest.approx(192.5 + 55 - 66 - 10)
    assert t.loc[2026, "arrendamento"] == pytest.approx(11)  # informado, mas fora do FCFF


def test_erros_de_projecao() -> None:
    with pytest.raises(ErroProjecao, match="começam em 2026"):
        pj.projetar(HISTORICO.loc[[2024]], PREMISSAS, data_base=DATA_BASE)
    with pytest.raises(ErroProjecao, match="não é positiva"):
        pj.projetar(HISTORICO * 0, PREMISSAS, data_base=DATA_BASE)
    with pytest.raises(ErroProjecao, match="vazio"):
        pj.projetar(HISTORICO.iloc[0:0], PREMISSAS, data_base=DATA_BASE)


@pytest.mark.parametrize(
    ("data_base", "ano_base", "horizonte", "esperado"),
    [
        (dt.date(2026, 10, 30), 2025, 3, (2026, 2027, 2028)),
        (dt.date(2026, 1, 1), 2025, 1, (2026,)),
        # 31/12: exercício encerrado; 2026 vira ponte (fração 0) e o horizonte começa em 2027.
        (dt.date(2026, 12, 31), 2025, 2, (2026, 2027, 2028)),
        # Fevereiro de 2027 sem a DFP de 2026 ainda: 2026 é ponte.
        (dt.date(2027, 2, 10), 2025, 2, (2026, 2027, 2028)),
    ],
)
def test_anos_projetados(
    data_base: dt.date, ano_base: int, horizonte: int, esperado: tuple[int, ...]
) -> None:
    assert pj.anos_projetados(ano_base, data_base, horizonte) == esperado


def test_anos_projetados_erros() -> None:
    with pytest.raises(ErroProjecao, match="não encerrado"):
        pj.anos_projetados(2026, DATA_BASE, 5)
    with pytest.raises(ErroProjecao, match="Horizonte"):
        pj.anos_projetados(2025, DATA_BASE, 0)


def test_fracao_restante() -> None:
    assert pj.fracao_restante(2025, DATA_BASE) == 0
    assert pj.fracao_restante(2026, DATA_BASE) == pytest.approx(62 / 365)
    assert pj.fracao_restante(2026, dt.date(2026, 12, 31)) == 0
    assert pj.fracao_restante(2027, DATA_BASE) == 1
    assert pj.fracao_restante(2028, dt.date(2028, 1, 1)) == 1  # 365 dias restantes no bissexto


def _sugestoes() -> sg.Sugestoes:
    h = historico_anual([0.10] * 9, [0.20] * 10)
    return sg.sugerir(
        h, g_terminal=sg.Sugestao(0.04, "teste"), aliquota_limite=0.34, commodity=False
    )


def test_resolver_sugerido_e_manual() -> None:
    s = _sugestoes()
    anos = (2026, 2027, 2028, 2029)
    base = pj.resolver(
        pm.ConfigProjecao(), s, anos=anos, aliquota_limite=0.34, descontar_arrendamento=True
    )
    assert base.crescimento == pytest.approx((0.10, 0.08, 0.06, 0.04))
    assert base.margem_ebitda == pytest.approx((0.20,) * 4)
    assert base.aliquota == pytest.approx(0.30)
    assert base.g_terminal == 0.04

    config = pm.ConfigProjecao.model_validate(
        {
            "receita": {"crescimento": [0.09, 0.08, 0.07, 0.06, 0.05]},
            "margens": {"ebitda": {"inicio": 0.25, "fim": "sugerido"}},
            "capex_sobre_receita": 0.12,
            "aliquota_imposto": {"valor": 0.20},
        }
    )
    manual = pj.resolver(config, s, anos=anos, aliquota_limite=0.34, descontar_arrendamento=False)
    assert manual.crescimento == (0.09, 0.08, 0.07, 0.06)  # lista mais longa é cortada
    assert manual.margem_ebitda == pytest.approx((0.25, 0.25 - 0.05 / 3, 0.25 - 0.10 / 3, 0.20))
    assert manual.capex_sobre_receita == 0.12
    assert manual.da_sobre_receita == pytest.approx(0.05)  # continua sugerido
    assert manual.aliquota == 0.20


def test_resolver_erros() -> None:
    s = _sugestoes()
    curta = pm.ConfigProjecao.model_validate({"receita": {"crescimento": [0.1]}})
    with pytest.raises(ErroProjecao, match="a lista tem 1 valores"):
        pj.resolver(curta, s, anos=(2026, 2027), aliquota_limite=0.34, descontar_arrendamento=True)
    with pytest.raises(ErroProjecao, match="histórico das sugestões vai até 2025"):
        pj.resolver(
            pm.ConfigProjecao(), s, anos=(2027,), aliquota_limite=0.34, descontar_arrendamento=True
        )
    alta = pm.ConfigProjecao.model_validate({"aliquota_imposto": {"valor": 0.40}})
    with pytest.raises(ErroProjecao, match="acima do limite"):
        pj.resolver(alta, s, anos=(2026,), aliquota_limite=0.34, descontar_arrendamento=True)


def test_cenarios() -> None:
    s = _sugestoes()
    deltas = pj.resolver_cenarios(
        pm.Cenarios.model_validate({"otimista": {"crescimento_pp": 0.03, "capex_pp": -0.001}}), s
    )
    assert deltas["base"] == pj.DeltaResolvido()
    pess, otim = deltas["pessimista"], deltas["otimista"]
    assert pess.crescimento == -s.delta_crescimento.valor
    assert pess.margem_ebitda == -s.delta_margem.valor
    assert pess.capex == s.delta_capex.valor
    assert otim == pj.DeltaResolvido(0.03, s.delta_margem.valor, -0.001)

    cenario = pj.aplicar_cenario(PREMISSAS, pj.DeltaResolvido(-0.02, -0.03, -0.10), "pessimista")
    assert cenario.crescimento == pytest.approx((0.08, 0.05, 0.02))
    assert cenario.margem_ebitda == pytest.approx((0.27, 0.22, 0.17))
    assert cenario.capex_sobre_receita == 0  # não fica negativo
    assert cenario.g_terminal == PREMISSAS.g_terminal
    assert cenario.cenario == "pessimista"


def test_g_terminal() -> None:
    config = ConfigTerminal(g_nominal_max=0.045, ronic="wacc", checagem_multiplo_saida=True)
    assert pj.g_terminal(pm.TerminalEmpresa(), config).valor == 0.045
    assert pj.g_terminal(pm.TerminalEmpresa(g_nominal=0.03), config).valor == 0.03
    with pytest.raises(ErroProjecao, match="acima do teto"):
        pj.g_terminal(pm.TerminalEmpresa(g_nominal=0.05), config)
