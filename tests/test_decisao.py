"""Preço teto de Bazin e recomendação (`analise/decisao.py`, ADR 0025), com valores à mão."""

import math

import pandas as pd
import pytest

from valuation.analise import decisao as dec
from valuation.modelos import ErroModelo

# 2020 fica fora da janela de 5 exercícios que termina em 2025.
DIVIDENDOS = pd.Series([100.0, 10.0, 20.0, 30.0, 40.0, 50.0], index=range(2020, 2026))


def test_teto_bazin_a_mao() -> None:
    # Média de 2021 a 2025 = 30; 30 / 10 ações = R$ 3 por ação; 3 / 6% = R$ 50.
    t = dec.teto_bazin(DIVIDENDOS, anos=5, acoes=10, cambio=1.0, yield_minimo=0.06)
    assert t.dividendo_por_acao == pytest.approx(3.0)
    assert t.valor == pytest.approx(50.0)
    assert t.exercicios == (2021, 2022, 2023, 2024, 2025)
    assert t.yield_minimo == 0.06
    assert t.avisos == ()


def test_teto_bazin_com_cambio_e_indice_de_datas() -> None:
    datas = pd.to_datetime([f"{a}-12-31" for a in range(2020, 2026)])
    serie = pd.Series(DIVIDENDOS.to_numpy(), index=datas)
    t = dec.teto_bazin(serie, anos=3, acoes=10, cambio=5.0, yield_minimo=0.08)
    # Média de 2023 a 2025 = 40; x 5 / 10 = R$ 20 por ação; / 8% = R$ 250.
    assert t.dividendo_por_acao == pytest.approx(20.0)
    assert t.valor == pytest.approx(250.0)


def test_teto_bazin_ano_sem_dado_sai_da_media_com_aviso() -> None:
    serie = DIVIDENDOS.drop(2023)
    serie[2022] = math.nan
    t = dec.teto_bazin(serie, anos=5, acoes=1, cambio=1.0, yield_minimo=0.05)
    # Sobram 2021, 2024 e 2025: média (10 + 40 + 50) / 3.
    assert t.exercicios == (2021, 2024, 2025)
    assert t.dividendo_por_acao == pytest.approx(100 / 3)
    assert t.avisos == (
        "Teto de Bazin com 3 de 5 exercícios (2021 a 2025); sem dado em 2022, 2023.",
    )


def test_teto_bazin_sem_dividendos_fica_indefinido() -> None:
    zeros = pd.Series([0.0, 0.0], index=[2024, 2025])
    t = dec.teto_bazin(zeros, anos=5, acoes=10, cambio=1.0, yield_minimo=0.06)
    assert t.valor is None and t.dividendo_por_acao is None
    assert t.avisos[-1] == "Teto de Bazin indefinido: sem dividendos pagos de 2021 a 2025."
    vazio = dec.teto_bazin(pd.Series(dtype=float), anos=5, acoes=10, cambio=1.0, yield_minimo=0.06)
    assert vazio.valor is None and vazio.avisos == ("Teto de Bazin sem histórico anual.",)


@pytest.mark.parametrize(
    ("anos", "acoes", "yield_minimo", "mensagem"),
    [(0, 10, 0.06, "Janela"), (5, 0, 0.06, "ações"), (5, 10, 0.0, "Yield")],
)
def test_teto_bazin_parametros_invalidos(
    anos: int, acoes: float, yield_minimo: float, mensagem: str
) -> None:
    with pytest.raises(ErroModelo, match=mensagem):
        dec.teto_bazin(DIVIDENDOS, anos=anos, acoes=acoes, cambio=1.0, yield_minimo=yield_minimo)


def _recomendar(
    preco: float, ke: float | None = 0.25, motivos: tuple[str, ...] = ()
) -> dec.Recomendacao:
    # Valor ponderado 100, margem de 20%: preço máximo 80; hurdle 20%.
    return dec.recomendar(
        preco=preco,
        valor_ponderado=100.0,
        preco_maximo_compra=80.0,
        ke_implicito=ke,
        hurdle=0.20,
        motivos_confianca=motivos,
    )


@pytest.mark.parametrize(
    ("preco", "ke", "sinal"),
    [
        (70.0, 0.25, "compra"),
        (80.0, 0.20, "compra"),  # nos dois limites ainda é compra
        (70.0, 0.19, "manter"),  # barato, mas o retorno não paga o hurdle
        (70.0, None, "manter"),  # Ke implícito sem solução
        (90.0, 0.25, "manter"),  # entre o preço máximo e o valor ponderado
        (100.0, 0.25, "manter"),  # no valor ponderado ainda não é venda
        (100.01, 0.25, "venda"),
        (150.0, None, "venda"),
    ],
)
def test_recomendacao_por_preco_e_hurdle(preco: float, ke: float | None, sinal: str) -> None:
    r = _recomendar(preco, ke)
    assert (r.sinal, r.sinal_modelo, r.confianca, r.rebaixada) == (sinal, sinal, "alta", False)


def test_confianca_baixa_rebaixa_so_a_compra() -> None:
    motivos = ("sem pares medidos",)
    compra = _recomendar(70.0, motivos=motivos)
    assert (compra.sinal, compra.sinal_modelo, compra.confianca) == ("manter", "compra", "baixa")
    assert compra.rebaixada and compra.motivos_confianca == motivos
    venda = _recomendar(120.0, motivos=motivos)
    assert (venda.sinal, venda.confianca, venda.rebaixada) == ("venda", "baixa", False)
    assert _recomendar(90.0, motivos=motivos).sinal == "manter"


def test_recomendacao_exige_preco_positivo() -> None:
    with pytest.raises(ErroModelo, match="Preço"):
        _recomendar(0.0)


def _motivos(**trocas: object) -> tuple[str, ...]:
    args: dict[str, object] = {
        "erros_qa": 0,
        "vt_sobre_valor": 0.60,
        "alerta_vt": 0.75,
        "n_pares": 3,
        "min_pares": 3,
        "r2_beta": 0.30,
        "min_r2": 0.10,
    }
    return dec.motivos_baixa_confianca(**{**args, **trocas})  # type: ignore[arg-type]


def test_motivos_de_confianca_baixa() -> None:
    assert _motivos() == ()
    assert _motivos(r2_beta=None) == ()  # beta manual ou por comparáveis não tem R²
    assert _motivos(vt_sobre_valor=0.75) == ()  # no alerta ainda não é motivo
    assert _motivos(erros_qa=2) == ("QA com 2 erro(s)",)
    assert _motivos(vt_sobre_valor=0.80) == ("VT de 80% do valor, acima do alerta de 75%",)
    assert _motivos(vt_sobre_valor=math.nan) == ("VT sobre o valor indefinido (valor <= 0)",)
    assert _motivos(n_pares=None) == ("sem pares medidos",)
    assert _motivos(n_pares=2) == ("2 par(es) válido(s), abaixo do mínimo de 3",)
    assert _motivos(r2_beta=0.05) == ("R² do beta de 0,05, abaixo de 0,10",)
    assert len(_motivos(erros_qa=1, n_pares=0, r2_beta=0.01)) == 3
