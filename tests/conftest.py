from __future__ import annotations

import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import requests

DIR_FIXTURES_CVM = Path(__file__).parent / "fixtures" / "cvm"


def montar_zip(pasta: Path, destino: Path) -> Path:
    """Zipa os CSVs de `tests/fixtures/cvm/<pasta>` como o portal da CVM entrega."""
    with zipfile.ZipFile(destino, "w") as zf:
        for csv in sorted(pasta.glob("*.csv")):
            zf.write(csv, csv.name)
    return destino


@pytest.fixture
def zip_cvm(tmp_path: Path) -> Callable[[str], Path]:
    def _montar(nome: str) -> Path:
        return montar_zip(DIR_FIXTURES_CVM / nome, tmp_path / f"{nome}.zip")

    return _montar


def resposta(
    status: int, conteudo: bytes = b"", headers: dict[str, str] | None = None
) -> requests.Response:
    r = requests.Response()
    r.status_code = status
    r._content = conteudo
    r._content_consumed = True
    r.headers.update(headers or {})
    return r


@dataclass
class SessaoFalsa:
    """Servidor HTTP em memória: URL -> (status, conteúdo, headers)."""

    rotas: dict[str, tuple[int, bytes, dict[str, str]]] = field(default_factory=dict)
    chamadas: list[tuple[str, dict[str, str]]] = field(default_factory=list)

    def get(
        self, url: str, *, headers: dict[str, str], timeout: float, stream: bool
    ) -> requests.Response:
        self.chamadas.append((url, dict(headers)))
        if url not in self.rotas:
            return resposta(404)
        status, conteudo, cabecalhos = self.rotas[url]
        modificado_desde = headers.get("If-Modified-Since")
        if (
            status == 200
            and modificado_desde
            and modificado_desde == cabecalhos.get("Last-Modified")
        ):
            return resposta(304)
        return resposta(status, conteudo, cabecalhos)


@pytest.fixture
def sessao_falsa() -> SessaoFalsa:
    return SessaoFalsa()
