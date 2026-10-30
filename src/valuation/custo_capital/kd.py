"""Custo da dívida antes do imposto (seção 10.3 do guia).

Histórico: despesas financeiras da DRE / dívida bruta média do exercício, mediana dos últimos
`JANELA_KD_ANOS` exercícios, limitada a [Rf + spread_min, Rf + spread_max]. As despesas
financeiras da CVM incluem mais que juros (variação cambial e monetária, encargos): é um proxy,
por isso o limite. Com IFRS 16 = dívida, a dívida bruta já inclui o arrendamento e as despesas
já incluem os juros dele.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from valuation.custo_capital import ErroCustoCapital

JANELA_KD_ANOS = 3


@dataclass(frozen=True)
class ResultadoKd:
    """`kd` é o valor usado; `kd_bruto` é a mediana antes do limite."""

    metodo: Literal["historico", "manual"]
    kd: float
    kd_bruto: float | None = None
    anos: tuple[int, ...] = ()
    piso: float | None = None
    teto: float | None = None
    avisos: tuple[str, ...] = ()


def taxas_anuais(despesas_financeiras: pd.Series, divida_bruta: pd.Series) -> pd.Series:
    """Despesa financeira (sinal da DRE: negativa) / dívida bruta média, por exercício.

    Exercício sem a dívida do ano anterior, sem despesa ou com dívida média <= 0 fica de fora.
    """
    media = (divida_bruta + divida_bruta.shift(1)) / 2
    media = media.where(divida_bruta.index.to_series().diff() == 1)  # anos consecutivos
    taxas = (-despesas_financeiras / media.reindex(despesas_financeiras.index)).where(media > 0)
    return taxas.dropna().sort_index()


def historico(
    despesas_financeiras: pd.Series,
    divida_bruta: pd.Series,
    *,
    piso: float,
    teto: float,
    janela: int = JANELA_KD_ANOS,
) -> ResultadoKd:
    """Mediana das taxas dos últimos `janela` exercícios, limitada a [piso, teto]."""
    taxas = taxas_anuais(despesas_financeiras, divida_bruta).tail(janela)
    if taxas.empty:
        raise ErroCustoCapital(
            "Kd histórico sem exercícios com despesa financeira e dívida bruta média positiva: "
            "use custo_capital.kd: {metodo: manual, valor: ...} no YAML da empresa."
        )
    bruto = float(taxas.median())
    kd = min(max(bruto, piso), teto)
    anos = tuple(int(a) for a in taxas.index)
    avisos: list[str] = []
    if len(taxas) < janela:
        avisos.append(f"Kd histórico com só {len(taxas)} exercício(s).")
    if kd != bruto:
        avisos.append(
            f"Kd histórico de {bruto:.2%} ({anos[0]}-{anos[-1]}) fora de [{piso:.2%}, {teto:.2%}];"
            f" usado {kd:.2%}."
        )
    return ResultadoKd("historico", kd, bruto, anos, piso, teto, tuple(avisos))


def manual(valor: float) -> ResultadoKd:
    return ResultadoKd("manual", valor)
