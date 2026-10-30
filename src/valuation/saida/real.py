"""Relatório complementar em valores reais (seção 11.5 do CLAUDE.md e ADR 0016).

Deflaciona os fluxos e o valor terminal nominais pelo IPCA projetado, para o equivalente em reais
da data-base. IPCA do ano = Focus daquele ano; entre anos do Focus e além do último vale o último
Focus anterior (mesma convenção do IPCA de longo prazo do `usd_crp`); antes do primeiro, o IPCA de
12 meses. Funções puras: a data-base e o IPCA entram por parâmetro.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

import pandas as pd

COLUNAS = ("cenario", "item", "ano", "ipca_ano", "deflator", "nominal", "real")


@dataclass(frozen=True)
class IpcaProjetado:
    por_ano: Mapping[int, float]  # Focus (decimal a.a.)
    ipca_12m: float  # usado antes do primeiro ano do Focus

    def taxa(self, ano: int) -> float:
        anteriores = [a for a in self.por_ano if a <= ano]
        return self.por_ano[max(anteriores)] if anteriores else self.ipca_12m


def fator_acumulado(data_base: dt.date, anos_a_frente: float, ipca: IpcaProjetado) -> float:
    """Inflação acumulada entre a data-base e `anos_a_frente` anos depois (dias / 365), com o
    IPCA de cada ano civil capitalizado pelos dias que o trecho passa nele."""
    alvo = data_base + dt.timedelta(days=round(anos_a_frente * 365))
    fator, cursor = 1.0, data_base
    while cursor < alvo:
        fim = min(dt.date(cursor.year + 1, 1, 1), alvo)
        fator *= (1 + ipca.taxa(cursor.year)) ** ((fim - cursor).days / 365)
        cursor = fim
    return fator


@dataclass(frozen=True)
class FluxosCenario:
    """O que se deflaciona de um cenário (moeda de reporte; valor por ação já em BRL)."""

    fluxos: pd.DataFrame  # índice ano; colunas `fluxo` e `tau` (anos desde a data-base)
    valor_terminal: float  # no fim do último ano explícito
    taxa_desconto: float  # WACC ou Ke
    g: float
    valor_por_acao: float


def fisher_real(taxa_nominal: float, inflacao: float) -> float:
    return (1 + taxa_nominal) / (1 + inflacao) - 1


def tabela(
    data_base: dt.date, ipca: IpcaProjetado, cenarios: Mapping[str, FluxosCenario]
) -> pd.DataFrame:
    """`valores_reais.csv` em formato longo: fluxos, valor terminal, valor por ação (já em reais
    da data-base, deflator 1) e taxas nominal e real (Fisher com o IPCA do último ano projetado)."""
    linhas: list[tuple[str, str, float | None, float | None, float, float, float]] = []
    for nome, c in cenarios.items():
        ultimo_ano = int(c.fluxos.index[-1])
        for ano, f in c.fluxos.iterrows():
            d = fator_acumulado(data_base, float(f["tau"]), ipca)
            linhas.append(
                (
                    nome,
                    "fluxo",
                    int(cast(int, ano)),
                    ipca.taxa(int(cast(int, ano))),
                    d,
                    f["fluxo"],
                    f["fluxo"] / d,
                )
            )
        d_t = fator_acumulado(data_base, float(c.fluxos["tau"].iloc[-1]), ipca)
        linhas.append(
            (
                nome,
                "valor_terminal",
                ultimo_ano,
                ipca.taxa(ultimo_ano),
                d_t,
                c.valor_terminal,
                c.valor_terminal / d_t,
            )
        )
        linhas.append((nome, "valor_por_acao", None, None, 1.0, c.valor_por_acao, c.valor_por_acao))
        pi_lp = ipca.taxa(ultimo_ano)
        for item, nominal in (("taxa_desconto", c.taxa_desconto), ("g_terminal", c.g)):
            linhas.append(
                (nome, item, None, pi_lp, float("nan"), nominal, fisher_real(nominal, pi_lp))
            )
    df = pd.DataFrame(linhas, columns=list(COLUNAS))
    df["ano"] = df["ano"].astype("Int64")
    return df
