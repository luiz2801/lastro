import pandas as pd
import pytest

from sintetico import ano, contas_padronizadas, saldo, ytd
from valuation.contabil import ErroContabil
from valuation.contabil import nao_financeiras as nf

# Dois exercícios calculados à mão. Arrendamento: 10 (CP) e 40 (LP) dentro de empréstimos, mais
# 5 (LP) em "outras obrigações" em 2025.
ANUAL = pd.DataFrame(
    {
        "receita_liquida": [1000.0, 1200.0],
        "ebit": [200.0, 260.0],
        "da": [50.0, 60.0],
        "equivalencia_patrimonial": [3.0, 5.0],
        "lair": [180.0, 240.0],
        "ir_csll": [-54.0, -96.0],
        "lucro_liquido": [126.0, 144.0],
        "lucro_liquido_controladora": [120.0, 140.0],
        "cfo": [230.0, 250.0],
        "capex": [-80.0, -90.0],
        "pagamento_arrendamento": [-10.0, -12.0],
        "dividendos_pagos": [-40.0, -50.0],
        "ativo_circulante": [400.0, 450.0],
        "caixa": [100.0, 110.0],
        "aplicacoes_financeiras": [20.0, 30.0],
        "passivo_circulante": [250.0, 280.0],
        "emprestimos_cp": [60.0, 70.0],
        "arrendamento_cp_em_emprestimos": [10.0, 10.0],
        "emprestimos_lp": [300.0, 320.0],
        "arrendamento_lp_em_emprestimos": [40.0, 40.0],
        "arrendamento_lp_outros": [float("nan"), 5.0],
        "patrimonio_liquido_total": [500.0, 550.0],
        "minoritarios": [30.0, 35.0],
    },
    index=pd.Index([2024, 2025], name="ano"),
)


def test_metricas_calculadas_a_mao() -> None:
    m = nf.metricas(ANUAL, aliquota_nominal=0.34).loc[2025]
    assert m["ebitda"] == 320
    assert m["ebit_ajustado"] == 255  # sem a equivalência
    assert m["aliquota_efetiva"] == pytest.approx(0.40)
    assert m["aliquota_operacional"] == pytest.approx(0.34)  # limitada à nominal
    assert m["nopat"] == pytest.approx(255 * 0.66)
    assert m["capex"] == 90
    assert m["divida_financeira"] == (70 - 10) + (320 - 40)
    assert m["arrendamento"] == 10 + 40 + 5
    assert m["divida_bruta"] == 340 + 55
    assert m["caixa_e_aplicacoes"] == 140
    assert m["divida_liquida"] == 395 - 140
    # NWC = (AC - caixa - aplic.) - (PC - dívida CP - arrendamento CP)
    nwc_2024 = (400 - 120) - (250 - 50 - 10)
    nwc_2025 = (450 - 140) - (280 - 60 - 10)
    assert m["nwc"] == nwc_2025
    assert m["delta_nwc"] == nwc_2025 - nwc_2024
    assert m["fcff"] == pytest.approx(255 * 0.66 + 60 - 90 - (nwc_2025 - nwc_2024) - 12)
    capital_2024 = 500 + (50 + 260 + 50 - 120)
    capital_2025 = 550 + 255
    assert m["roic"] == pytest.approx(255 * 0.66 / ((capital_2024 + capital_2025) / 2))
    assert m["dividendos_pagos"] == 50
    assert m["fcf_caixa"] == 250 - 90


def test_primeiro_ano_sem_delta_nwc_nem_roic() -> None:
    m = nf.metricas(ANUAL, aliquota_nominal=0.34).loc[2024]
    assert pd.isna(m["delta_nwc"]) and pd.isna(m["fcff"]) and pd.isna(m["roic"])
    assert m["aliquota_operacional"] == pytest.approx(0.30)
    assert m["arrendamento"] == 50  # "outros" ausente conta como zero


