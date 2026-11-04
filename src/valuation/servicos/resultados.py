"""Última rodada gravada de um ticker em `saida/`, lida sem recalcular nada e sem rede."""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from valuation.config import DIR_SAIDA, ConfigCsv
from valuation.saida import favoritos as fav


@dataclass(frozen=True)
class Resultado:
    """Arquivos da rodada; o que não pôde ser lido fica `None`, com o motivo em `avisos`.

    `avisos` fala da leitura dos arquivos; `avisos_rodada` é a coluna `avisos` do `resumo.csv`.
    """

    ticker: str
    data_base: dt.date
    pasta: Path
    modelo: str  # dcf | ddm
    resumo: pd.Series
    projecoes: dict[str, pd.DataFrame] = field(default_factory=dict)  # cenário -> tabela
    sensibilidades: dict[str, pd.DataFrame] = field(default_factory=dict)  # ex.: wacc_g
    wacc: pd.DataFrame | None = None
    ponte: pd.DataFrame | None = None
    multiplos_pares: pd.DataFrame | None = None
    multiplos_implicitos: pd.DataFrame | None = None
    qa: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None
    avisos_rodada: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def _matriz(tabela: pd.DataFrame) -> pd.DataFrame:
    """Desfaz o `gravar_matriz`: índice na 1ª coluna (`linha\\coluna`), rótulos numéricos."""
    primeira = str(tabela.columns[0])
    linha, _, coluna = primeira.partition("\\")
    matriz = tabela.set_index(primeira)
    matriz.index = pd.Index(matriz.index.astype(float), name=linha)
    rotulos = [float(str(c).replace(",", ".")) for c in matriz.columns]
    matriz.columns = pd.Index(rotulos, name=coluna)
    return matriz


def _csv(pasta: Path, nome: str, config: ConfigCsv, avisos: list[str]) -> pd.DataFrame | None:
    """Tabela de `nome`, ou `None` com o motivo; ausente é aviso de quem esperava o arquivo."""
    caminho = pasta / nome
    if not caminho.is_file():
        return None
    try:
        return fav.ler_csv_saida(caminho, config)
    except (ValueError, pd.errors.EmptyDataError, pd.errors.ParserError) as e:
        avisos.append(f"{nome} não pôde ser lido: {e}")
        return None


def _json(pasta: Path, nome: str, avisos: list[str]) -> dict[str, Any] | None:
    caminho = pasta / nome
    if not caminho.is_file():
        avisos.append(f"{nome} não existe em {pasta} (rodada incompleta ou antiga).")
        return None
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        avisos.append(f"{nome} não pôde ser lido: {e}")
        return None
    if not isinstance(dados, dict):
        avisos.append(f"{nome} não pôde ser lido: esperado um objeto JSON.")
        return None
    return dados


def _esperado(pasta: Path, nome: str, config: ConfigCsv, avisos: list[str]) -> pd.DataFrame | None:
    if not (pasta / nome).is_file():
        avisos.append(f"{nome} não existe em {pasta} (rodada incompleta ou antiga).")
    return _csv(pasta, nome, config, avisos)


def ultimo_resultado(
    ticker: str, config: ConfigCsv, *, dir_saida: Path = DIR_SAIDA
) -> Resultado | None:
    """Rodada da pasta de data mais recente com `resumo.csv`; `None` se o ticker não tem rodada.

    Pasta só com `wacc.csv` (comando `wacc`) não conta como rodada.
    """
    pasta = fav.pasta_mais_recente(ticker, dir_saida)
    if pasta is None:
        return None
    resumo = fav.ler_resumo(pasta / "resumo.csv", config).iloc[0]
    modelo = "dcf" if pd.isna(resumo.get("modelo")) else str(resumo["modelo"])
    avisos: list[str] = []

    projecoes: dict[str, pd.DataFrame] = {}
    for caminho in sorted(pasta.glob("projecao_*.csv")):
        tabela = _csv(pasta, caminho.name, config, avisos)
        if tabela is not None:
            projecoes[caminho.stem.removeprefix("projecao_")] = tabela
    if not projecoes:
        avisos.append(f"Nenhuma projeção legível em {pasta}.")

    sensibilidades: dict[str, pd.DataFrame] = {}
    for caminho in sorted(pasta.glob("sensibilidade_*.csv")):
        tabela = _csv(pasta, caminho.name, config, avisos)
        if tabela is None:
            continue
        try:
            sensibilidades[caminho.stem.removeprefix("sensibilidade_")] = _matriz(tabela)
        except ValueError as e:
            avisos.append(f"{caminho.name} não pôde ser lido: {e}")

    texto_avisos = resumo.get("avisos")
    return Resultado(
        ticker=ticker,
        data_base=dt.date.fromisoformat(str(resumo["data_base"])),
        pasta=pasta,
        modelo=modelo,
        resumo=resumo,
        projecoes=projecoes,
        sensibilidades=sensibilidades,
        wacc=_esperado(pasta, "wacc.csv", config, avisos),
        ponte=(
            _esperado(pasta, "ponte_ev_equity.csv", config, avisos) if modelo == "dcf" else None
        ),
        multiplos_pares=_csv(pasta, "multiplos_pares.csv", config, avisos),
        multiplos_implicitos=_csv(pasta, "multiplos_implicitos.csv", config, avisos),
        qa=_json(pasta, "qa.json", avisos),
        meta=_json(pasta, "meta.json", avisos),
        avisos_rodada=(
            [] if pd.isna(texto_avisos) else str(texto_avisos).split(fav.SEPARADOR_AVISOS)
        ),
        avisos=avisos,
    )
