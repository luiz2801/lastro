from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from test_dcf import FIM_2025, HISTORICO, ITENS, PREMISSAS
from valuation.analise import sensibilidade as sens
from valuation.config import ConfigCsv
from valuation.modelos import dcf
from valuation.saida.csv import gravar_matriz

DADOS = dcf.DadosAvaliacao(HISTORICO, ITENS, FIM_2025, False, 0.75)


def test_eixo() -> None:
    assert sens.eixo(0.10, 0.005, 0.01) == (0.09, 0.095, 0.10, 0.105, 0.11)
    assert sens.eixo(0.0, 0.01, 0.03) == (-0.03, -0.02, -0.01, 0.0, 0.01, 0.02, 0.03)


def test_sensibilidade_wacc_x_g() -> None:
    m = sens.wacc_x_g(
        PREMISSAS,
        DADOS,
        wacc=0.06,
        ronic=0.20,
        passo_wacc=0.005,
        faixa_wacc=0.01,
        passo_g=0.005,
        faixa_g=0.01,
    )
    assert list(m.index) == pytest.approx([0.05, 0.055, 0.06, 0.065, 0.07])
    assert list(m.columns) == pytest.approx([0.04, 0.045, 0.05, 0.055, 0.06])
    base = dcf.avaliar(PREMISSAS, DADOS, wacc=0.06, ronic=0.20).valor_por_acao
    assert m.loc[0.06, 0.05] == pytest.approx(base)
    # g >= WACC: célula vazia.
    assert np.isnan(m.loc[0.05, 0.05])
    assert np.isnan(m.loc[0.06, 0.06])
    # Valor cai com o WACC e, com RONIC > WACC, sobe com o g.
    coluna = m[0.04].to_numpy()
    assert (np.diff(coluna) < 0).all()
    assert (np.diff(m.loc[0.07].to_numpy()) > 0).all()


def test_sensibilidade_margem_x_crescimento(tmp_path: Path) -> None:
    m = sens.margem_x_crescimento(
        PREMISSAS,
        DADOS,
        wacc=0.10,
        ronic="wacc",
        passo_margem=0.01,
        faixa_margem=0.02,
        passo_crescimento=0.01,
        faixa_crescimento=0.01,
    )
    assert list(m.index) == pytest.approx([0.28, 0.29, 0.30, 0.31, 0.32])
    assert list(m.columns) == pytest.approx([0.065, 0.075, 0.085])
    base = dcf.avaliar(PREMISSAS, DADOS, wacc=0.10, ronic="wacc").valor_por_acao
    assert m.iloc[2, 1] == pytest.approx(base)
    assert (np.diff(m.iloc[:, 1].to_numpy()) > 0).all()

    caminho = gravar_matriz(m, tmp_path / "s.csv", ConfigCsv())
    lido = pd.read_csv(caminho, sep=";", decimal=",", encoding="utf-8-sig")
    assert lido.columns[0] == "margem_ebitda_terminal\\crescimento_medio"
    assert list(lido.columns[1:]) == ["0,0650", "0,0750", "0,0850"]
    assert lido.iloc[2, 2] == pytest.approx(base)
