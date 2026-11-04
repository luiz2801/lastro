"""`servicos/empresa.py`: cadastro e padronização sem terminal e sem rede."""

import datetime as dt
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest

from conftest import DIR_FIXTURES_CVM, SessaoFalsa
from sintetico import dfp_completa, juntar
from valuation import cli
from valuation.config import carregar_settings
from valuation.contabil import ErroContabil
from valuation.data.cvm import url_cadastro, url_fca
from valuation.servicos import empresa as emp

AGORA = dt.datetime(2026, 10, 30, tzinfo=dt.UTC)
BASE = dt.date(2026, 10, 30)
AVISO_INDIVIDUAL = "WEGE3 só publica demonstrações individuais"


@pytest.fixture
def cadastro(
    tmp_path: Path, sessao_falsa: SessaoFalsa, zip_cvm: Callable[[str], Path]
) -> pd.DataFrame:
    rotas = sessao_falsa.rotas
    rotas[url_cadastro()] = (200, (DIR_FIXTURES_CVM / "cad_cia_aberta.csv").read_bytes(), {})
    for ano in (2025, 2026):
        rotas[url_fca(ano)] = (200, zip_cvm(f"fca_cia_aberta_{ano}").read_bytes(), {})
    return emp.carregar_cadastro(
        carregar_settings(),
        BASE,
        False,
        sessao=sessao_falsa,
        agora=AGORA,
        dir_raw=tmp_path / "raw",
        dir_processed=tmp_path / "processed",
        caminho_manual=tmp_path / "manual.csv",
    )


def _gravar(tmp_path: Path, dados: pd.DataFrame) -> None:
    pasta = tmp_path / "processed" / "cvm" / "5410"
    pasta.mkdir(parents=True, exist_ok=True)
    dados.to_parquet(pasta / "demonstracoes.parquet", index=False)


def _padronizar(tmp_path: Path, cadastro: pd.DataFrame) -> emp.Padronizada:
    return emp.padronizar(
        "WEGE3",
        cadastro,
        dir_processed=tmp_path / "processed",
        dir_empresas=tmp_path / "empresas",
    )


def test_carregar_cadastro_grava_nos_diretorios_recebidos(
    tmp_path: Path, cadastro: pd.DataFrame
) -> None:
    assert {"PETR4", "WEGE3"} <= set(cadastro["ticker"])
    assert (tmp_path / "processed" / "cadastro.parquet").is_file()


def test_padronizar_consolidado_nao_avisa(tmp_path: Path, cadastro: pd.DataFrame) -> None:
    _gravar(tmp_path, juntar(dfp_completa(2024), dfp_completa(2025)))
    p = _padronizar(tmp_path, cadastro)
    assert p.avisos == []
    assert p.moeda == "BRL"
    assert p.empresa.cd_cvm == 5410
    assert p.ajustes == cli.pm.ajustes_contabeis(p.premissas.ajustes)
    gravado = pd.read_parquet(
        tmp_path / "processed" / "cvm" / "5410" / "contas_padronizadas.parquet"
    )
    assert len(gravado) == len(p.contas) > 0


def test_padronizar_individual_devolve_aviso_no_retorno(
    tmp_path: Path, cadastro: pd.DataFrame, capsys: pytest.CaptureFixture[str]
) -> None:
    _gravar(tmp_path, dfp_completa(2025).assign(consolidado=False))
    p = _padronizar(tmp_path, cadastro)
    assert len(p.avisos) == 1
    assert p.avisos[0].startswith(AVISO_INDIVIDUAL)
    assert not p.contas.empty
    assert capsys.readouterr().out == ""


def test_padronizar_sem_demonstracoes_pede_atualizar(
    tmp_path: Path, cadastro: pd.DataFrame
) -> None:
    with pytest.raises(ErroContabil, match="valuation atualizar --tickers WEGE3"):
        _padronizar(tmp_path, cadastro)


def test_padronizar_recusa_holding(tmp_path: Path, cadastro: pd.DataFrame) -> None:
    alterado = cadastro.assign(tipo_modelo="holding")
    with pytest.raises(ErroContabil, match="NAV/SOTP"):
        _padronizar(tmp_path, alterado)


def test_erro_depois_do_aviso_leva_o_aviso_nas_notas(
    tmp_path: Path, cadastro: pd.DataFrame
) -> None:
    dados = juntar(
        dfp_completa(2024).assign(consolidado=False, moeda="REAL"),
        dfp_completa(2025).assign(consolidado=False, moeda="DÓLAR"),
    )
    _gravar(tmp_path, dados)
    with pytest.raises(ErroContabil, match="Moeda muda") as erro:
        _padronizar(tmp_path, cadastro)
    assert erro.value.__notes__[0].startswith(AVISO_INDIVIDUAL)


def test_cli_imprime_o_aviso_antes_de_repassar_o_erro(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def falha(*_: object, **__: object) -> emp.Padronizada:
        erro = ErroContabil("Moeda muda")
        erro.add_note("aviso que precisa aparecer")
        raise erro

    monkeypatch.setattr(cli.emp, "padronizar", falha)
    with pytest.raises(ErroContabil, match="Moeda muda"):
        cli._padronizar("WEGE3", carregar_settings(), pd.DataFrame())
    assert "aviso que precisa aparecer" in capsys.readouterr().out


def test_servicos_sem_dependencia_de_terminal() -> None:
    pasta = Path(emp.__file__).parent
    for arquivo in pasta.rglob("*.py"):
        texto = arquivo.read_text(encoding="utf-8")
        for proibido in ("rich", "typer", "console.print"):
            assert proibido not in texto, f"{arquivo.name} contém {proibido!r}"
