import statistics

import pandas as pd
import pytest

from sintetico import historico_anual
from valuation.projecao import ErroProjecao
from valuation.projecao import sugestor as sg

G = sg.Sugestao(0.04, "g terminal de teste")

# 2016-2025. Crescimento 2021-2025: 30%, 0%, 5%, 10%, 20% (mediana 10%).
CRESCIMENTO = [0.10, 0.10, 0.10, 0.10, 0.30, 0.00, 0.05, 0.10, 0.20]
# Margem: 16% em 2016-2020; 2021-2025: 20%, 22%, 18%, 20%, 21% (mediana 20%).
MARGEM = [0.16] * 5 + [0.20, 0.22, 0.18, 0.20, 0.21]
CAPEX = [0.06] * 5 + [0.08] * 5
ALIQUOTA = [0.30] * 5 + [0.25, 0.40, float("nan"), 0.20, 0.30]


def historico() -> pd.DataFrame:
    return historico_anual(CRESCIMENTO, MARGEM, capex=CAPEX, aliquota=ALIQUOTA)


def sugerir(h: pd.DataFrame | None = None, **kw: object) -> sg.Sugestoes:
    opcoes: dict[str, object] = {"g_terminal": G, "aliquota_limite": 0.34, "commodity": False}
    opcoes.update(kw)
    return sg.sugerir(historico() if h is None else h, **opcoes)  # type: ignore[arg-type]


def test_sugestoes_calculadas_a_mao() -> None:
    s = sugerir()
    assert s.ano_base == 2025
    assert s.crescimento_inicio.valor == pytest.approx(0.10)
    assert s.crescimento_fim is G
    assert s.margem_inicio.valor == pytest.approx(0.20)
    # Mediana de 10a = (0,16 + 0,18) / 2 = 0,17; fim = metade do caminho de 0,20 até 0,17.
    assert s.margem_fim.valor == pytest.approx(0.185)
    assert s.da_sobre_receita.valor == pytest.approx(0.05)
    assert s.capex_sobre_receita.valor == pytest.approx(0.08)
    assert s.nwc_sobre_receita.valor == pytest.approx(0.10)
    assert s.arrendamento_sobre_receita.valor == pytest.approx(0.01)
    assert s.aliquota.valor == pytest.approx(0.275)  # mediana de 0,25 0,40 0,20 0,30
    # Desvio do crescimento (8,7 p.p.) e o da margem (2,4 p.p.); capex: metade de 1,05 p.p.
    assert s.delta_crescimento.valor == 0.05  # teto
    assert s.delta_margem.valor == pytest.approx(statistics.stdev(MARGEM))
    assert s.delta_margem.valor == pytest.approx(0.024244, abs=1e-6)
    assert s.delta_capex.valor == pytest.approx(0.5 * statistics.stdev(CAPEX))
    assert "limitado a [1,00 p.p., 5,00 p.p.]" in s.delta_crescimento.origem
    assert "limitado" not in s.delta_margem.origem
    assert s.margem_inicio.origem == "mediana da margem EBITDA ajustada 2021-2025"
    assert s.avisos == ()


def test_estatisticas_do_resumo() -> None:
    e = sugerir().estatisticas
    receita = historico()["receita_liquida"]
    assert e.loc["mediana_5a", "crescimento"] == pytest.approx(0.10)
    assert e.loc["mediana_10a", "margem_ebitda_ajustada"] == pytest.approx(0.17)
    assert e.loc["ultimo", "crescimento"] == pytest.approx(0.20)
    assert e.loc["cagr_3a", "crescimento"] == pytest.approx(
        (receita[2025] / receita[2022]) ** (1 / 3) - 1
    )
    assert e.loc["cagr_10a", "crescimento"] != e.loc["cagr_10a", "crescimento"]  # NaN: sem 2015


def test_limites_do_crescimento_e_da_aliquota() -> None:
    alto = historico_anual([0.30] * 9, MARGEM, aliquota=0.40)
    s = sugerir(alto, aliquota_limite=0.34)
    assert s.crescimento_inicio.valor == 0.20
    assert "= 30,0%, limitada a [-5%, 20%]" in s.crescimento_inicio.origem
    assert s.aliquota.valor == 0.34
    assert s.delta_crescimento.valor == 0.01  # crescimento constante: desvio zero, vai ao piso
    queda = historico_anual([-0.20] * 9, MARGEM)
    assert sugerir(queda).crescimento_inicio.valor == -0.05


def test_sem_lair_positivo_usa_limite() -> None:
    s = sugerir(historico_anual(CRESCIMENTO, MARGEM, aliquota=float("nan")), aliquota_limite=0.3)
    assert s.aliquota.valor == 0.3
    assert "sem LAIR positivo" in s.aliquota.origem


def test_historico_curto_e_ano_faltante() -> None:
    curto = historico_anual([0.10], [0.20, 0.20], inicio=2024)
    s = sugerir(curto)
    assert s.crescimento_inicio.valor == pytest.approx(0.10)
    assert s.delta_crescimento.valor == 0.01  # piso: um só crescimento
    assert any("Histórico de 2 exercícios" in a for a in s.avisos)
    assert any("Histórico curto para o desvio-padrão" in a for a in s.avisos)

    com_buraco = historico().drop(index=2023)
    s = sugerir(com_buraco)
    assert any("ausentes no histórico: 2023" in a for a in s.avisos)
    # Sem 2023, os crescimentos de 2023 e 2024 somem: mediana de 30%, 0% e 20%.
    assert s.crescimento_inicio.valor == pytest.approx(0.20)


def test_commodity_avisa() -> None:
    s = sugerir(commodity=True, setor="mineracao")
    assert any("commodity (mineracao)" in a for a in s.avisos)


def test_historico_insuficiente() -> None:
    with pytest.raises(ErroProjecao, match="Só 1 exercício"):
        sugerir(historico().tail(1))
    with pytest.raises(ErroProjecao, match="vazio"):
        sugerir(historico().iloc[0:0])


def test_pct_e_pp() -> None:
    assert sg.pct(0.1234) == "12,3%"
    assert sg.pct(-0.0) == "0,0%"
    assert sg.pct(float("nan")) == "—"
    assert sg.pp(0.015) == "1,50 p.p."
