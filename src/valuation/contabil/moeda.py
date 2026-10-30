"""Moeda de reporte das demonstrações e conversão do valor final para BRL.

A escala (`MIL`/`UNIDADE`) já foi aplicada na ingestão (`data/cvm.py`); aqui só se confere que a
moeda é a mesma em todos os períodos. Hoje a CVM traz `MOEDA = REAL` para todas as companhias,
inclusive a Vale (ADR 0002): outra moeda só aparece por `moeda_relatorio` no YAML da empresa.
"""

from __future__ import annotations

from typing import Literal

import pandas as pd

from valuation.contabil import ErroContabil

Moeda = Literal["BRL", "USD"]
MoedaRelatorio = Literal["auto", "BRL", "USD"]
MOEDAS_CVM: dict[str, Moeda] = {"REAL": "BRL", "DOLAR": "USD", "DÓLAR": "USD"}


def detectar_moeda(demonstracoes: pd.DataFrame, moeda_relatorio: MoedaRelatorio = "auto") -> Moeda:
    """Moeda das demonstrações. `moeda_relatorio` diferente de `auto` sobrescreve o campo da CVM.

    Mais de uma moeda entre os períodos, ou moeda desconhecida, é erro (seção 7.5 do guia).
    """
    if moeda_relatorio != "auto":
        return moeda_relatorio
    valores = sorted(demonstracoes["moeda"].dropna().str.strip().str.upper().unique())
    if not valores:
        raise ErroContabil("Demonstrações sem a coluna MOEDA preenchida.")
    if len(valores) > 1:
        raise ErroContabil(f"Moeda muda entre períodos: {', '.join(valores)}.")
    if valores[0] not in MOEDAS_CVM:
        raise ErroContabil(f"Moeda {valores[0]!r} não suportada; defina moeda_relatorio.")
    return MOEDAS_CVM[valores[0]]


def converter_para_brl(valor: float, moeda: Moeda, cambio_brl_por_unidade: float) -> float:
    """Converte um valor final (ex.: valor por ação) para BRL pela taxa spot da data-base.

    Só para a saída: fluxos e taxa de desconto ficam sempre na moeda de reporte.
    """
    if moeda == "BRL":
        return valor
    if cambio_brl_por_unidade <= 0:
        raise ErroContabil(f"Câmbio inválido: {cambio_brl_por_unidade}.")
    return valor * cambio_brl_por_unidade
