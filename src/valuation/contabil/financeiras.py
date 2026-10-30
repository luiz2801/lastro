"""Métricas históricas de financeiras: bancos, seguradoras e holdings de seguros (ADR 0011).

Entrada: visão larga (`periodos.anual` ou linhas LTM) com uma linha por período, em ordem. O que
compara um período com o anterior (ROE, ROA) só usa a linha anterior quando ela está exatamente 12
meses antes; com buraco na série, sai NaN.

Convenções (as mesmas do DDM, seção 11.3 do CLAUDE.md):

- `patrimonio_liquido` = PL da controladora (PL consolidado - não controladores);
- `roe` = lucro da controladora / PL da controladora **do início** do período (LL_t = ROE_t x
  PL_{t-1}, como na projeção);
- `dividendos_pagos` positivo (saída de caixa, dividendos e JCP aos acionistas da controladora);
  ausente fica NaN, e não zero: o Santander passou ao DFC pelo método direto em 2021 e não abre a
  linha (zerar puxaria o payout para baixo); `payout` = dividendos pagos / lucro da controladora.

Algumas companhias informam a atribuição do lucro zerada na controladora e nos não controladores
(ABCB4 2020-2023, IRBR3 2022-2025): nesse caso o lucro inteiro vai para a controladora (o QA avisa
pela verificação `lucro_atribuido`).
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd

from valuation.contabil import ErroContabil, periodos

OPCIONAIS = (
    "receitas",
    "resultado_bruto",
    "lucro_liquido_minoritarios",
    "minoritarios",
)


def _coluna(largo: pd.DataFrame, nome: str) -> pd.Series:
    if nome in largo.columns:
        return largo[nome].astype(float)
    if nome in OPCIONAIS or nome == "dividendos_pagos":
        return pd.Series(np.nan, index=largo.index)
    raise ErroContabil(f"Conta {nome!r} ausente: não dá para calcular as métricas.")


def _anterior(serie: pd.Series) -> pd.Series:
    """Valor do período 12 meses antes (NaN se a linha anterior não for exatamente essa)."""
    indice = serie.index
    if isinstance(indice, pd.DatetimeIndex):
        esperado = pd.DatetimeIndex(indice) - pd.DateOffset(years=1)
        anterior = pd.Series(pd.DatetimeIndex(indice).to_series().shift(1).to_numpy())
        consecutivo = anterior.to_numpy() == esperado.to_numpy()
    else:
        numeros = pd.Series(indice, dtype=float)
        consecutivo = (numeros - numeros.shift(1) == 1).to_numpy()
    return serie.shift(1).where(consecutivo)


def metricas(largo: pd.DataFrame) -> pd.DataFrame:
    """Lucro, PL, ROE, dividendos, payout, alavancagem e alíquota efetiva por período."""

    def c(nome: str) -> pd.Series:
        return _coluna(largo, nome)

    m = pd.DataFrame(index=largo.index)
    m["receitas"] = c("receitas")
    m["resultado_bruto"] = c("resultado_bruto")
    m["lair"] = c("lair")
    m["ir_csll"] = c("ir_csll")
    m["aliquota_efetiva"] = (-m["ir_csll"] / m["lair"]).where(m["lair"] > 0)

    lucro = c("lucro_liquido")
    controladora = c("lucro_liquido_controladora")
    minoritarios = c("lucro_liquido_minoritarios").fillna(0.0)
    sem_atribuicao = (controladora == 0) & (minoritarios == 0) & (lucro != 0)
    m["lucro_liquido"] = lucro
    m["lucro_liquido_controladora"] = controladora.where(~sem_atribuicao, lucro)
    m["lucro_liquido_minoritarios"] = minoritarios
    m["atribuicao_ausente"] = sem_atribuicao

    m["ativo_total"] = c("ativo_total")
    m["patrimonio_liquido_total"] = c("patrimonio_liquido_total")
    m["minoritarios"] = c("minoritarios").fillna(0.0)
    m["patrimonio_liquido"] = m["patrimonio_liquido_total"] - m["minoritarios"]
    pl_inicio = _anterior(m["patrimonio_liquido"])
    m["roe"] = (m["lucro_liquido_controladora"] / pl_inicio).where(pl_inicio > 0)
    ativo_inicio = _anterior(m["ativo_total"])
    m["roa"] = (m["lucro_liquido"] / ativo_inicio).where(ativo_inicio > 0)
    m["alavancagem"] = (m["ativo_total"] / m["patrimonio_liquido_total"]).where(
        m["patrimonio_liquido_total"] > 0
    )

    m["dividendos_pagos"] = -c("dividendos_pagos")
    m["payout"] = (m["dividendos_pagos"] / m["lucro_liquido_controladora"]).where(
        m["lucro_liquido_controladora"] > 0
    )
    return m.replace([np.inf, -np.inf], np.nan)


def metricas_ltm(contas: pd.DataFrame, *, dt_fim: pd.Timestamp | None = None) -> pd.Series:
    """Métricas nos 12 meses até `dt_fim`; ROE e ROA contra o balanço de 12 meses antes."""
    atual = periodos.ltm(contas, dt_fim)
    fim = pd.Timestamp(str(atual.name))
    bal = periodos.saldos(contas)
    um_ano_antes = fim - pd.DateOffset(years=1)
    if um_ano_antes not in bal.index:
        raise ErroContabil(f"Sem balanço em {um_ano_antes.date()} para o ROE do LTM.")
    largo = pd.DataFrame([bal.loc[um_ano_antes], atual], index=[um_ano_antes, fim])
    m = metricas(largo)
    return cast(pd.Series, m.loc[fim])
