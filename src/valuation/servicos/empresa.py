"""Cadastro e padronização contábil de uma empresa."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from valuation.config import (
    CAMINHO_CADASTRO_MANUAL,
    DIR_EMPRESAS,
    DIR_PROCESSED,
    DIR_RAW,
    Settings,
)
from valuation.contabil import ErroContabil
from valuation.contabil import nao_financeiras as nf
from valuation.contabil import padronizacao as pad
from valuation.contabil.moeda import detectar_moeda
from valuation.data import cadastro as cad
from valuation.data.http import SessaoHttp
from valuation.projecao import premissas as pm


@dataclass(frozen=True)
class Padronizada:
    empresa: cad.Empresa
    plano: pad.PlanoContas
    selecionadas: pd.DataFrame
    contas: pd.DataFrame
    moeda: str
    premissas: pm.PremissasEmpresa
    caminho_premissas: Path
    avisos: list[str] = field(default_factory=list)

    @property
    def ajustes(self) -> nf.AjustesContabeis:
        return pm.ajustes_contabeis(self.premissas.ajustes)


def carregar_cadastro(
    settings: Settings,
    data_base: dt.date,
    forcar: bool,
    *,
    sessao: SessaoHttp,
    agora: dt.datetime,
    dir_raw: Path = DIR_RAW,
    dir_processed: Path = DIR_PROCESSED,
    caminho_manual: Path = CAMINHO_CADASTRO_MANUAL,
) -> pd.DataFrame:
    """Cadastro de companhias, respeitando o TTL de `cache_ttl_horas.cvm` (salvo `forcar`)."""
    return cad.atualizar_cadastro(
        ano=data_base.year,
        data_ref=data_base,
        dir_raw=dir_raw,
        dir_processed=dir_processed,
        caminho_manual=caminho_manual,
        ttl=dt.timedelta(hours=settings.cache_ttl_horas.cvm),
        sessao=sessao,
        agora=agora,
        forcar=forcar,
    )


def padronizar(
    ticker: str,
    cadastro: pd.DataFrame,
    *,
    dir_processed: Path = DIR_PROCESSED,
    dir_empresas: Path = DIR_EMPRESAS,
) -> Padronizada:
    """Padroniza as demonstrações de `ticker` e grava `contas_padronizadas.parquet`.

    Usa `config/empresas/{TICKER}.yaml` se existir (mapeamento extra, consolidado, moeda); senão,
    as premissas padrão. Se falhar depois de um aviso, ele segue nas notas da exceção
    (`__notes__`), para quem chama poder mostrá-lo junto do erro.
    """
    empresa = cad.empresa_por_ticker(cadastro, ticker)
    tipo = empresa.tipo_modelo
    if tipo not in ("nao_financeira", "financeira"):
        raise ErroContabil(
            f"{', '.join(empresa.tickers)} é {tipo}: a v1 não avalia esse tipo "
            "(holdings exigem NAV/SOTP; ver seção 1 do CLAUDE.md)."
        )
    normalizado = cad.normalizar_ticker(ticker)
    caminho = pm.caminho_premissas(normalizado, dir_empresas)
    if caminho.is_file():
        premissas = pm.carregar_premissas(caminho)
        pm.conferir_cadastro(premissas, empresa.tickers, tipo)
    else:
        premissas = pm.premissas_padrao(normalizado, tipo, empresa.tickers)
    plano = pad.carregar_mapeamento(tipo=tipo, extra=premissas.ajustes.mapeamento_extra)
    try:
        demonstracoes = pad.ler_demonstracoes(dir_processed, empresa.cd_cvm)
    except FileNotFoundError as e:
        raise ErroContabil(
            f"{e.filename} não existe. Rode `valuation atualizar --tickers {ticker}`."
        ) from e
    avisos: list[str] = []
    consolidado = premissas.ajustes.consolidado
    if consolidado and not demonstracoes["consolidado"].any():
        avisos.append(
            f"{normalizado} só publica demonstrações individuais: usadas no lugar das consolidadas."
        )
        consolidado = False
    try:
        selecionadas = pad.selecionar_reapresentacoes(demonstracoes, consolidado=consolidado)
        moeda = detectar_moeda(selecionadas, premissas.moeda_relatorio)
        contas = pad.padronizar(selecionadas, plano, ticker=normalizado)
        contas.to_parquet(pad.caminho_padronizadas(dir_processed, empresa.cd_cvm), index=False)
    except Exception as e:
        for aviso in avisos:
            e.add_note(aviso)
        raise
    return Padronizada(empresa, plano, selecionadas, contas, moeda, premissas, caminho, avisos)
