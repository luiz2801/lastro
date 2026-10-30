import json
from pathlib import Path

import pandas as pd
import pytest

from sintetico import dfp_completa as _dfp
from sintetico import juntar
from valuation.contabil import padronizacao as pad
from valuation.contabil import qa
from valuation.contabil.qa import ResultadoQA


def _qa(*docs: pd.DataFrame, historico_anos: int = 2) -> ResultadoQA:
    plano = pad.carregar_mapeamento()
    sel = pad.selecionar_reapresentacoes(juntar(*docs))
    contas = pad.padronizar(sel, plano, ticker="SINT3")
    return qa.verificar(
        sel, contas, plano, ticker="SINT3", moeda="BRL", historico_anos=historico_anos
    )


def _codigos(r: ResultadoQA) -> dict[str, tuple[str, ...]]:
    return {v.codigo: v.periodos for v in r.verificacoes}


def test_empresa_consistente_passa() -> None:
    r = _qa(_dfp(2024), _dfp(2025))
    assert r.verificacoes == ()
    assert set(r.cobertura.values()) == {1.0}
    assert r.nao_mapeadas == ()


def test_balanco_que_nao_fecha_e_erro() -> None:
    r = _qa(_dfp(2024), _dfp(2025, BPA={"1": 210}))
    assert [v.codigo for v in r.erros] == ["balanco_fecha", "balanco_fecha"]
    assert r.erros[0].periodos == ("2025-12-31",)
    assert "subcontas" in _codigos(r)


def test_custo_com_sinal_invertido_e_erro() -> None:
    r = _qa(_dfp(2024), _dfp(2025, DRE={"3.02": 60}))
    assert _codigos(r)["ebit_consistente"] == ("2025-01-01/2025-12-31",)
    assert r.erros


def test_receita_nao_positiva_e_erro() -> None:
    r = _qa(_dfp(2024), _dfp(2025, DRE={"3.01": -10, "3.02": 50}))
    assert _codigos(r)["receita_positiva"] == ("2025",)


def test_avisos_de_dre() -> None:
    r = _qa(_dfp(2024), _dfp(2025, DRE={"3.11.01": 5, "3.07": 30}))
    codigos = _codigos(r)
    assert codigos["lucro_atribuido"] == ("2025-01-01/2025-12-31",)
    assert codigos["lair_consistente"] == ("2025-01-01/2025-12-31",)
    assert not r.erros


def test_da_ausente_em_empresa_intensiva() -> None:
    r = _qa(_dfp(2024), _dfp(2025, DFC={"6.01.01.04": None}, DVA={"7.04.01": None}))
    codigos = _codigos(r)
    assert codigos["da_ausente"] == ("2025",)
    assert codigos["conta_critica_ausente"] == ("2025",)


def test_fontes_divergentes() -> None:
    r = _qa(_dfp(2024), _dfp(2025, DVA={"7.04.01": -12}))
    v = next(v for v in r.verificacoes if v.codigo == "fontes_divergentes")
    assert v.mensagem.startswith("da:")
    assert v.periodos == ("2025-01-01/2025-12-31",)


def test_salto_anual() -> None:
    r = _qa(_dfp(2024), _dfp(2025, DRE={"3.01": 200, "3.02": -160}))
    assert _codigos(r)["salto_anual"] == ("2025",)


def test_anos_faltantes_e_escala() -> None:
    r = _qa(_dfp(2023), _dfp(2025, escala="UNIDADE"), historico_anos=3)
    codigos = _codigos(r)
    assert codigos["anos_faltantes"] == ("2024",)
    assert "escala_varia" in codigos
    assert r.verificacoes[-1].severidade == "info"


def test_contas_nao_mapeadas_relevantes() -> None:
    r = _qa(
        _dfp(2024),
        _dfp(
            2025,
            DRE={
                "3.04.05": ("Outras Despesas Operacionais", -10),
                "3.04.01": ("Despesas com Vendas", -10),
            },
            BPP={"2.01.05": ("Outras Obrigações", 2)},
        ),
    )
    assert [(x["cd_conta"], x["fracao_da_base"]) for x in r.nao_mapeadas] == [("3.04.05", 0.1)]


def test_gravar_json(tmp_path: Path) -> None:
    r = _qa(_dfp(2024), _dfp(2025, DRE={"3.02": 60}))
    caminho = qa.gravar(r, tmp_path / "qa" / "qa_SINT3.json")
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert dados["ticker"] == "SINT3"
    assert dados["n_erros"] == len(r.erros) >= 1
    assert dados["verificacoes"][0]["severidade"] == "erro"
    assert "receita_liquida" in dados["cobertura"]


@pytest.mark.parametrize("severidade", ["erro", "aviso"])
def test_ordem_por_severidade(severidade: str) -> None:
    r = _qa(_dfp(2024), _dfp(2025, DRE={"3.02": 60, "3.11.01": 5}))
    ordem = [v.severidade for v in r.verificacoes]
    assert ordem == sorted(ordem, key=["erro", "aviso", "info"].index)
    assert severidade in ordem
