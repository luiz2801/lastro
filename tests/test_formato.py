"""`saida/formato.py`: texto em pt-BR; sem dado nunca vira zero."""

import math

import pytest

from valuation.saida import formato as fo

NAN = math.nan


@pytest.mark.parametrize(
    ("valor", "unidade", "esperado"),
    [
        (0.1234, "%", "12,3%"),
        (2.54, "x", "2,5x"),
        (1_234_567_890.0, "mi", "1.235"),
        (NAN, "%", "—"),
        (NAN, "mi", "—"),
    ],
)
def test_formatar(valor: float, unidade: str, esperado: str) -> None:
    assert fo.formatar(valor, unidade) == esperado


def test_multiplo() -> None:
    assert fo.multiplo("dividend_yield", 0.0612) == "6,1%"
    assert fo.multiplo("p_l", 12.34) == "12,3x"
    assert fo.multiplo("p_l", NAN) == "—"


@pytest.mark.parametrize(
    ("componente", "valor", "esperado"),
    [
        ("market_cap", 2_500_000_000.0, "2.500 mi"),
        ("divida_bruta", 1_000_000.0, "1 mi"),
        ("beta_n_obs", 260.0, "260"),
        ("beta", 0.92290, "0,923"),
        ("wacc", 0.12345, "12,35%"),
        ("data_base", NAN, ""),
    ],
)
def test_componente_wacc(componente: str, valor: float, esperado: str) -> None:
    assert fo.componente_wacc(componente, valor) == esperado


def test_reais_e_brl() -> None:
    assert fo.reais(1234.5) == "R$ 1.234,50"
    assert fo.reais(NAN) == "—"
    assert fo.brl(1234.5) == "R$ 1.234,50"
    assert fo.brl(1234.5, casas=0) == "R$ 1.234"  # arredonda como o format do Python (par)
    assert fo.brl(None) == "—"


def test_preco_curto_taxa_e_pct() -> None:
    assert fo.preco_curto(1234.5) == "R$ 1234,50"
    assert fo.preco_curto(None) == "—"
    assert fo.taxa(0.1234) == "12,34%"
    assert fo.taxa(None) == "sem solução"
    assert fo.taxa(NAN) == "sem solução"
    assert fo.pct(0.123) == "12,3%"
    assert fo.pct(None) == "—"


def test_sinal_da_recomendacao() -> None:
    assert [fo.sinal(s) for s in ("compra", "manter", "venda")] == ["Compra", "Manter", "Venda"]
    assert fo.sinal(NAN) == "—"  # rodada anterior à coluna


@pytest.mark.parametrize(
    ("sinal", "preco", "ke", "esperado"),
    [
        ("venda", 120.0, 0.25, "preço R$ 120,00 acima do valor justo ponderado R$ 100,00"),
        (
            "compra",
            70.0,
            0.25,
            "preço R$ 70,00 até o preço máximo de compra R$ 80,00 e Ke implícito 25,00% no "
            "mínimo igual ao hurdle 20,00%",
        ),
        (
            "manter",
            90.0,
            0.25,
            "preço R$ 90,00 entre o preço máximo de compra R$ 80,00 e o valor justo ponderado "
            "R$ 100,00",
        ),
        ("manter", 70.0, None, "preço R$ 70,00 até o preço máximo, mas Ke implícito sem solução"),
        ("manter", 70.0, NAN, "preço R$ 70,00 até o preço máximo, mas Ke implícito sem solução"),
        (
            "manter",
            70.0,
            0.15,
            "preço R$ 70,00 até o preço máximo, mas Ke implícito 15,00% abaixo do hurdle 20,00%",
        ),
    ],
)
def test_criterio_recomendacao(sinal: str, preco: float, ke: float | None, esperado: str) -> None:
    texto = fo.criterio_recomendacao(
        sinal, preco=preco, valor_ponderado=100.0, preco_maximo=80.0, ke_implicito=ke, hurdle=0.20
    )
    assert texto == esperado
