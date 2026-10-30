import datetime as dt
import hashlib
import json
import logging
from pathlib import Path

import pytest
import requests

from conftest import SessaoFalsa
from valuation.data.http import ArquivoNaoEncontrado, ErroDownload, baixar, caminho_meta

URL = "https://exemplo.test/arquivo.zip"
T0 = dt.datetime(2026, 10, 30, 12, 0, tzinfo=dt.UTC)
TTL = dt.timedelta(hours=24)
LM = "Sun, 25 Oct 2026 10:19:28 GMT"


def test_download_grava_arquivo_e_meta(tmp_path: Path, sessao_falsa: SessaoFalsa) -> None:
    sessao_falsa.rotas[URL] = (200, b"conteudo", {"Last-Modified": LM})
    destino = tmp_path / "sub" / "arquivo.zip"

    r = baixar(URL, destino, ttl=TTL, sessao=sessao_falsa, agora=T0)

    assert not r.do_cache
    assert destino.read_bytes() == b"conteudo"
    meta = json.loads(caminho_meta(destino).read_text(encoding="utf-8"))
    assert meta["sha256"] == hashlib.sha256(b"conteudo").hexdigest()
    assert meta["tamanho_bytes"] == 8
    assert meta["last_modified"] == LM
    assert meta["url"] == URL


def test_cache_dentro_do_ttl_nao_acessa_rede(tmp_path: Path, sessao_falsa: SessaoFalsa) -> None:
    sessao_falsa.rotas[URL] = (200, b"x", {})
    destino = tmp_path / "arquivo.zip"
    baixar(URL, destino, ttl=TTL, sessao=sessao_falsa, agora=T0)

    r = baixar(URL, destino, ttl=TTL, sessao=sessao_falsa, agora=T0 + dt.timedelta(hours=1))

    assert r.do_cache
    assert len(sessao_falsa.chamadas) == 1


def test_ttl_vencido_revalida_com_if_modified_since(
    tmp_path: Path, sessao_falsa: SessaoFalsa
) -> None:
    sessao_falsa.rotas[URL] = (200, b"x", {"Last-Modified": LM})
    destino = tmp_path / "arquivo.zip"
    baixar(URL, destino, ttl=TTL, sessao=sessao_falsa, agora=T0)
    depois = T0 + dt.timedelta(days=2)

    r = baixar(URL, destino, ttl=TTL, sessao=sessao_falsa, agora=depois)

    assert r.do_cache
    assert sessao_falsa.chamadas[-1][1] == {"If-Modified-Since": LM}
    assert r.meta.baixado_em == T0.isoformat()
    assert r.meta.verificado_em == depois.isoformat()


def test_forcar_ignora_cache(tmp_path: Path, sessao_falsa: SessaoFalsa) -> None:
    sessao_falsa.rotas[URL] = (200, b"v1", {"Last-Modified": LM})
    destino = tmp_path / "arquivo.zip"
    baixar(URL, destino, ttl=TTL, sessao=sessao_falsa, agora=T0)
    sessao_falsa.rotas[URL] = (200, b"v2", {"Last-Modified": LM})

    r = baixar(URL, destino, ttl=TTL, sessao=sessao_falsa, agora=T0, forcar=True)

    assert not r.do_cache
    assert destino.read_bytes() == b"v2"
    assert sessao_falsa.chamadas[-1][1] == {}


def test_404_levanta_arquivo_nao_encontrado(tmp_path: Path, sessao_falsa: SessaoFalsa) -> None:
    with pytest.raises(ArquivoNaoEncontrado, match="404"):
        baixar(URL, tmp_path / "a.zip", ttl=TTL, sessao=sessao_falsa, agora=T0)


def test_falha_sem_cache_propaga(tmp_path: Path, sessao_falsa: SessaoFalsa) -> None:
    sessao_falsa.rotas[URL] = (503, b"", {})
    with pytest.raises(ErroDownload, match="HTTP 503"):
        baixar(URL, tmp_path / "a.zip", ttl=TTL, sessao=sessao_falsa, agora=T0)


def test_falha_com_cache_vencido_usa_copia_com_aviso(
    tmp_path: Path, sessao_falsa: SessaoFalsa, caplog: pytest.LogCaptureFixture
) -> None:
    sessao_falsa.rotas[URL] = (200, b"antigo", {})
    destino = tmp_path / "a.zip"
    baixar(URL, destino, ttl=TTL, sessao=sessao_falsa, agora=T0)
    sessao_falsa.rotas[URL] = (500, b"", {})

    with caplog.at_level(logging.WARNING):
        r = baixar(URL, destino, ttl=TTL, sessao=sessao_falsa, agora=T0 + dt.timedelta(days=9))

    assert r.do_cache
    assert destino.read_bytes() == b"antigo"
    assert "cópia em cache" in caplog.text


def test_falha_com_forcar_propaga_mesmo_com_cache(
    tmp_path: Path, sessao_falsa: SessaoFalsa
) -> None:
    sessao_falsa.rotas[URL] = (200, b"antigo", {})
    destino = tmp_path / "a.zip"
    baixar(URL, destino, ttl=TTL, sessao=sessao_falsa, agora=T0)
    sessao_falsa.rotas[URL] = (500, b"", {})

    with pytest.raises(ErroDownload):
        baixar(URL, destino, ttl=TTL, sessao=sessao_falsa, agora=T0, forcar=True)


def test_validacao_falha_nao_deixa_arquivo(tmp_path: Path, sessao_falsa: SessaoFalsa) -> None:
    sessao_falsa.rotas[URL] = (200, b"<html>erro</html>", {})
    destino = tmp_path / "a.zip"

    def recusar(_: Path) -> None:
        raise ErroDownload("não é zip")

    with pytest.raises(ErroDownload, match="não é zip"):
        baixar(URL, destino, ttl=TTL, sessao=sessao_falsa, agora=T0, validar=recusar)
    assert list(tmp_path.iterdir()) == []


def test_erro_de_rede_vira_erro_download(tmp_path: Path) -> None:
    class SessaoQuebrada:
        def get(self, url: str, **_: object) -> requests.Response:
            raise requests.ConnectionError("sem rede")

    with pytest.raises(ErroDownload, match="sem rede"):
        baixar(URL, tmp_path / "a.zip", ttl=TTL, sessao=SessaoQuebrada(), agora=T0)  # type: ignore[arg-type]
