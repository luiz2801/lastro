"""Ponte EV -> equity -> valor por ação (seção 11.2 do CLAUDE.md e ADR 0008).

Equity = EV - dívida bruta (com arrendamento, se IFRS 16 = dívida) + caixa e aplicações
- não controladores + investimentos em coligadas (se excluídas do EBIT) - `divida_extra`.
Saldos do último balanço até a data-base (o mesmo dos pesos do WACC), na moeda de reporte.
Valor por ação = equity / ações em circulação (ON + PN, sem tesouraria): igual para todas as
classes (aproximação; PN pode ter direitos diferentes). Diluição ignorada na v1.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Literal

import pandas as pd

from valuation.modelos import ErroModelo


@dataclass(frozen=True)
class ItensPonte:
    """Saldos da ponte, em unidades da moeda de reporte; todos positivos como no balanço."""

    divida_bruta: float
    caixa_e_aplicacoes: float
    minoritarios: float
    investimentos: float  # coligadas pelo valor contábil (0 se mantidas no EBIT)
    divida_extra: float
    acoes: int
    data_balanco: dt.date


def itens_do_balanco(
    balanco: pd.Series,
    *,
    acoes: int,
    data_balanco: dt.date,
    coligadas: Literal["somar_investimento_contabil", "manter_no_ebit"],
    minoritarios: Literal["contabil", "multiplo_pvp"],
) -> ItensPonte:
    """Itens da ponte a partir das métricas de balanço (`nao_financeiras.metricas_ltm`)."""
    if acoes <= 0:
        raise ErroModelo(f"Quantidade de ações em circulação inválida: {acoes}.")
    if minoritarios == "multiplo_pvp":
        raise ErroModelo(
            "ajustes.minoritarios = multiplo_pvp depende do P/VP dos pares (Fase 8): use contabil."
        )

    def valor(nome: str) -> float:
        x = float(balanco.get(nome, 0.0))
        return 0.0 if pd.isna(x) else x

    return ItensPonte(
        divida_bruta=valor("divida_bruta"),
        caixa_e_aplicacoes=valor("caixa_e_aplicacoes"),
        minoritarios=valor("minoritarios"),
        investimentos=valor("investimentos") if coligadas == "somar_investimento_contabil" else 0.0,
        divida_extra=valor("divida_extra"),
        acoes=acoes,
        data_balanco=data_balanco,
    )


@dataclass(frozen=True)
class ResultadoPonte:
    ev: float
    itens: ItensPonte
    equity: float
    valor_por_acao: float  # moeda de reporte


def ponte(ev: float, itens: ItensPonte) -> ResultadoPonte:
    equity = (
        ev
        - itens.divida_bruta
        + itens.caixa_e_aplicacoes
        - itens.minoritarios
        + itens.investimentos
        - itens.divida_extra
    )
    return ResultadoPonte(ev, itens, equity, equity / itens.acoes)


def tabela(r: ResultadoPonte) -> pd.DataFrame:
    """Ponte detalhada (`item, valor`) com o sinal com que cada item entra no equity."""
    i = r.itens
    linhas = [
        ("valor_da_firma", r.ev),
        ("divida_bruta", -i.divida_bruta),
        ("caixa_e_aplicacoes", i.caixa_e_aplicacoes),
        ("minoritarios", -i.minoritarios),
        ("investimentos_coligadas", i.investimentos),
        ("divida_extra", -i.divida_extra),
        ("equity", r.equity),
        ("acoes", float(i.acoes)),
        ("valor_por_acao", r.valor_por_acao),
    ]
    # + 0.0 evita "-0,0" no CSV para item zerado.
    return pd.DataFrame([(n, v + 0.0) for n, v in linhas], columns=["item", "valor"])
