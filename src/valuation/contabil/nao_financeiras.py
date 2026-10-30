"""Métricas históricas de empresas não financeiras (seção 7.6 do guia).

Entrada: visão larga (`periodos.anual` ou linhas LTM) com uma linha por período, em ordem e com
12 meses entre linhas consecutivas (ΔNWC e ROIC usam a linha anterior). Saída em unidades da
moeda, com a convenção: capex, D&A, dividendos e pagamentos de arrendamento **positivos**;
IR/CSLL como na DRE (negativo = despesa).

Contas opcionais (arrendamento fora de empréstimos, aplicações de longo prazo, equivalência,
pagamento de arrendamento, dividendos) ausentes contam como zero.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, cast

import numpy as np
import pandas as pd

from valuation.contabil import ErroContabil, periodos

OPCIONAIS = (
    "equivalencia_patrimonial",
    "arrendamento_cp_em_emprestimos",
    "arrendamento_cp_outros",
    "arrendamento_lp_em_emprestimos",
    "arrendamento_lp_outros",
    "aplicacoes_financeiras",
    "aplicacoes_financeiras_lp",
    "pagamento_arrendamento",
    "dividendos_pagos",
    "minoritarios",
    "investimentos",
)


@dataclass(frozen=True)
class NaoRecorrente:
    """Item não recorrente do EBIT de um exercício: `valor` é retirado do EBIT ajustado.

    Ganho não recorrente entra positivo; perda (ex.: impairment) entra negativa.
    """

    ano: int
    valor: float
    descricao: str = ""
    conta: Literal["ebit"] = "ebit"


@dataclass(frozen=True)
class AjustesContabeis:
    """Ajustes da seção 9.1 (`ajustes:` no YAML da empresa). Padrões = os do guia."""

    ifrs16: Literal["divida", "ignorar"] = "divida"
    capex_equivalente_arrendamento: bool = True
    coligadas: Literal["somar_investimento_contabil", "manter_no_ebit"] = (
        "somar_investimento_contabil"
    )
    nao_recorrentes: Sequence[NaoRecorrente] = field(default_factory=tuple)


def _coluna(largo: pd.DataFrame, nome: str) -> pd.Series:
    if nome in largo.columns:
        serie = largo[nome].astype(float)
        return serie.fillna(0.0) if nome in OPCIONAIS else serie
    if nome in OPCIONAIS:
        return pd.Series(0.0, index=largo.index)
    raise ErroContabil(f"Conta {nome!r} ausente: não dá para calcular as métricas.")


def _nao_recorrentes(indice: pd.Index, itens: Sequence[NaoRecorrente]) -> pd.Series:
    por_ano: dict[int, float] = {}
    for item in itens:
        por_ano[item.ano] = por_ano.get(item.ano, 0.0) + item.valor
    return pd.Series([por_ano.get(i, 0.0) for i in indice], index=indice, dtype=float)


def metricas(
    largo: pd.DataFrame, *, aliquota_nominal: float, ajustes: AjustesContabeis | None = None
) -> pd.DataFrame:
    """EBITDA, NOPAT, capex, capital de giro, FCFF, dívida líquida e ROIC por período.

    - `ebitda` = EBIT contábil + D&A (definição das companhias; bate com os releases).
    - `ebit_ajustado` = EBIT - equivalência (se `coligadas = somar_investimento_contabil`; o
      investimento entra na ponte EV -> equity) - não recorrentes.
    - `aliquota_operacional` = alíquota efetiva limitada a [0, nominal]; nominal quando o LAIR
      não é positivo.
    - `fcff` = NOPAT + D&A - capex - ΔNWC [- pagamento de arrendamento, se IFRS 16 = dívida e
      `capex_equivalente_arrendamento`].
    - `roic` = NOPAT / capital investido médio (PL + dívida líquida).
    """
    aj = ajustes or AjustesContabeis()

    def c(nome: str) -> pd.Series:
        return _coluna(largo, nome)

    m = pd.DataFrame(index=largo.index)

    m["receita_liquida"] = c("receita_liquida")
    m["ebit"] = c("ebit")
    m["da"] = c("da")
    m["ebitda"] = m["ebit"] + m["da"]
    m["equivalencia_patrimonial"] = c("equivalencia_patrimonial")
    m["nao_recorrentes"] = _nao_recorrentes(largo.index, aj.nao_recorrentes)
    m["ebit_ajustado"] = m["ebit"] - m["nao_recorrentes"]
    if aj.coligadas == "somar_investimento_contabil":
        m["ebit_ajustado"] -= m["equivalencia_patrimonial"]
    m["ebitda_ajustado"] = m["ebit_ajustado"] + m["da"]
    m["margem_ebitda"] = m["ebitda"] / m["receita_liquida"]
    m["margem_ebit_ajustado"] = m["ebit_ajustado"] / m["receita_liquida"]

    m["lair"] = c("lair")
    m["ir_csll"] = c("ir_csll")
    lair_positivo = m["lair"] > 0
    m["aliquota_efetiva"] = (-m["ir_csll"] / m["lair"]).where(lair_positivo)
    m["aliquota_operacional"] = (
        m["aliquota_efetiva"].clip(0.0, aliquota_nominal).fillna(aliquota_nominal)
    )
    m["nopat"] = m["ebit_ajustado"] * (1 - m["aliquota_operacional"])
    m["lucro_liquido"] = c("lucro_liquido")
    m["lucro_liquido_controladora"] = c("lucro_liquido_controladora")

    m["capex"] = -c("capex")
    m["pagamento_arrendamento"] = -c("pagamento_arrendamento")
    m["dividendos_pagos"] = -c("dividendos_pagos")
    m["cfo"] = c("cfo")
    m["fcf_caixa"] = m["cfo"] - m["capex"]

    arr_cp_emp = c("arrendamento_cp_em_emprestimos")
    arr_lp_emp = c("arrendamento_lp_em_emprestimos")
    m["arrendamento_cp"] = arr_cp_emp + c("arrendamento_cp_outros")
    m["arrendamento"] = m["arrendamento_cp"] + arr_lp_emp + c("arrendamento_lp_outros")
    divida_cp = c("emprestimos_cp") - arr_cp_emp
    m["divida_financeira"] = divida_cp + c("emprestimos_lp") - arr_lp_emp
    m["divida_bruta"] = m["divida_financeira"]
    if aj.ifrs16 == "divida":
        m["divida_bruta"] += m["arrendamento"]
    m["caixa_e_aplicacoes"] = c("caixa") + c("aplicacoes_financeiras")
    m["divida_liquida"] = m["divida_bruta"] - m["caixa_e_aplicacoes"]

    ativo_operacional = c("ativo_circulante") - m["caixa_e_aplicacoes"]
    passivo_operacional = c("passivo_circulante") - divida_cp - m["arrendamento_cp"]
    m["nwc"] = ativo_operacional - passivo_operacional
    m["delta_nwc"] = m["nwc"].diff()

    m["fcff"] = m["nopat"] + m["da"] - m["capex"] - m["delta_nwc"]
    if aj.ifrs16 == "divida" and aj.capex_equivalente_arrendamento:
        m["fcff"] -= m["pagamento_arrendamento"]

    m["patrimonio_liquido_total"] = c("patrimonio_liquido_total")
    m["minoritarios"] = c("minoritarios")
    m["investimentos"] = c("investimentos")
    m["capital_investido"] = m["patrimonio_liquido_total"] + m["divida_liquida"]
    medio = (m["capital_investido"] + m["capital_investido"].shift(1)) / 2
    m["roic"] = (m["nopat"] / medio).where(medio > 0)
    return m.replace([np.inf, -np.inf], np.nan)


def metricas_ltm(
    contas: pd.DataFrame,
    *,
    aliquota_nominal: float,
    dt_fim: pd.Timestamp | None = None,
    ajustes: AjustesContabeis | None = None,
) -> pd.Series:
    """Métricas nos 12 meses até `dt_fim`; ΔNWC e ROIC contra o balanço de 12 meses antes."""
    atual = periodos.ltm(contas, dt_fim)
    fim = pd.Timestamp(str(atual.name))
    bal = periodos.saldos(contas)
    um_ano_antes = fim - pd.DateOffset(years=1)
    if um_ano_antes not in bal.index:
        raise ErroContabil(f"Sem balanço em {um_ano_antes.date()} para o ΔNWC do LTM.")
    largo = pd.DataFrame([bal.loc[um_ano_antes], atual], index=[um_ano_antes, fim])
    # Métricas de fluxo da primeira linha não são usadas; evita erro de conta ausente.
    largo = largo.reindex(columns=largo.columns.union(atual.index))
    largo.loc[um_ano_antes, atual.index.difference(bal.columns)] = 0.0
    m = metricas(largo, aliquota_nominal=aliquota_nominal, ajustes=ajustes)
    # Em LTM o índice é data: não recorrentes por ano não se aplicam.
    return cast(pd.Series, m.loc[fim])
