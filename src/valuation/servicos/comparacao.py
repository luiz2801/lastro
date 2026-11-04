"""Múltiplos de hoje do ativo contra pares do setor e Ibovespa, só com empresas já em disco."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from valuation.analise import anomalias as an
from valuation.config import (
    DIR_EMPRESAS,
    DIR_PROCESSED,
    DIR_RAW,
    ErroConfiguracao,
    Setor,
    Settings,
)
from valuation.contabil import ErroContabil
from valuation.data import cadastro as cad
from valuation.data import precos as prc
from valuation.data.validacao import ErroDadosExternos
from valuation.modelos import ErroModelo
from valuation.modelos import multiplos as mt
from valuation.projecao import premissas as pm
from valuation.servicos import empresa as emp
from valuation.servicos import indicadores as sind
from valuation.universo import EmpresaUniverso


def tickers_pares(
    premissas: pm.PremissasEmpresa, proprios: tuple[str, ...], setor: Setor | None
) -> list[str]:
    """Pares do setor + `pares.incluir` - `pares.excluir`, sem as classes da própria empresa."""
    candidatos = [*(setor.pares if setor else ()), *premissas.pares.incluir]
    fora = {cad.normalizar_ticker(t) for t in (*premissas.pares.excluir, *proprios)}
    unicos = dict.fromkeys(cad.normalizar_ticker(t) for t in candidatos)
    return [t for t in unicos if t not in fora]


def corte_fixo(settings: Settings, nome: str) -> float | None:
    """Corte de n < 15 (`multiplos.corte_*`); `None` para os múltiplos sem parâmetro."""
    cfg = settings.multiplos
    return {
        "p_l": cfg.corte_pl,
        "p_vp": cfg.corte_p_vp,
        "ev_ebitda": cfg.corte_ev_ebitda,
        "ev_ebit": cfg.corte_ev_ebit,
    }.get(nome)


@dataclass(frozen=True)
class Medida:
    """Fundamentos de hoje de uma companhia, ou o motivo de não haver."""

    ticker: str
    fundamentos: mt.Fundamentos | None
    motivo: str | None = None


def medir_de_hoje(
    p: emp.Padronizada,
    settings: Settings,
    base: dt.date,
    *,
    dir_raw: Path = DIR_RAW,
    dir_processed: Path = DIR_PROCESSED,
) -> Medida:
    """Market cap pelo último fechamento em disco e LTM do último balanço, sem rede.

    A conta é a do `comparar`; muda só a origem do preço (o cache, sem validação cruzada).
    """
    ticker = p.premissas.ticker
    if p.moeda != "BRL":
        return Medida(ticker, None, f"reporta em {p.moeda}")
    caminho = dir_processed / "cvm" / str(p.empresa.cd_cvm) / "composicao_capital.parquet"
    if not caminho.is_file():
        return Medida(ticker, None, "sem composição do capital em disco")
    precos: dict[str, float] = {}
    for classe in p.empresa.classes:
        df = prc.historico_em_cache(prc.simbolo_yahoo(classe.ticker), dir_raw / "precos")
        if df is None:
            continue
        ate = df.loc[df.index <= pd.Timestamp(base), "close"].dropna()
        if not ate.empty:
            precos[classe.ticker] = float(ate.iloc[-1])
    if not precos:
        return Medida(ticker, None, "sem cotação em disco")
    try:
        cap = prc.market_cap(p.empresa, pd.read_parquet(caminho), precos, base)
        return Medida(ticker, sind.fundamentos(p, cap, settings, base, 1.0))
    except (ErroDadosExternos, ErroContabil, ErroModelo) as e:
        return Medida(ticker, None, str(e))


def medir_varios(
    tickers: Iterable[str],
    cadastro: pd.DataFrame,
    settings: Settings,
    base: dt.date,
    *,
    dir_raw: Path = DIR_RAW,
    dir_processed: Path = DIR_PROCESSED,
    dir_empresas: Path = DIR_EMPRESAS,
) -> list[Medida]:
    """Mede só quem já tem demonstrações em disco; os demais voltam com o motivo."""
    medidas: list[Medida] = []
    for ticker in tickers:
        try:
            p = emp.padronizar(
                ticker, cadastro, dir_processed=dir_processed, dir_empresas=dir_empresas
            )
        except (ErroContabil, ErroConfiguracao, cad.ErroCadastro) as e:
            medidas.append(Medida(ticker, None, str(e)))
            continue
        medidas.append(
            medir_de_hoje(p, settings, base, dir_raw=dir_raw, dir_processed=dir_processed)
        )
    return medidas


def tickers_ibovespa(universo: Sequence[EmpresaUniverso], financeira: bool) -> list[str]:
    """Empresas do universo do mesmo tipo: financeiras separadas, holdings fora."""
    tipo = "financeira" if financeira else "nao_financeira"
    return [e.ticker for e in universo if e.tipo_modelo == tipo]


@dataclass(frozen=True)
class ReferenciaGrupo:
    valor: float
    n: int  # empresas com o múltiplo válido depois do filtro
    descartadas: dict[str, str] = field(default_factory=dict)  # ticker -> motivo


def referencia_do_grupo(
    medidas: Sequence[Medida],
    nome: mt.NomeMultiplo,
    tipo: an.Referencia,
    settings: Settings,
) -> ReferenciaGrupo:
    """Referência de hoje de um grupo, com o mesmo tratamento de anomalias dos gráficos."""
    valores: dict[str, float] = {}
    descartadas: dict[str, str] = {}
    metrica = mt.DEFINICOES[nome][1]
    for m in medidas:
        if m.fundamentos is None:
            continue
        valor = mt.multiplo(m.fundamentos, nome)
        if pd.notna(valor):
            valores[m.ticker] = valor
        elif an.CLASSES[nome] is an.Classe.POSITIVO and m.fundamentos.metrica(metrica) <= 0:
            descartadas[m.ticker] = "múltiplo ≤ 0"
    filtro = an.filtrar(
        pd.Series(valores, dtype="float64"), an.CLASSES[nome], corte_fixo(settings, nome)
    )
    descartadas.update({str(k): str(v) for k, v in filtro.descartados.items()})
    return ReferenciaGrupo(an.referencia(filtro, tipo), len(filtro.validos), descartadas)
