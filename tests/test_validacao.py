import logging

import pytest

from valuation.data.validacao import ErroDadosExternos, Leitura, cruzar, manual


def test_concordancia_dentro_da_tolerancia() -> None:
    v = cruzar("x", Leitura(1.00, "A"), Leitura(1.01, "B"), tolerancia=0.02, relativa=True)
    assert v.status == "ok"
    assert v.valor == 1.00
    assert v.aviso is None


def test_divergencia_mantem_principal_e_avisa(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        v = cruzar("taxa", Leitura(0.10, "A"), Leitura(0.14, "B"), tolerancia=0.01)
    assert v.status == "divergente"
    assert v.valor == 0.10
    assert v.divergencia == pytest.approx(0.04)
    assert v.aviso is not None and "taxa" in v.aviso
    assert "divergem" in caplog.text


def test_tolerancia_relativa_e_absoluta_sao_diferentes() -> None:
    a, b = Leitura(100.0, "A"), Leitura(101.0, "B")
    assert cruzar("x", a, b, tolerancia=0.02, relativa=True).status == "ok"
    assert cruzar("x", a, b, tolerancia=0.02, relativa=False).status == "divergente"


@pytest.mark.parametrize("principal_ausente", [True, False])
def test_uma_fonte_so_vira_sem_validacao(principal_ausente: bool) -> None:
    unica = Leitura(5.0, "U")
    p, a = (None, unica) if principal_ausente else (unica, None)
    v = cruzar("x", p, a, tolerancia=0.1)
    assert v.status == "sem_validacao"
    assert v.valor == 5.0
    assert v.aviso is not None


def test_nenhuma_fonte_e_erro() -> None:
    with pytest.raises(ErroDadosExternos):
        cruzar("x", None, None, tolerancia=0.1)


def test_manual() -> None:
    v = manual("Rf", 0.12)
    assert (v.status, v.valor, v.aviso) == ("manual", 0.12, None)
