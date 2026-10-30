import dataclasses
import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from valuation.config import ConfigCsv
from valuation.custo_capital import ErroCustoCapital, capm
from valuation.custo_capital import beta as bt
from valuation.custo_capital import kd as kd_mod
from valuation.custo_capital import wacc as wc
from valuation.saida.csv import gravar_csv

DATA_BASE = dt.date(2026, 10, 30)


def test_wacc_calculado_a_mao() -> None:
    # 18% x 0,6 + 12% x (1 - 0,34) x 0,4 = 10,8% + 3,168%
    assert wc.wacc(0.18, 0.12, 0.34, 0.4) == pytest.approx(0.13968)


def test_estrutura_mercado_atual_e_manual() -> None:
    atual = wc.estrutura(metodo="mercado_atual", divida=40, equity=60)
    assert atual.peso_divida == pytest.approx(0.4)
    assert atual.peso_equity == pytest.approx(0.6)
    assert atual.divida_sobre_equity == pytest.approx(40 / 60)
    alvo = wc.estrutura(metodo="manual", divida=40, equity=60, divida_sobre_capital_alvo=0.2)
    assert alvo.peso_divida == 0.2
    assert alvo.divida_sobre_equity == pytest.approx(0.25)
    assert alvo.divida_sobre_equity_atual == pytest.approx(40 / 60)
    setor = wc.estrutura(metodo="setor", divida=40, equity=60, divida_sobre_capital_alvo=0.3)
    assert (setor.metodo, setor.peso_divida) == ("setor", 0.3)


def test_estrutura_invalida() -> None:
    with pytest.raises(ErroCustoCapital, match="Market cap"):
        wc.estrutura(metodo="mercado_atual", divida=1, equity=0)
    with pytest.raises(ErroCustoCapital, match="mediana dos pares"):
        wc.estrutura(metodo="setor", divida=1, equity=1)
    with pytest.raises(ErroCustoCapital, match="divida_sobre_capital"):
        wc.estrutura(metodo="manual", divida=1, equity=1)


def test_beta_realavancado_na_estrutura_alvo() -> None:
    regressao = bt.ResultadoBeta(metodo="regressao", beta=1.0, beta_bruto=1.0)
    atual = wc.estrutura(metodo="mercado_atual", divida=40, equity=60)
    assert wc.beta_na_estrutura(regressao, atual, 0.34) is regressao
    alvo = wc.estrutura(metodo="manual", divida=40, equity=60, divida_sobre_capital_alvo=0.2)
    # beta_u = 1 / (1 + 0,66 x 2/3) = 1 / 1,44; beta_L = beta_u x (1 + 0,66 x 0,25)
    assert wc.beta_na_estrutura(regressao, alvo, 0.34).beta == pytest.approx(1.165 / 1.44)
    manual = bt.manual(0.8)
    assert wc.beta_na_estrutura(manual, alvo, 0.34) is manual


def test_validar_g() -> None:
    wc.validar_g(0.12, 0.045)
    with pytest.raises(ErroCustoCapital, match="não converge"):
        wc.validar_g(0.04, 0.045)
    with pytest.raises(ErroCustoCapital):
        wc.validar_g(0.045, 0.045)


def _custo() -> wc.CustoCapital:
    beta = bt.ResultadoBeta(
        metodo="regressao", beta=1.0, beta_bruto=0.9, r2=0.3, n_obs=260, avisos=("aviso beta",)
    )
    ke = capm.custo_capital_proprio(
        metodo="brl_direto", moeda="BRL", beta=1.0, erp=0.06, rf_brl=0.12, rf_usd=0.04,
        crp=0.0, inflacao_usd=0.02, inflacao_brl=None,
    )  # fmt: skip
    return wc.montar(
        data_base=DATA_BASE,
        beta=beta,
        ke=ke,
        kd=kd_mod.manual(0.12),
        aliquota=0.34,
        estrutura=wc.estrutura(metodo="mercado_atual", divida=40, equity=60),
        data_balanco=dt.date(2026, 9, 30),
        avisos=("aviso extra",),
    )


def test_montar() -> None:
    cc = _custo()
    assert cc.wacc == pytest.approx(0.13968)
    assert cc.kd_liquido == pytest.approx(0.0792)
    assert cc.beta_regressao == 0.9
    assert cc.avisos == ("aviso beta", "aviso extra")


def test_tabela_e_csv(tmp_path: Path) -> None:
    tab = wc.tabela(_custo())
    assert list(tab.columns) == ["componente", "valor", "detalhe"]
    assert tab["valor"].dtype == "float64"
    por_nome = tab.set_index("componente")
    assert por_nome.loc["wacc", "valor"] == pytest.approx(0.13968)
    assert por_nome.loc["metodo_ke", "detalhe"] == "brl_direto"
    assert list(tab.loc[tab["componente"] == "aviso", "detalhe"]) == ["aviso beta", "aviso extra"]

    br = gravar_csv(tab, tmp_path / "a" / "wacc.csv", ConfigCsv())
    texto = br.read_text(encoding="utf-8-sig")
    assert texto.startswith("componente;valor;detalhe")
    assert "wacc;0,1396" in texto
    intl = gravar_csv(tab, tmp_path / "wacc_intl.csv", ConfigCsv(), "intl")
    assert "wacc,0.1396" in intl.read_text(encoding="utf-8")
    lido = pd.read_csv(br, sep=";", decimal=",", encoding="utf-8-sig")
    assert lido["valor"].dtype == "float64"


def test_kd_manual_na_tabela() -> None:
    cc = dataclasses.replace(_custo(), kd=kd_mod.manual(0.1))
    assert wc.tabela(cc).set_index("componente").loc["kd", "valor"] == 0.1
