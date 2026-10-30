from pathlib import Path

import numpy as np
import pandas as pd

from valuation.saida import graficos as gr
from valuation.saida.arquivos import CenarioSaida, Faixa

PNG = b"\x89PNG\r\n\x1a\n"


def _png(caminho: Path) -> bool:
    return caminho.is_file() and caminho.read_bytes()[:8] == PNG


def test_formatacao_pt_br() -> None:
    assert gr.br(1234.5) == "1.234,50"
    assert gr.br(float("nan")) == "—"
    assert gr.reais(9.5) == "R$ 9,50"
    assert gr.pct(0.1234) == "12,3%"


def _cenario(valor: float) -> CenarioSaida:
    anos = pd.Index([2026, 2027, 2028], name="ano")
    fluxos = pd.DataFrame({"fluxo": [1e9, 2e9, 3e9], "tau": [0.2, 1.2, 2.2]}, index=anos)
    ponte = pd.DataFrame(
        {
            "item": [
                "valor_da_firma",
                "divida_bruta",
                "caixa_e_aplicacoes",
                "minoritarios",
                "investimentos_coligadas",
                "divida_extra",
                "equity",
            ],
            "valor": [10e9, -2e9, 1e9, -0.5e9, 0.1e9, 0.0, 8.6e9],
        }
    )
    return CenarioSaida(valor, fluxos, fluxos, 4e9, 6e9, 9e9, 0.15, 0.05, ponte)


def test_todos_os_graficos_geram_png(tmp_path: Path) -> None:
    faixas = [
        Faixa("DCF (pess. a otim.)", 8.0, 15.0, 11.0),
        Faixa("P/L", 9.0, 13.0, 11.0, aviso=True),
        Faixa("Faixa de 52 semanas", 9.0, 20.0),
    ]
    assert _png(
        gr.football_field(
            faixas,
            preco=12.0,
            preco_maximo=9.0,
            caminho=tmp_path / "f.png",
            ticker="X",
            perfil="moderado",
        )
    )
    cen = {"pessimista": _cenario(8.0), "base": _cenario(11.0), "otimista": _cenario(15.0)}
    assert _png(
        gr.cascata_ponte(
            cen["base"].ponte, caminho=tmp_path / "c.png", ticker="X", cenario="base", moeda="BRL"
        )  # type: ignore[arg-type]
    )
    matriz = pd.DataFrame(
        np.arange(81, dtype=float).reshape(9, 9),
        index=pd.Index(np.linspace(0.14, 0.18, 9), name="wacc"),
        columns=pd.Index(np.linspace(0.04, 0.06, 9), name="g"),
    )
    assert _png(
        gr.heatmap(
            matriz,
            caminho=tmp_path / "h.png",
            titulo="t",
            rotulo_x="g",
            rotulo_y="WACC",
            preco=40.0,
        )
    )
    serie = pd.Series([1e9, 2e9, 3e9], index=[2024, 2025, 2026])
    paineis = [
        gr.Painel(
            "Receita", serie, {"base": serie, "pessimista": serie * 0.9, "otimista": serie * 1.1}
        )
    ]
    assert _png(
        gr.historico_vs_projecao(
            paineis, caminho=tmp_path / "p.png", ticker="X", referencia="base", moeda="BRL"
        )
    )
    assert _png(
        gr.composicao_valor(
            cen,
            caminho=tmp_path / "v.png",
            ticker="X",
            rotulo_fluxos="VP",
            rotulo_total="EV",
            moeda="BRL",
        )
    )


def test_football_aceita_valores_negativos(tmp_path: Path) -> None:
    f = [Faixa("DCF", -3.0, 5.0, 1.0)]
    assert _png(
        gr.football_field(
            f,
            preco=2.0,
            preco_maximo=-1.0,
            caminho=tmp_path / "f.png",
            ticker="X",
            perfil="conservador",
        )
    )
