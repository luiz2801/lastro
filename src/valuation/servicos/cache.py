"""O que já existe em disco para um ativo e de quando é, sem rede."""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path

from valuation.config import DIR_PROCESSED, DIR_RAW, DIR_SAIDA
from valuation.data.precos import simbolo_yahoo
from valuation.saida import favoritos as fav


@dataclass(frozen=True)
class FonteCache:
    nome: str
    atualizado_em: dt.datetime | None  # em UTC; None = nada em disco

    def idade_dias(self, agora: dt.datetime) -> int | None:
        return None if self.atualizado_em is None else (agora - self.atualizado_em).days


def caminho_demonstracoes(cd_cvm: int, dir_processed: Path = DIR_PROCESSED) -> Path:
    return dir_processed / "cvm" / str(cd_cvm) / "demonstracoes.parquet"


def _do_arquivo(caminho: Path) -> dt.datetime | None:
    if not caminho.is_file():
        return None
    return dt.datetime.fromtimestamp(caminho.stat().st_mtime, dt.UTC)


def _ultimo_download(pasta: Path, padrao: str) -> dt.datetime | None:
    """Data mais recente dos `.meta.json` da pasta; meta ilegível é ignorado."""
    datas: list[dt.datetime] = []
    for caminho in pasta.glob(padrao):
        try:
            datas.append(dt.datetime.fromisoformat(json.loads(caminho.read_text())["baixado_em"]))
        except (ValueError, KeyError, TypeError, OSError):
            continue
    return max(datas, default=None)


def estado_fontes(
    ticker: str,
    cd_cvm: int | None,
    *,
    dir_raw: Path = DIR_RAW,
    dir_processed: Path = DIR_PROCESSED,
    dir_saida: Path = DIR_SAIDA,
) -> list[FonteCache]:
    """Última atualização de cada fonte do ativo: CVM, preços, macro e valuation."""
    resumo = None
    pasta = fav.pasta_mais_recente(ticker, dir_saida)
    if pasta is not None:
        resumo = _do_arquivo(pasta / "resumo.csv")
    cvm = None if cd_cvm is None else _do_arquivo(caminho_demonstracoes(cd_cvm, dir_processed))
    simbolo = simbolo_yahoo(ticker)
    return [
        FonteCache("CVM", cvm),
        FonteCache("Preços", _ultimo_download(dir_raw / "precos", f"yf_{simbolo}_*.meta.json")),
        FonteCache("Macro", _ultimo_download(dir_raw / "macro", "*.meta.json")),
        FonteCache("Valuation", resumo),
    ]
