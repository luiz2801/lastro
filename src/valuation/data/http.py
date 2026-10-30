"""Download com cache em disco, retry e metadados.

Cada arquivo baixado fica ao lado de um `<nome>.meta.json` com URL, datas, hash e `Last-Modified`.
Dentro do TTL o cache é usado sem rede. Vencido o TTL, a revalidação usa `If-Modified-Since`:
se o servidor responder 304, o arquivo é mantido e só a data de verificação muda.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from valuation import __version__

logger = logging.getLogger(__name__)

TIMEOUT_SEGUNDOS = 60
TAMANHO_BLOCO = 1 << 20


class ErroDownload(Exception):
    """Falha ao baixar um arquivo (rede, HTTP ou conteúdo inválido)."""


class ArquivoNaoEncontrado(ErroDownload):
    """O servidor respondeu 404."""


class SessaoHttp(Protocol):
    def get(
        self, url: str, *, headers: dict[str, str], timeout: float, stream: bool
    ) -> requests.Response: ...


@dataclass(frozen=True)
class MetaDownload:
    url: str
    baixado_em: str
    verificado_em: str
    sha256: str
    tamanho_bytes: int
    last_modified: str | None


@dataclass(frozen=True)
class ArquivoBaixado:
    caminho: Path
    meta: MetaDownload
    do_cache: bool


def criar_sessao(tentativas: int = 4) -> requests.Session:
    """Sessão com retry exponencial para erros transitórios (429 e 5xx)."""
    retry = Retry(
        total=tentativas,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    sessao = requests.Session()
    sessao.mount("https://", HTTPAdapter(max_retries=retry))
    sessao.mount("http://", HTTPAdapter(max_retries=retry))
    sessao.headers["User-Agent"] = f"valuation/{__version__} (uso pessoal)"
    return sessao


def caminho_meta(destino: Path) -> Path:
    return destino.with_name(destino.name + ".meta.json")


def ler_meta(destino: Path) -> MetaDownload | None:
    caminho = caminho_meta(destino)
    if not (destino.is_file() and caminho.is_file()):
        return None
    try:
        return MetaDownload(**json.loads(caminho.read_text(encoding="utf-8")))
    except (ValueError, TypeError):
        logger.warning("Metadados ilegíveis, arquivo será baixado de novo: %s", caminho)
        return None


def _gravar_meta(destino: Path, meta: MetaDownload) -> None:
    caminho_meta(destino).write_text(
        json.dumps(asdict(meta), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def baixar(
    url: str,
    destino: Path,
    *,
    ttl: dt.timedelta,
    sessao: SessaoHttp,
    agora: dt.datetime,
    forcar: bool = False,
    validar: Callable[[Path], None] | None = None,
) -> ArquivoBaixado:
    """Baixa `url` para `destino`, usando o cache quando possível.

    `validar` recebe o arquivo temporário e deve levantar `ErroDownload` se o conteúdo for
    inválido (ex.: página de erro HTML no lugar de um zip). Se o download falhar e houver uma
    cópia vencida em cache, ela é usada com aviso; com `forcar=True` a falha é propagada.
    """
    meta = ler_meta(destino)
    if meta is not None and not forcar:
        verificado = dt.datetime.fromisoformat(meta.verificado_em)
        if agora - verificado < ttl:
            logger.debug("Cache válido: %s", destino)
            return ArquivoBaixado(destino, meta, do_cache=True)

    headers: dict[str, str] = {}
    if meta is not None and meta.last_modified and not forcar:
        headers["If-Modified-Since"] = meta.last_modified

    try:
        return _baixar_rede(url, destino, headers, sessao, agora, meta, validar)
    except ArquivoNaoEncontrado:
        raise
    except ErroDownload as e:
        if meta is None or forcar:
            raise
        logger.warning("%s. Usando cópia em cache de %s.", e, meta.baixado_em)
        return ArquivoBaixado(destino, meta, do_cache=True)


def _baixar_rede(
    url: str,
    destino: Path,
    headers: dict[str, str],
    sessao: SessaoHttp,
    agora: dt.datetime,
    meta_anterior: MetaDownload | None,
    validar: Callable[[Path], None] | None,
) -> ArquivoBaixado:
    logger.info("Baixando %s", url)
    try:
        resposta = sessao.get(url, headers=headers, timeout=TIMEOUT_SEGUNDOS, stream=True)
    except requests.RequestException as e:
        raise ErroDownload(f"Falha de rede ao baixar {url}: {e}") from e

    with resposta:
        if resposta.status_code == 304 and meta_anterior is not None:
            meta = MetaDownload(**{**asdict(meta_anterior), "verificado_em": agora.isoformat()})
            _gravar_meta(destino, meta)
            logger.debug("Não modificado desde o último download: %s", url)
            return ArquivoBaixado(destino, meta, do_cache=True)
        if resposta.status_code == 404:
            raise ArquivoNaoEncontrado(f"Arquivo não encontrado (HTTP 404): {url}")
        if resposta.status_code != 200:
            raise ErroDownload(f"HTTP {resposta.status_code} ao baixar {url}")

        destino.parent.mkdir(parents=True, exist_ok=True)
        temporario = destino.with_name(destino.name + ".parcial")
        hash_ = hashlib.sha256()
        tamanho = 0
        try:
            with temporario.open("wb") as f:
                for bloco in resposta.iter_content(TAMANHO_BLOCO):
                    f.write(bloco)
                    hash_.update(bloco)
                    tamanho += len(bloco)
            if validar is not None:
                validar(temporario)
        except requests.RequestException as e:
            temporario.unlink(missing_ok=True)
            raise ErroDownload(f"Download interrompido de {url}: {e}") from e
        except BaseException:
            temporario.unlink(missing_ok=True)
            raise
        os.replace(temporario, destino)

    meta = MetaDownload(
        url=url,
        baixado_em=agora.isoformat(),
        verificado_em=agora.isoformat(),
        sha256=hash_.hexdigest(),
        tamanho_bytes=tamanho,
        last_modified=resposta.headers.get("Last-Modified"),
    )
    _gravar_meta(destino, meta)
    return ArquivoBaixado(destino, meta, do_cache=False)
