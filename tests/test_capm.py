import pytest

from valuation.custo_capital import ErroCustoCapital, capm

PARAMS = {"erp": 0.05, "rf_brl": 0.12, "rf_usd": 0.04, "crp": 0.03, "inflacao_usd": 0.02}


def test_brl_direto() -> None:
    ke = capm.custo_capital_proprio(
        metodo="brl_direto", moeda="BRL", beta=1.1, inflacao_brl=None, **PARAMS
    )
    assert ke.ke == pytest.approx(0.12 + 1.1 * 0.05)  # 17,5%; sem CRP por cima
    assert ke.ke_usd is None


def test_usd_crp_em_usd() -> None:
    ke = capm.custo_capital_proprio(
        metodo="usd_crp", moeda="USD", beta=1.1, inflacao_brl=None, **PARAMS
    )
    assert ke.ke == pytest.approx(0.04 + 1.1 * 0.05 + 0.03)  # 12,5%
    assert ke.ke_usd == ke.ke


def test_usd_crp_convertido_para_brl() -> None:
    ke = capm.custo_capital_proprio(
        metodo="usd_crp", moeda="BRL", beta=1.1, inflacao_brl=0.04, **PARAMS
    )
    assert ke.ke == pytest.approx(1.125 * 1.04 / 1.02 - 1)  # 14,71%
    with pytest.raises(ErroCustoCapital, match="inflação brasileira"):
        capm.custo_capital_proprio(
            metodo="usd_crp", moeda="BRL", beta=1.1, inflacao_brl=None, **PARAMS
        )


def test_metodos_coerentes_com_inflacao_consistente() -> None:
    # Se Rf_BRL = Fisher(Rf_USD + CRP), com beta 0 os dois métodos dão o mesmo Ke em BRL.
    rf_brl = capm.converter_taxa(0.04 + 0.03, 0.04, 0.02)
    params = {**PARAMS, "rf_brl": rf_brl}
    direto = capm.custo_capital_proprio(
        metodo="brl_direto", moeda="BRL", beta=0.0, inflacao_brl=None, **params
    )
    crp = capm.custo_capital_proprio(
        metodo="usd_crp", moeda="BRL", beta=0.0, inflacao_brl=0.04, **params
    )
    assert direto.ke == pytest.approx(crp.ke)


def test_metodo_efetivo() -> None:
    assert capm.metodo_efetivo("brl_direto", "BRL") == ("brl_direto", None)
    metodo, aviso = capm.metodo_efetivo("brl_direto", "USD")
    assert metodo == "usd_crp" and aviso
    with pytest.raises(ErroCustoCapital):
        capm.custo_capital_proprio(
            metodo="brl_direto", moeda="USD", beta=1, inflacao_brl=None, **PARAMS
        )
