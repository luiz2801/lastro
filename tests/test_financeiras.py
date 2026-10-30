"""Plano de contas `financeira`, métricas de financeiras e QA (ADR 0011)."""

import numpy as np
import pandas as pd
import pytest

from sintetico import contas_padronizadas, dfp_banco, documento, juntar, saldo, ytd
from valuation.contabil import ErroContabil, qa
from valuation.contabil import financeiras as fin
from valuation.contabil import padronizacao as pad
from valuation.contabil import periodos as per

PLANO = pad.carregar_mapeamento(tipo="financeira")


def _padronizar(demonstracoes: pd.DataFrame, consolidado: bool = True) -> pd.DataFrame:
    selecionadas = pad.selecionar_reapresentacoes(demonstracoes, consolidado=consolidado)
    return pad.padronizar(selecionadas, PLANO, ticker="BANC4")


def test_plano_financeiro_carrega() -> None:
    assert set(PLANO.criticas) <= set(PLANO.contas)
    assert PLANO.eh_saldo("patrimonio_liquido_total")
    assert not PLANO.eh_saldo("lucro_liquido_controladora")


def test_mapeia_plano_antigo_de_bancos() -> None:
    anual = per.anual(_padronizar(dfp_banco(2025)))
    linha = anual.loc[2025]
    assert linha["lucro_liquido"] == 24
    assert linha["lucro_liquido_controladora"] == 22
    assert linha["lucro_liquido_minoritarios"] == 2
    assert linha["patrimonio_liquido_total"] == 120
    assert linha["minoritarios"] == 20
    assert linha["dividendos_pagos"] == -11  # sem os pagos a não controladores
    assert linha["lair"] == 30 and linha["ir_csll"] == -6
    assert linha["receitas"] == 200 and linha["resultado_bruto"] == 50


def test_plano_novo_prefere_atribuicao_do_lucro_consolidado() -> None:
    # Plano de 2020 em diante (BB 2024-2025): atribuição sob 3.09 (antes das participações) e
    # sob 3.11 (lucro consolidado); vale a de 3.11. PL em 2.07, minoritários em 2.07.02.
    dados = dfp_banco(
        2025,
        BPP={
            "2.08": None,
            "2.08.09": None,
            "2.07": ("Patrimônio Líquido Consolidado", 120),
            "2.07.01": ("Patrimônio Líquido Atribuído ao Controlador", 100),
            "2.07.02": ("Patrimônio Líquido Atribuído aos Não Controladores", 20),
        },
        DRE={
            "3.09": ("Lucro ou Prejuízo antes das Participações e Contribuições Estatutárias", 25),
            "3.09.01": ("Atribuído aos Sócios da Empresa Controladora", 23),
            "3.09.02": ("Atribuído aos Sócios não Controladores", 2),
            "3.10": ("Participações nos Lucros e Contribuições Estatutárias", -1),
            "3.11": ("Lucro ou Prejuízo Líquido Consolidado do Período", 24),
            "3.11.01": ("Atribuído aos Sócios da Empresa Controladora", 22),
            "3.11.02": ("Atribuído aos Sócios não Controladores", 2),
        },
    )
    linha = per.anual(_padronizar(dados)).loc[2025]
    assert linha["lucro_liquido"] == 24
    assert linha["lucro_liquido_controladora"] == 22
    assert linha["patrimonio_liquido_total"] == 120
    assert linha["minoritarios"] == 20


def test_demonstracao_individual_sem_atribuicao() -> None:
    individual = dfp_banco(
        2025,
        BPP={
            "2.08": ("Patrimônio Líquido", 120),
            "2.08.09": None,
        },
        DRE={
            "3.09": ("Lucro ou Prejuízo Líquido do Período", 24),
            "3.09.01": None,
            "3.09.02": None,
        },
    ).assign(consolidado=False)
    linha = per.anual(_padronizar(individual, consolidado=False)).loc[2025]
    assert linha["lucro_liquido"] == 24
    assert linha["lucro_liquido_controladora"] == 24
    assert linha["patrimonio_liquido_total"] == 120


def test_documento_com_periodo_zerado_nao_substitui_o_anterior() -> None:
    # O ITR de 2025 traz o balanço comparativo de 31/12/2024 todo zerado (BAZA3, BNBR3...).
    zerado = documento(
        {"1": ("Ativo Total", 0), "2": ("Passivo Total", 0)},
        dem="BPA",
        dt_fim="2024-12-31",
        dt_refer="2025-03-31",
        fonte="ITR",
        ordem="PENÚLTIMO",
    )
    dados = juntar(dfp_banco(2024), zerado)
    linha = per.anual(_padronizar(dados)).loc[2024]
    assert linha["ativo_total"] == 1_000


def _historico() -> pd.DataFrame:
    """Dois exercícios: PL da controladora de 90 e 100; lucro da controladora de 22 em 2025."""
    return per.anual(
        _padronizar(
            juntar(
                dfp_banco(
                    2024,
                    BPP={"2.08": ("Patrimônio Líquido Consolidado", 110)},
                    BPA={"1": ("Ativo Total", 800)},
                ),
                dfp_banco(2025),
            )
        )
    )