def test_ajustes() -> None:
    aj = nf.AjustesContabeis(
        ifrs16="ignorar",
        capex_equivalente_arrendamento=False,
        coligadas="manter_no_ebit",
        nao_recorrentes=(nf.NaoRecorrente(ano=2025, valor=-40.0, descricao="impairment"),),
    )
    m = nf.metricas(ANUAL, aliquota_nominal=0.34, ajustes=aj).loc[2025]
    assert m["ebit_ajustado"] == 260 + 40
    assert m["ebitda_ajustado"] == 300 + 60
    assert m["divida_bruta"] == m["divida_financeira"]
    sem_arrendamento = nf.metricas(ANUAL, aliquota_nominal=0.34).loc[2025]
    # EBIT ajustado +45 (40 do impairment devolvido + 5 da equivalência mantida) e sem
    # descontar os 12 de arrendamento.
    assert m["fcff"] - sem_arrendamento["fcff"] == pytest.approx(45 * 0.66 + 12)


def test_prejuizo_usa_aliquota_nominal() -> None:
    largo = ANUAL.copy()
    largo.loc[2025, ["lair", "ir_csll"]] = [-10.0, 5.0]
    m = nf.metricas(largo, aliquota_nominal=0.34).loc[2025]
    assert pd.isna(m["aliquota_efetiva"])
    assert m["aliquota_operacional"] == 0.34


def test_conta_obrigatoria_ausente() -> None:
    with pytest.raises(ErroContabil, match="receita_liquida"):
        nf.metricas(ANUAL.drop(columns="receita_liquida"), aliquota_nominal=0.34)


def test_metricas_ltm_compara_com_balanco_de_um_ano_antes() -> None:
    fluxos = {
        "receita_liquida": (100, 60, 50),
        "ebit": (20, 12, 10),
        "da": (5, 3, 2),
        "lair": (18, 11, 9),
        "ir_csll": (-6, -3, -3),
        "lucro_liquido": (12, 8, 6),
        "lucro_liquido_controladora": (12, 8, 6),
        "cfo": (22, 13, 11),
        "capex": (-8, -5, -4),
    }
    registros = []
    for conta, (a25, s26, s25) in fluxos.items():
        registros += [
            ano(conta, 2025, a25),
            ytd(conta, "2026-06-30", s26),
            ytd(conta, "2025-06-30", s25),
        ]
    saldos = {
        "ativo_circulante": (40, 50),
        "caixa": (10, 12),
        "passivo_circulante": (20, 22),
        "emprestimos_cp": (5, 5),
        "emprestimos_lp": (30, 28),
        "patrimonio_liquido_total": (60, 70),
    }
    for conta, (antes, agora) in saldos.items():
        registros += [saldo(conta, "2025-06-30", antes), saldo(conta, "2026-06-30", agora)]
    contas = contas_padronizadas(registros)
    m = nf.metricas_ltm(contas, aliquota_nominal=0.34)
    assert m["receita_liquida"] == 110
    assert m["ebitda"] == 22 + 6
    assert m["delta_nwc"] == ((50 - 12) - (22 - 5)) - ((40 - 10) - (20 - 5))
    assert m["divida_liquida"] == 33 - 12
    sem_balanco_anterior = contas[
        ~((contas["periodicidade"] == "S") & (contas["dt_fim"] == pd.Timestamp("2025-06-30")))
    ]
    with pytest.raises(ErroContabil, match="ΔNWC"):
        nf.metricas_ltm(sem_balanco_anterior, aliquota_nominal=0.34)


def test_caixa_extra_e_divida_extra() -> None:
    largo = ANUAL.assign(aplicacoes_financeiras_lp=[7.0, 8.0], provisoes_lp=[float("nan"), 25.0])
    ajustes = nf.AjustesContabeis(
        caixa_extra=("aplicacoes_financeiras_lp",), divida_extra=("provisoes_lp",)
    )
    base = nf.metricas(ANUAL, aliquota_nominal=0.34).loc[2025]
    m = nf.metricas(largo, aliquota_nominal=0.34, ajustes=ajustes)
    assert m.loc[2025, "caixa_e_aplicacoes"] == 140 + 8
    assert m.loc[2025, "divida_liquida"] == base["divida_liquida"] - 8
    assert m.loc[2025, "nwc"] == base["nwc"]  # caixa extra não sai do capital de giro
    assert list(m["divida_extra"]) == [0.0, 25.0]
    assert base["caixa_extra"] == 0 and base["divida_extra"] == 0


def test_caixa_extra_conta_inexistente() -> None:
    with pytest.raises(ErroContabil, match="caixa_extra: conta 'nao_existe'"):
        nf.metricas(
            ANUAL, aliquota_nominal=0.34, ajustes=nf.AjustesContabeis(caixa_extra=("nao_existe",))
        )
