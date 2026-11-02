"""Tickers favoritos (`config/favoritos.yaml`) e o último resultado gravado de cada um.

O "cache de resultados" dos favoritos é o próprio `resumo.csv` da pasta mais recente de
`saida/{TICKER}/`: nada novo é persistido, e a consulta não usa rede.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

from valuation.config import ConfigCsv, ErroConfiguracao
from valuation.saida.csv import INTERNACIONAL


def carregar_favoritos(caminho: Path) -> list[str]:
    """Lista de tickers em maiúsculas, sem repetição e na ordem do arquivo. Sem arquivo: vazia."""
    if not caminho.exists():
        return []
    bruto = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
    if not isinstance(bruto, dict) or set(bruto) - {"favoritos"}:
        raise ErroConfiguracao(f"{caminho}: esperado só a chave `favoritos` (lista de tickers).")
    lista = bruto.get("favoritos") or []
    if not isinstance(lista, list) or not all(isinstance(t, str) for t in lista):
        raise ErroConfiguracao(f"{caminho}: `favoritos` deve ser uma lista de tickers.")
    return list(dict.fromkeys(t.strip().upper() for t in lista if t.strip()))


def gravar_favoritos(tickers: list[str], caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    cabecalho = "# Tickers favoritos (`valuation favoritos`). Edite à mão ou pelos comandos.\n"
    corpo = yaml.safe_dump({"favoritos": tickers}, allow_unicode=True, sort_keys=False)
    caminho.write_text(cabecalho + corpo, encoding="utf-8")


@dataclass(frozen=True)
class ResumoFavorito:
    ticker: str
    data_base: dt.date
    perfil: str
    preco: float | None
    valor_ponderado: float | None
    preco_maximo_compra: float | None
    upside: float | None
    n_avisos: int

    def idade_dias(self, hoje: dt.date) -> int:
        return (hoje - self.data_base).days


def _numero(linha: pd.Series, coluna: str) -> float | None:
    valor = linha.get(coluna)
    return None if valor is None or pd.isna(valor) else float(valor)


def _ler_resumo(caminho: Path, config: ConfigCsv) -> pd.DataFrame:
    for cfg in (config, INTERNACIONAL):
        df = pd.read_csv(caminho, sep=cfg.separador, decimal=cfg.decimal, encoding=cfg.encoding)
        if "ticker" in df.columns:
            return df
    raise ErroConfiguracao(f"{caminho}: sem a coluna `ticker`; não é um resumo.csv.")


def ultimo_resumo(ticker: str, dir_saida: Path, config: ConfigCsv) -> ResumoFavorito | None:
    """`resumo.csv` da pasta de data mais recente de `saida/{ticker}/`; `None` se não houver."""
    pastas = sorted(
        (p for p in (dir_saida / ticker).glob("*") if (p / "resumo.csv").is_file()),
        reverse=True,
    )
    if not pastas:
        return None
    linha = _ler_resumo(pastas[0] / "resumo.csv", config).iloc[0]
    avisos = linha.get("avisos")
    n_avisos = 0 if avisos is None or pd.isna(avisos) else len(str(avisos).split(" | "))
    return ResumoFavorito(
        ticker=ticker,
        data_base=dt.date.fromisoformat(str(linha["data_base"])),
        perfil=str(linha["perfil"]),
        preco=_numero(linha, "preco"),
        valor_ponderado=_numero(linha, "valor_ponderado"),
        preco_maximo_compra=_numero(linha, "preco_maximo_compra"),
        upside=_numero(linha, "upside"),
        n_avisos=n_avisos,
    )