def test_metricas_calculadas_a_mao() -> None:
    m = fin.metricas(_historico())
    a = m.loc[2025]
    assert a["patrimonio_liquido"] == 100
    assert a["roe"] == pytest.approx(22 / 90)  # lucro / PL da controladora do início
    assert a["roa"] == pytest.approx(24 / 800)
    assert a["dividendos_pagos"] == 11
    assert a["payout"] == pytest.approx(11 / 22)
    assert a["alavancagem"] == pytest.approx(1000 / 120)
    assert a["aliquota_efetiva"] == pytest.approx(6 / 30)
    assert np.isnan(m.loc[2024, "roe"])  # sem o PL de 2023


def test_metricas_sem_atribuicao_e_sem_dividendos() -> None:
    largo = pd.DataFrame(
        {
            "lair": [10.0, 10.0],
            "ir_csll": [-2.0, -2.0],
            "lucro_liquido": [8.0, 8.0],
            "lucro_liquido_controladora": [8.0, 0.0],
            "lucro_liquido_minoritarios": [0.0, 0.0],
            "ativo_total": [100.0, 100.0],
            "patrimonio_liquido_total": [40.0, 40.0],
        },
        index=pd.Index([2023, 2025], name="ano"),
    )
    m = fin.metricas(largo)
    assert m.loc[2025, "lucro_liquido_controladora"] == 8.0  # atribuição zerada
    assert bool(m.loc[2025, "atribuicao_ausente"])
    assert np.isnan(m.loc[2025, "roe"])  # 2024 ausente: sem PL inicial
    assert m["dividendos_pagos"].isna().all()  # sem a linha: NaN, não zero
    assert m["payout"].isna().all()
    with pytest.raises(ErroContabil, match="patrimonio_liquido_total"):
        fin.metricas(largo.drop(columns="patrimonio_liquido_total"))


def test_metricas_ltm() -> None:
    contas = contas_padronizadas(
        [
            saldo("patrimonio_liquido_total", "2025-06-30", 100),
            saldo("ativo_total", "2025-06-30", 1000),
            saldo("patrimonio_liquido_total", "2026-06-30", 110),
            saldo("ativo_total", "2026-06-30", 1100),
            *(
                ytd(conta, fim, valor)
                for fim, mult in (("2025-06-30", 1), ("2025-12-31", 2), ("2026-06-30", 1.5))
                for conta, valor in (
                    ("lucro_liquido", 10 * mult),
                    ("lucro_liquido_controladora", 10 * mult),
                    ("lair", 12 * mult),
                    ("ir_csll", -2 * mult),
                    ("dividendos_pagos", -4 * mult),
                )
            ),
        ]
    )
    ltm = fin.metricas_ltm(contas)
    assert ltm.name == pd.Timestamp("2026-06-30")
    assert ltm["lucro_liquido_controladora"] == pytest.approx(25)  # 20 + 15 - 10
    assert ltm["roe"] == pytest.approx(25 / 100)
    assert ltm["dividendos_pagos"] == pytest.approx(10)
    sem_balanco = (contas["dt_fim"] == pd.Timestamp("2025-06-30")) & contas["dt_ini"].isna()
    with pytest.raises(ErroContabil, match="ROE do LTM"):
        fin.metricas_ltm(contas[~sem_balanco])


def _qa(demonstracoes: pd.DataFrame) -> qa.ResultadoQA:
    selecionadas = pad.selecionar_reapresentacoes(demonstracoes)
    contas = pad.padronizar(selecionadas, PLANO, ticker="BANC4")
    return qa.verificar(selecionadas, contas, PLANO, ticker="BANC4", moeda="BRL", historico_anos=2)


def test_qa_financeira_sem_problemas() -> None:
    r = _qa(juntar(dfp_banco(2024), dfp_banco(2025)))
    assert r.verificacoes == ()
    assert r.cobertura == {c: 1.0 for c in PLANO.criticas}
    assert r.nao_mapeadas == ()


def test_qa_financeira_falhas() -> None:
    r = _qa(
        juntar(
            dfp_banco(2024, BPA={"1": ("Ativo Total", 999)}),
            dfp_banco(
                2025,
                BPP={"2.08": ("Patrimônio Líquido Consolidado", -5)},
                DRE={"3.09.01": ("Atribuído a Sócios da Empresa Controladora", 10)},
            ),
        )
    )
    codigos = {v.codigo: v for v in r.verificacoes}
    assert codigos["balanco_fecha"].severidade == "erro"
    assert codigos["balanco_fecha"].periodos == ("2024-12-31",)
    assert codigos["pl_positivo"].periodos == ("2025-12-31",)
    assert codigos["lucro_atribuido"].severidade == "aviso"
    assert "subcontas" in codigos
