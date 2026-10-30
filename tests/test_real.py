import datetime as dt

import pandas as pd
import pytest

from valuation.saida import real

BASE = dt.date(2026, 1, 1)


def test_taxa_do_ano_usa_o_ultimo_focus_anterior() -> None:
    ipca = real.IpcaProjetado({2027: 0.04, 2030: 0.035}, ipca_12m=0.05)
    assert ipca.taxa(2026) == 0.05  # antes do Focus: IPCA de 12 meses
    assert ipca.taxa(2027) == 0.04
    assert ipca.taxa(2029) == 0.04  # lacuna: último anterior
    assert ipca.taxa(2040) == 0.035  # além do Focus: o último


def test_fator_acumulado_calculado_a_mao() -> None:
    ipca = real.IpcaProjetado({2026: 0.10, 2027: 0.05}, ipca_12m=0.0)
    assert real.fator_acumulado(BASE, 0, ipca) == 1.0
    assert real.fator_acumulado(BASE, 1, ipca) == pytest.approx(1.10)  # 365 dias de 2026
    assert real.fator_acumulado(BASE, 2, ipca) == pytest.approx(1.10 * 1.05)


def test_fator_acumulado_atravessa_a_virada_do_ano() -> None:
    ipca = real.IpcaProjetado({2026: 0.10, 2027: 0.05}, ipca_12m=0.0)
    base = dt.date(2026, 7, 2)
    d1 = (dt.date(2027, 1, 1) - base).days  # 183 dias em 2026
    esperado = 1.10 ** (d1 / 365) * 1.05 ** ((365 - d1) / 365)
    assert real.fator_acumulado(base, 1, ipca) == pytest.approx(esperado)


def test_fisher_real() -> None:
    assert real.fisher_real(0.155, 0.05) == pytest.approx(0.10)


def test_tabela_deflaciona_fluxos_e_valor_terminal() -> None:
    ipca = real.IpcaProjetado({2026: 0.10, 2027: 0.05}, ipca_12m=0.0)
    fluxos = pd.DataFrame(
        {"fluxo": [110.0, 231.0], "tau": [1.0, 2.0]}, index=pd.Index([2026, 2027], name="ano")
    )
    c = real.FluxosCenario(
        fluxos, valor_terminal=1155.0, taxa_desconto=0.155, g=0.05, valor_por_acao=9.0
    )
    t = real.tabela(BASE, ipca, {"base": c}).set_index(["item", "ano"], drop=False)
    assert list(t.columns) == list(real.COLUNAS)
    assert t.loc[("fluxo", 2026), "real"] == pytest.approx(100.0)
    assert t.loc[("fluxo", 2027), "real"] == pytest.approx(231 / 1.155)
    assert t.loc[("valor_terminal", 2027), "real"] == pytest.approx(1000.0)
    por_acao = t[t["item"] == "valor_por_acao"].iloc[0]
    assert por_acao["real"] == por_acao["nominal"] == 9.0
    taxa = t[t["item"] == "taxa_desconto"].iloc[0]
    assert taxa["real"] == pytest.approx(1.155 / 1.05 - 1)
    g = t[t["item"] == "g_terminal"].iloc[0]
    assert g["real"] == pytest.approx(1.05 / 1.05 - 1)
