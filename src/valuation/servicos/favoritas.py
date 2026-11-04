"""Adicionar e retirar favoritas, com a mesma validação da CLI: só tickers do universo."""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path

from valuation.config import ErroConfiguracao
from valuation.saida import favoritos as fav


def adicionar(ticker: str, universo: Collection[str], caminho: Path) -> list[str]:
    """Acrescenta ao fim da lista. Fora do universo ⇒ `ErroConfiguracao`."""
    if ticker not in universo:
        raise ErroConfiguracao(f"{ticker} está fora do universo: não pode ser favorita.")
    resultado = list(dict.fromkeys([*fav.carregar_favoritos(caminho), ticker]))
    fav.gravar_favoritos(resultado, caminho)
    return resultado


def remover(ticker: str, caminho: Path) -> list[str]:
    resultado = [t for t in fav.carregar_favoritos(caminho) if t != ticker]
    fav.gravar_favoritos(resultado, caminho)
    return resultado
