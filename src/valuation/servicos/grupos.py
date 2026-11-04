"""Séries de múltiplos de um grupo de empresas (pares do setor ou Ibovespa), do que está em disco.

Sem rede. Empresa sem os dados da série fica de fora, com o motivo; ninguém é estimado.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from valuation.analise import anomalias as an
from valuation.analise import serie_multiplos as sm
from valuation.config import (
    DIR_EMPRESAS,
    DIR_PROCESSED,
    DIR_RAW,
    ErroConfiguracao,
    Settings,
)
from valuation.contabil import ErroContabil
from valuation.data import cadastro as cad
from valuation.data import cvm
from valuation.modelos import multiplos as mt
from valuation.servicos import comparacao as cmp
from valuation.servicos import historico_mercado as hm

MOTIVO_SEM_SERIE = "sem a série histórica em disco"


@dataclass(frozen=True)
class PainelGrupo:
    """Um múltiplo de cada empresa por mês. `faltam` = quem ficou de fora, com o motivo."""

    tickers: tuple[str, ...]
    multiplos: dict[str, pd.DataFrame]  # múltiplo -> mês x empresa
    faltam: dict[str, str] = field(default_factory=dict)
    com_cotacao: pd.Series | None = None  # mês -> empresas com cotação naquele mês

    @property
    def em_disco(self) -> int:
        return len(self.tickers) - len(self.faltam)


def _uma_empresa(
    ticker: str,
    cadastro: pd.DataFrame,
    settings: Settings,
    base: dt.date,
    dir_raw: Path,
    dir_processed: Path,
    dir_empresas: Path,
) -> tuple[pd.DataFrame | None, pd.Series | None, str | None]:
    """Múltiplos por mês de uma empresa, sem os meses de balanço defasado, e quem tem cotação."""
    try:
        empresa = cad.empresa_por_ticker(cadastro, ticker)
        pasta = dir_processed / "cvm" / str(empresa.cd_cvm)
        if not (pasta / cvm.ARQUIVO_SERIES_COMPOSICAO).is_file():
            return None, None, MOTIVO_SEM_SERIE
        series = hm.series_com_cache(
            ticker,
            cadastro,
            settings,
            base,
            dir_raw=dir_raw,
            dir_processed=dir_processed,
            dir_empresas=dir_empresas,
        )
    except (ErroContabil, ErroConfiguracao, cad.ErroCadastro) as e:
        return None, None, str(e)
    if series is None:
        return None, None, "sem cotação em disco"
    if series.multiplos.empty or series.market_cap.notna().sum() == 0:
        return None, None, MOTIVO_SEM_SERIE
    velhos = sm.defasados(series.vigencia, settings.multiplos.defasagem_max_meses)
    multiplos = series.multiplos.where(~velhos.reindex(series.multiplos.index, fill_value=False))
    meses = pd.DatetimeIndex(multiplos.index).to_period("M").to_timestamp("M").normalize()
    multiplos.index = meses
    cotadas = pd.Series(series.market_cap.notna().to_numpy(), index=meses, dtype="bool")
    return multiplos, cotadas, None


def montar_painel(
    tickers: Sequence[str],
    cadastro: pd.DataFrame,
    settings: Settings,
    base: dt.date,
    *,
    dir_raw: Path = DIR_RAW,
    dir_processed: Path = DIR_PROCESSED,
    dir_empresas: Path = DIR_EMPRESAS,
) -> PainelGrupo:
    colunas: dict[str, dict[str, pd.Series]] = {}
    faltam: dict[str, str] = {}
    cotadas: dict[str, pd.Series] = {}
    for ticker in tickers:
        multiplos, cotada, motivo = _uma_empresa(
            ticker, cadastro, settings, base, dir_raw, dir_processed, dir_empresas
        )
        if multiplos is None or cotada is None:
            faltam[ticker] = str(motivo)
            continue
        cotadas[ticker] = cotada
        for nome in multiplos.columns:
            colunas.setdefault(str(nome), {})[ticker] = multiplos[nome]
    com_cotacao = pd.DataFrame(cotadas).sort_index().fillna(False).astype(bool).sum(axis=1)
    return PainelGrupo(
        tuple(tickers),
        {nome: pd.DataFrame(por_empresa).sort_index() for nome, por_empresa in colunas.items()},
        faltam,
        com_cotacao,
    )


def referencia_em_serie(
    painel: PainelGrupo, nome: mt.NomeMultiplo, tipo: an.Referencia, settings: Settings
) -> pd.DataFrame | None:
    """Referência do grupo mês a mês; `None` se nenhuma empresa tem este múltiplo."""
    tabela = painel.multiplos.get(nome)
    if tabela is None or tabela.empty:
        return None
    if painel.com_cotacao is not None:
        tabela = sm.sem_mes_parcial(tabela, painel.com_cotacao)
    return sm.serie_do_grupo(
        tabela,
        an.CLASSES[nome],
        tipo,
        cmp.corte_fixo(settings, nome),
        settings.multiplos.min_pares,
    )


def preparar_calculo(
    tickers: Sequence[str],
    cadastro: pd.DataFrame,
    settings: Settings,
    base: dt.date,
    *,
    dir_raw: Path = DIR_RAW,
    dir_processed: Path = DIR_PROCESSED,
    dir_empresas: Path = DIR_EMPRESAS,
) -> list[str]:
    """Deixa séries e medidas no cache em disco, para a tela não calcular dezenas de empresas."""
    avisos: list[str] = []
    for ticker in tickers:
        _, _, motivo = _uma_empresa(
            ticker, cadastro, settings, base, dir_raw, dir_processed, dir_empresas
        )
        if motivo is not None:
            avisos.append(f"{ticker}: {motivo}")
    cmp.medir_com_cache(
        tickers,
        cadastro,
        settings,
        base,
        dir_raw=dir_raw,
        dir_processed=dir_processed,
        dir_empresas=dir_empresas,
    )
    return avisos
