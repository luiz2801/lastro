import datetime as dt
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from conftest import DIR_FIXTURES_CVM, SessaoFalsa
from valuation import __version__, cli
from valuation.cli import app
from valuation.config import Settings, carregar_settings
from valuation.data.cvm import url_cadastro, url_documento, url_fca


def test_versao() -> None:
    resultado = CliRunner().invoke(app, ["versao"])
    assert resultado.exit_code == 0
    assert __version__ in resultado.stdout


@pytest.fixture
def ambiente_offline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sessao_falsa: SessaoFalsa,
    zip_cvm: Callable[[str], Path],
) -> Path:
    """CLI apontando para diretórios temporários e um servidor CVM em memória."""
    settings = carregar_settings().model_copy(
        update={"data_base": dt.date(2026, 10, 30), "historico_anos": 1}
    )

    def carregar() -> Settings:
        return settings

    monkeypatch.setattr(cli, "carregar_settings", carregar)
    monkeypatch.setattr(cli, "criar_sessao", lambda: sessao_falsa)
    monkeypatch.setattr(cli, "DIR_RAW", tmp_path / "raw")
    monkeypatch.setattr(cli, "DIR_PROCESSED", tmp_path / "processed")
    monkeypatch.setattr(cli, "CAMINHO_CADASTRO_MANUAL", tmp_path / "manual.csv")
    monkeypatch.setattr(cli, "CAMINHO_UNIVERSO", tmp_path / "universo.csv")

    rotas = sessao_falsa.rotas
    rotas[url_cadastro()] = (200, (DIR_FIXTURES_CVM / "cad_cia_aberta.csv").read_bytes(), {})
    for ano in (2025, 2026):
        rotas[url_fca(ano)] = (200, zip_cvm(f"fca_cia_aberta_{ano}").read_bytes(), {})
    rotas[url_documento("DFP", 2025)] = (200, zip_cvm("dfp_cia_aberta_2025").read_bytes(), {})
    rotas[url_documento("ITR", 2026)] = (200, zip_cvm("itr_cia_aberta_2026").read_bytes(), {})
    # ITR 2025 publicado, mas sem as companhias da fixture.
    rotas[url_documento("ITR", 2025)] = (200, zip_cvm("fca_cia_aberta_2025").read_bytes(), {})
    return tmp_path


def test_cadastro_buscar(ambiente_offline: Path) -> None:
    resultado = CliRunner().invoke(app, ["cadastro", "buscar", "petrobras"])
    assert resultado.exit_code == 0, resultado.output
    assert "PETR4" in resultado.output
    assert "9512" in resultado.output


def test_cadastro_buscar_sem_resultado(ambiente_offline: Path) -> None:
    resultado = CliRunner().invoke(app, ["cadastro", "buscar", "zzzzzz"])
    assert resultado.exit_code == 1
    assert "Nada encontrado" in resultado.output


def test_atualizar(ambiente_offline: Path) -> None:
    resultado = CliRunner().invoke(app, ["atualizar", "--tickers", "PETR4,PETR3,WEGE3"])
    assert resultado.exit_code == 0, resultado.output
    assert "DFP: 2025 a 2025 (ainda não publicado: 2026)" in resultado.output
    processado = ambiente_offline / "processed" / "cvm"
    assert sorted(p.name for p in processado.iterdir()) == ["5410", "9512"]
    weg = pd.read_parquet(processado / "5410" / "demonstracoes.parquet")
    assert not weg.empty


def test_atualizar_ticker_inexistente(ambiente_offline: Path) -> None:
    resultado = CliRunner().invoke(app, ["atualizar", "--tickers", "XPTO3"])
    assert resultado.exit_code == 1
    assert "XPTO3 não encontrado" in resultado.output


def test_atualizar_tudo_sem_universo(ambiente_offline: Path) -> None:
    resultado = CliRunner().invoke(app, ["atualizar", "--tudo"])
    assert resultado.exit_code == 1
    assert "não existe" in " ".join(resultado.output.split())


def test_atualizar_tudo_com_universo(ambiente_offline: Path) -> None:
    (ambiente_offline / "universo.csv").write_text("ticker;setor\nWEGE3;industria\n")
    resultado = CliRunner().invoke(app, ["atualizar", "--tudo"])
    assert resultado.exit_code == 0, resultado.output
    assert (ambiente_offline / "processed" / "cvm" / "5410").is_dir()


def test_atualizar_exige_uma_opcao() -> None:
    resultado = CliRunner().invoke(app, ["atualizar"])
    assert resultado.exit_code == 1
    assert "--tickers ou --tudo" in resultado.output
