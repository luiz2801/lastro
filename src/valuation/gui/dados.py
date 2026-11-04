"""Leituras da GUI: `st.cache_data` sobre `servicos/`, com o mtime dos arquivos na chave.

Nada aqui usa rede. Os caminhos são lidos de `config` na hora da chamada.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from valuation import config as cfg
from valuation.data import cadastro as cad
from valuation.projecao import premissas as pm
from valuation.saida import favoritos as fav
from valuation.servicos import cache as sc
from valuation.servicos import empresa as emp
from valuation.servicos import resultados as res
from valuation.universo import EmpresaUniverso, carregar_universo


def _mtime(caminho: Path) -> float:
    return caminho.stat().st_mtime if caminho.is_file() else 0.0


@st.cache_data(show_spinner=False)
def _settings(_mt: float, caminho: Path) -> cfg.Settings:
    return cfg.carregar_settings(caminho)


def settings() -> cfg.Settings:
    return _settings(_mtime(cfg.CAMINHO_SETTINGS), cfg.CAMINHO_SETTINGS)


@st.cache_data(show_spinner=False)
def _universo(_mt: float, caminho: Path) -> list[EmpresaUniverso]:
    return carregar_universo(caminho)


def universo() -> list[EmpresaUniverso]:
    return _universo(_mtime(cfg.CAMINHO_UNIVERSO), cfg.CAMINHO_UNIVERSO)


def favoritos() -> list[str]:
    return fav.carregar_favoritos(cfg.CAMINHO_FAVORITOS)


@st.cache_data(show_spinner=False)
def _resumo_favorito(
    ticker: str, _mt: float, dir_saida: Path, config: cfg.ConfigCsv
) -> fav.ResumoFavorito | None:
    return fav.ultimo_resumo(ticker, dir_saida, config)


def _mtime_resumo(ticker: str) -> float:
    pasta = fav.pasta_mais_recente(ticker, cfg.DIR_SAIDA)
    return 0.0 if pasta is None else _mtime(pasta / "resumo.csv")


def resumo_favorito(ticker: str) -> fav.ResumoFavorito | None:
    return _resumo_favorito(ticker, _mtime_resumo(ticker), cfg.DIR_SAIDA, settings().csv)


@st.cache_data(show_spinner=False)
def _resultado(
    ticker: str, _mt: float, dir_saida: Path, config: cfg.ConfigCsv
) -> res.Resultado | None:
    return res.ultimo_resultado(ticker, config, dir_saida=dir_saida)


def resultado(ticker: str) -> res.Resultado | None:
    return _resultado(ticker, _mtime_resumo(ticker), cfg.DIR_SAIDA, settings().csv)


@st.cache_data(show_spinner=False)
def _cadastro(_mt: float, dir_processed: Path) -> pd.DataFrame | None:
    return cad.ler_cadastro_processado(dir_processed)


def cadastro() -> pd.DataFrame | None:
    """Cadastro já gravado, sem rede; `None` se nunca foi baixado."""
    caminho = cfg.DIR_PROCESSED / "cadastro.parquet"
    return _cadastro(_mtime(caminho), cfg.DIR_PROCESSED)


def tem_demonstracoes(cd_cvm: int) -> bool:
    return sc.caminho_demonstracoes(cd_cvm, cfg.DIR_PROCESSED).is_file()


@st.cache_data(show_spinner=False)
def _padronizada(
    ticker: str,
    cadastro_atual: pd.DataFrame,
    _mt_dem: float,
    _mt_yaml: float,
    dir_processed: Path,
    dir_empresas: Path,
) -> emp.Padronizada:
    return emp.padronizar(
        ticker, cadastro_atual, dir_processed=dir_processed, dir_empresas=dir_empresas
    )


def padronizada(ticker: str, cadastro_atual: pd.DataFrame, cd_cvm: int) -> emp.Padronizada:
    return _padronizada(
        ticker,
        cadastro_atual,
        _mtime(sc.caminho_demonstracoes(cd_cvm, cfg.DIR_PROCESSED)),
        _mtime(pm.caminho_premissas(ticker, cfg.DIR_EMPRESAS)),
        cfg.DIR_PROCESSED,
        cfg.DIR_EMPRESAS,
    )


def estado_fontes(ticker: str, cd_cvm: int | None) -> list[sc.FonteCache]:
    return sc.estado_fontes(
        ticker,
        cd_cvm,
        dir_raw=cfg.DIR_RAW,
        dir_processed=cfg.DIR_PROCESSED,
        dir_saida=cfg.DIR_SAIDA,
    )


def invalidar() -> None:
    """Depois de uma atualização, tudo é lido de novo."""
    st.cache_data.clear()
