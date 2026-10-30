"""Projeção ano a ano do FCFF (seção 9.3 do CLAUDE.md e ADR 0006).

Fluxo: `anos_projetados` (do exercício seguinte ao último histórico até o fim do horizonte) →
`resolver` (troca cada `sugerido` pela sugestão e monta as trajetórias) → `aplicar_cenario`
(deltas pessimista/otimista) → `projetar` (função pura, sem I/O).

Por ano: receita = receita anterior x (1 + g); EBITDA = margem x receita; EBIT = EBITDA - D&A
(EBIT ajustado: sem equivalência patrimonial e não recorrentes); imposto = alíquota x EBIT;
capex e pagamento de arrendamento proporcionais à receita; ΔNWC = (NWC/receita) x Δreceita;
FCFF = NOPAT + D&A - capex - ΔNWC [- arrendamento, se IFRS 16 = dívida e
`capex_equivalente_arrendamento`].

`fracao` = parte do fluxo do ano que ainda está por vir na data-base: 0 para exercício já
encerrado (ainda sem DFP), dias restantes / 365 no ano corrente e 1 nos seguintes. O horizonte conta
só os anos com fluxo por vir (o ano corrente parcial é o primeiro).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, replace
from typing import Literal

import numpy as np
import pandas as pd

from valuation.config import ConfigTerminal
from valuation.projecao import ErroProjecao
from valuation.projecao.premissas import (
    SUGERIDO,
    Caminho,
    Cenarios,
    ConfigProjecao,
    DeltaCenario,
    TerminalEmpresa,
    TerminalFinanceira,
)
from valuation.projecao.sugestor import Sugestao, Sugestoes, pct

NomeCenario = Literal["pessimista", "base", "otimista"]
CENARIOS: tuple[NomeCenario, ...] = ("pessimista", "base", "otimista")
COLUNAS_PROJECAO = (
    "fracao",
    "crescimento",
    "receita_liquida",
    "margem_ebitda",
    "ebitda",
    "da",
    "ebit",
    "aliquota",
    "imposto",
    "nopat",
    "capex",
    "delta_nwc",
    "arrendamento",
    "fcff",
)


@dataclass(frozen=True)
class PremissasResolvidas:
    """Premissas numéricas de um cenário; trajetórias com um valor por ano de `anos`."""

    anos: tuple[int, ...]
    crescimento: tuple[float, ...]
    margem_ebitda: tuple[float, ...]
    da_sobre_receita: float
    capex_sobre_receita: float
    nwc_sobre_receita: float
    arrendamento_sobre_receita: float
    aliquota: float
    descontar_arrendamento: bool
    g_terminal: float
    cenario: NomeCenario = "base"


@dataclass(frozen=True)
class DeltaResolvido:
    crescimento: float = 0.0
    margem_ebitda: float = 0.0
    capex: float = 0.0


def primeiro_ano_aberto(data_base: dt.date) -> int:
    """Primeiro exercício (jan-dez) não encerrado na data-base."""
    return data_base.year if data_base < dt.date(data_base.year, 12, 31) else data_base.year + 1


def anos_projetados(ano_base: int, data_base: dt.date, horizonte: int) -> tuple[int, ...]:
    """Do exercício seguinte a `ano_base` até o último dos `horizonte` anos com fluxo por vir."""
    if horizonte < 1:
        raise ErroProjecao(f"Horizonte de projeção inválido: {horizonte}.")
    aberto = primeiro_ano_aberto(data_base)
    if ano_base >= aberto:
        raise ErroProjecao(
            f"O histórico vai até {ano_base}, exercício não encerrado em {data_base}: "
            "use só exercícios anteriores à data-base."
        )
    return tuple(range(ano_base + 1, aberto + horizonte))


def fracao_restante(ano: int, data_base: dt.date) -> float:
    """Fração do fluxo de `ano` posterior à data-base (dias restantes / 365, entre 0 e 1)."""
    fim = dt.date(ano, 12, 31)
    if fim <= data_base:
        return 0.0
    if data_base < dt.date(ano, 1, 1):
        return 1.0
    return min(1.0, (fim - data_base).days / 365)


def g_terminal(terminal: TerminalEmpresa | TerminalFinanceira, config: ConfigTerminal) -> Sugestao:
    """Crescimento perpétuo nominal: o do YAML da empresa ou o teto do settings."""
    if terminal.g_nominal is None:
        return Sugestao(config.g_nominal_max, "g terminal = settings.terminal.g_nominal_max")
    if terminal.g_nominal > config.g_nominal_max:
        raise ErroProjecao(
            f"terminal.g_nominal ({pct(terminal.g_nominal, 2)}) acima do teto "
            f"settings.terminal.g_nominal_max ({pct(config.g_nominal_max, 2)})."
        )
    return Sugestao(terminal.g_nominal, "g terminal do YAML da empresa")


def linear(inicio: float, fim: float, n: int) -> tuple[float, ...]:
    return tuple(float(x) for x in np.linspace(inicio, fim, n)) if n > 1 else (inicio,)


def escolher(valor: float | str, sugestao: Sugestao) -> float:
    return sugestao.valor if valor == SUGERIDO else float(valor)


def trajetoria(
    caminho: Caminho, inicio: Sugestao, fim: Sugestao, n: int, nome: str
) -> tuple[float, ...]:
    if isinstance(caminho, tuple):
        if len(caminho) < n:
            raise ErroProjecao(
                f"{nome}: a lista tem {len(caminho)} valores e a projeção tem {n} anos."
            )
        return tuple(caminho[:n])
    return linear(escolher(caminho.inicio, inicio), escolher(caminho.fim, fim), n)


def resolver(
    config: ConfigProjecao,
    sugestoes: Sugestoes,
    *,
    anos: tuple[int, ...],
    aliquota_limite: float,
    descontar_arrendamento: bool,
) -> PremissasResolvidas:
    """Premissas do cenário base: `sugerido` vira a sugestão; número ou lista ficam como estão."""
    if anos[0] != sugestoes.ano_base + 1:
        raise ErroProjecao(
            f"A projeção começa em {anos[0]}, mas o histórico das sugestões vai até "
            f"{sugestoes.ano_base}."
        )
    n = len(anos)
    aliquota = escolher(config.aliquota_imposto.valor, sugestoes.aliquota)
    limite = config.aliquota_imposto.limite_superior
    limite = aliquota_limite if limite is None else limite
    if aliquota > limite:
        raise ErroProjecao(f"Alíquota {pct(aliquota)} acima do limite {pct(limite)}.")
    return PremissasResolvidas(
        anos=anos,
        crescimento=trajetoria(
            config.receita.crescimento,
            sugestoes.crescimento_inicio,
            sugestoes.crescimento_fim,
            n,
            "receita.crescimento",
        ),
        margem_ebitda=trajetoria(
            config.margens.ebitda,
            sugestoes.margem_inicio,
            sugestoes.margem_fim,
            n,
            "margens.ebitda",
        ),
        da_sobre_receita=escolher(config.da_sobre_receita, sugestoes.da_sobre_receita),
        capex_sobre_receita=escolher(config.capex_sobre_receita, sugestoes.capex_sobre_receita),
        nwc_sobre_receita=escolher(config.nwc_sobre_receita, sugestoes.nwc_sobre_receita),
        arrendamento_sobre_receita=escolher(
            config.arrendamento_sobre_receita, sugestoes.arrendamento_sobre_receita
        ),
        aliquota=aliquota,
        descontar_arrendamento=descontar_arrendamento,
        g_terminal=sugestoes.crescimento_fim.valor,
    )


def resolver_cenarios(
    cenarios: Cenarios, sugestoes: Sugestoes
) -> dict[NomeCenario, DeltaResolvido]:
    """Deltas de cada cenário; os sugeridos têm sinal pessimista (-g, -margem, +capex)."""

    def delta(d: DeltaCenario, sinal: int) -> DeltaResolvido:
        def valor(v: float | str, s: Sugestao, sinal_campo: int) -> float:
            return sinal * sinal_campo * s.valor if v == SUGERIDO else float(v)

        return DeltaResolvido(
            crescimento=valor(d.crescimento_pp, sugestoes.delta_crescimento, 1),
            margem_ebitda=valor(d.margem_ebitda_pp, sugestoes.delta_margem, 1),
            capex=valor(d.capex_pp, sugestoes.delta_capex, -1),
        )

    return {
        "pessimista": delta(cenarios.pessimista, -1),
        "base": DeltaResolvido(),
        "otimista": delta(cenarios.otimista, 1),
    }


def aplicar_cenario(
    base: PremissasResolvidas, delta: DeltaResolvido, cenario: NomeCenario
) -> PremissasResolvidas:
    """Soma os deltas a todos os anos explícitos (o g terminal não muda); capex ≥ 0."""
    return replace(
        base,
        crescimento=tuple(g + delta.crescimento for g in base.crescimento),
        margem_ebitda=tuple(m + delta.margem_ebitda for m in base.margem_ebitda),
        capex_sobre_receita=max(0.0, base.capex_sobre_receita + delta.capex),
        cenario=cenario,
    )


def projetar(
    historico: pd.DataFrame, premissas: PremissasResolvidas, *, data_base: dt.date
) -> pd.DataFrame:
    """Projeção anual (índice `ano`, colunas `COLUNAS_PROJECAO`), em unidades da moeda.

    `historico` = métricas anuais; a receita do último exercício é a base do primeiro ano.
    """
    if historico.empty:
        raise ErroProjecao("Histórico vazio: nada a projetar.")
    ano_base = int(historico.index.max())
    if premissas.anos[0] != ano_base + 1:
        raise ErroProjecao(
            f"Premissas começam em {premissas.anos[0]}, mas o histórico vai até {ano_base}."
        )
    receita_base = float(historico["receita_liquida"].astype(float).loc[ano_base])
    if not receita_base > 0:
        raise ErroProjecao(f"Receita de {ano_base} não é positiva: não dá para projetar.")

    p = premissas
    anos = pd.Index(p.anos, name="ano")
    crescimento = np.array(p.crescimento)
    receita = receita_base * np.cumprod(1 + crescimento)
    receita_anterior = np.concatenate(([receita_base], receita[:-1]))
    t = pd.DataFrame(index=anos)
    t["fracao"] = [fracao_restante(a, data_base) for a in p.anos]
    t["crescimento"] = crescimento
    t["receita_liquida"] = receita
    t["margem_ebitda"] = p.margem_ebitda
    t["ebitda"] = t["margem_ebitda"] * receita
    t["da"] = p.da_sobre_receita * receita
    t["ebit"] = t["ebitda"] - t["da"]
    t["aliquota"] = p.aliquota
    t["imposto"] = t["ebit"] * p.aliquota
    t["nopat"] = t["ebit"] - t["imposto"]
    t["capex"] = p.capex_sobre_receita * receita
    t["delta_nwc"] = p.nwc_sobre_receita * (receita - receita_anterior)
    t["arrendamento"] = p.arrendamento_sobre_receita * receita
    t["fcff"] = t["nopat"] + t["da"] - t["capex"] - t["delta_nwc"]
    if p.descontar_arrendamento:
        t["fcff"] -= t["arrendamento"]
    return t[list(COLUNAS_PROJECAO)]
