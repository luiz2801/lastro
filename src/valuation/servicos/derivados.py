"""Cache em disco do que é caro de recalcular a partir do que já está em disco.

Sem rede. Tudo aqui é derivado e pode ser apagado: `data/processed/cvm/{cd_cvm}/derivados/`. Vale
só enquanto a chave bater, e a chave leva tudo que entra na conta: arquivos de entrada (caminho,
mtime e tamanho), parâmetros e o código do cálculo. Assim uma fórmula nova invalida o cache sozinha.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

PACOTES_DO_CALCULO = ("analise", "contabil", "data", "modelos", "servicos")


@lru_cache(maxsize=1)
def versao_codigo() -> str:
    """Hash do código que entra na conta: muda quando uma fórmula muda."""
    raiz = Path(__file__).resolve().parent.parent
    resumo = hashlib.sha256()
    for pacote in PACOTES_DO_CALCULO:
        for caminho in sorted((raiz / pacote).glob("*.py")):
            resumo.update(caminho.read_bytes())
    return resumo.hexdigest()


def assinatura(caminhos: Iterable[Path]) -> list[tuple[str, int, int]]:
    """(caminho, mtime em ns, tamanho) de cada arquivo; ausente entra com zeros, e também conta."""
    saida: list[tuple[str, int, int]] = []
    for caminho in sorted(set(caminhos)):
        if caminho.is_file():
            info = caminho.stat()
            saida.append((str(caminho), info.st_mtime_ns, info.st_size))
        else:
            saida.append((str(caminho), 0, 0))
    return saida


def chave(*partes: object) -> str:
    return hashlib.sha256(repr(partes).encode("utf-8")).hexdigest()


def pasta(dir_processed: Path, cd_cvm: int) -> Path:
    return dir_processed / "cvm" / str(cd_cvm) / "derivados"


def ler_json(caminho: Path, chave_esperada: str) -> dict[str, Any] | None:
    """Conteúdo do JSON, se existir, for legível e tiver a chave certa; senão `None`."""
    try:
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(bruto, dict) or bruto.get("chave") != chave_esperada:
        return None
    return bruto


def gravar_json(caminho: Path, chave_atual: str, dados: dict[str, Any]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps({**dados, "chave": chave_atual}), encoding="utf-8")
    os.replace(temporario, caminho)


def gravar_parquet(caminho: Path, tabela: pd.DataFrame) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(".tmp")
    tabela.to_parquet(temporario)
    os.replace(temporario, caminho)
