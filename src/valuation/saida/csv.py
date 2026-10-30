"""Gravação de CSV no formato do `settings.csv` (pt-BR) ou internacional."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd

from valuation.config import ConfigCsv

FormatoCsv = Literal["br", "intl"]
INTERNACIONAL = ConfigCsv(separador=",", decimal=".", encoding="utf-8")


def gravar_csv(
    df: pd.DataFrame, caminho: Path, config: ConfigCsv, formato: FormatoCsv = "br"
) -> Path:
    """`br` usa o `settings.csv` (`;`, `,`, utf-8-sig); `intl` usa `,`, `.` e utf-8."""
    cfg = config if formato == "br" else INTERNACIONAL
    caminho.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(caminho, sep=cfg.separador, decimal=cfg.decimal, encoding=cfg.encoding, index=False)
    return caminho


def gravar_matriz(
    matriz: pd.DataFrame, caminho: Path, config: ConfigCsv, formato: FormatoCsv = "br"
) -> Path:
    """Matriz com índice e colunas numéricos: a 1ª coluna é o índice (`linha\\coluna` no
    cabeçalho) e os rótulos das colunas usam o separador decimal do formato."""
    cfg = config if formato == "br" else INTERNACIONAL
    df = matriz.rename(columns=lambda x: f"{x:.4f}".replace(".", cfg.decimal))
    df.columns.name = None
    df = df.rename_axis(f"{matriz.index.name}\\{matriz.columns.name}").reset_index()
    return gravar_csv(df, caminho, config, formato)
