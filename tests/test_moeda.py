import pytest

from sintetico import documento, juntar
from valuation.contabil import ErroContabil
from valuation.contabil.moeda import converter_para_brl, detectar_moeda


def test_detecta_real() -> None:
    assert detectar_moeda(documento({"1": 1}, dem="BPA", dt_fim="2025-12-31")) == "BRL"


def test_override_ignora_campo_da_cvm() -> None:
    dados = documento({"1": 1}, dem="BPA", dt_fim="2025-12-31")
    assert detectar_moeda(dados, "USD") == "USD"


def test_moeda_que_muda_entre_periodos_e_erro() -> None:
    dados = juntar(
        documento({"1": 1}, dem="BPA", dt_fim="2024-12-31"),
        documento({"1": 1}, dem="BPA", dt_fim="2025-12-31", moeda="DOLAR"),
    )
    with pytest.raises(ErroContabil, match="muda"):
        detectar_moeda(dados)


def test_moeda_desconhecida_e_erro() -> None:
    with pytest.raises(ErroContabil, match="não suportada"):
        detectar_moeda(documento({"1": 1}, dem="BPA", dt_fim="2025-12-31", moeda="EURO"))


def test_conversao() -> None:
    assert converter_para_brl(10.0, "BRL", 5.0) == 10.0
    assert converter_para_brl(10.0, "USD", 5.4) == pytest.approx(54.0)
    with pytest.raises(ErroContabil):
        converter_para_brl(10.0, "USD", 0.0)
