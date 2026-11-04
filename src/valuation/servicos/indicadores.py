"""Indicadores por ativo: série histórica (anual + LTM) e múltiplos de mercado."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pandas as pd

from valuation.analise import indicadores as ind
from valuation.config import Settings
from valuation.contabil import ErroContabil
from valuation.contabil import financeiras as fin
from valuation.contabil import nao_financeiras as nf
from valuation.contabil import periodos as per
from valuation.data import precos as prc
from valuation.modelos import multiplos as mt
from valuation.modelos import ponte as pt
from valuation.servicos.empresa import Padronizada
from valuation.servicos.mercado import Mercado


@dataclass(frozen=True)
class TabelaIndicadores:
    """Uma linha por período, na ordem de `colunas`; a última é o LTM."""

    tabela: pd.DataFrame
    colunas: list[str]
    definicoes: dict[str, tuple[str, str, str]]  # indicador -> (rótulo, unidade, glossário)
    financeira: bool


@dataclass(frozen=True)
class IndicadoresMercado:
    fundamentos: mt.Fundamentos
    multiplos: dict[str, float]


def data_balanco(contas: pd.DataFrame, base: dt.date) -> pd.Timestamp:
    """Última data até a data-base com fluxos acumulados e balanço (ponto do LTM)."""
    comuns = per.acumulado_no_ano(contas).index.intersection(per.saldos(contas).index)
    comuns = comuns[comuns <= pd.Timestamp(base)]
    if comuns.empty:
        raise ErroContabil(f"Nenhuma demonstração até {base}.")
    return pd.Timestamp(comuns.max())


def _anos_encerrados(indice: pd.Index, base: dt.date) -> list[object]:
    """Exercícios (índice anual) encerrados em 31/12 até a data-base."""
    return [a for a in indice if dt.date(int(a), 12, 31) <= base]


def serie_indicadores(
    p: Padronizada, settings: Settings, base: dt.date, anos: int
) -> TabelaIndicadores:
    """Indicadores dos últimos `anos` exercícios encerrados até a data-base, mais o LTM."""
    financeira = p.plano.tipo == "financeira"
    data_bal = data_balanco(p.contas, base)
    if financeira:
        anual = fin.metricas(per.anual(p.contas))
        ltm = fin.metricas_ltm(p.contas, dt_fim=data_bal)
        definicoes = ind.HISTORICOS_FINANCEIRA
        calcular = ind.historicos_financeira
    else:
        aliquota = settings.impostos.aliquota_nominal
        anual = nf.metricas(per.anual(p.contas), aliquota_nominal=aliquota, ajustes=p.ajustes)
        ltm = nf.metricas_ltm(
            p.contas, aliquota_nominal=aliquota, dt_fim=data_bal, ajustes=p.ajustes
        )
        definicoes = ind.HISTORICOS
        calcular = ind.historicos
    anual = anual.loc[_anos_encerrados(anual.index, base)].tail(anos)
    tabela = calcular(pd.concat([anual, ltm.to_frame().T]))
    colunas = [*map(str, anual.index), f"LTM {data_bal:%m/%Y}"]
    return TabelaIndicadores(tabela, colunas, definicoes, financeira)


def fundamentos(
    p: Padronizada,
    cap: prc.MarketCap,
    settings: Settings,
    base: dt.date,
    dolar: float,
    acoes: int | None = None,
) -> mt.Fundamentos:
    """Métricas LTM no último balanço até a data-base e market cap, em BRL.

    `acoes` = quantidade usada no valor por ação (padrão: ON + PN do market cap).
    """
    data_bal = data_balanco(p.contas, base)
    acoes = sum(c.acoes for c in cap.classes) if acoes is None else acoes
    if p.plano.tipo == "financeira":
        return mt.fundamentos_financeira(
            p.premissas.ticker,
            fin.metricas_ltm(p.contas, dt_fim=data_bal),
            acoes=acoes,
            data_balanco=data_bal.date(),
            market_cap=cap.valor,
        )
    ltm = nf.metricas_ltm(
        p.contas,
        aliquota_nominal=settings.impostos.aliquota_nominal,
        dt_fim=data_bal,
        ajustes=p.ajustes,
    )
    itens = pt.itens_do_balanco(
        ltm,
        acoes=acoes,
        data_balanco=data_bal.date(),
        coligadas=p.premissas.ajustes.coligadas,
        minoritarios="contabil",
    )
    cambio = 1.0 if p.moeda == "BRL" else dolar
    return mt.fundamentos(p.premissas.ticker, ltm, itens=itens, market_cap=cap.valor, cambio=cambio)


def indicadores_de_mercado(
    p: Padronizada, mk: Mercado, settings: Settings, base: dt.date
) -> IndicadoresMercado:
    """Fundamentos LTM da data-base e os múltiplos de mercado (a mesma conta do `comparar`)."""
    f = fundamentos(p, mk.cap, settings, base, mk.macro.cambio.valor)
    return IndicadoresMercado(f, ind.de_mercado(f, financeira=p.plano.tipo == "financeira"))
