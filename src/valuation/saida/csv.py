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
