import datetime as dt
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from conftest import DIR_FIXTURES_CVM, SessaoFalsa
from sintetico import dfp_completa, juntar
from valuation import __version__, cli
from valuation.cli import app
from valuation.config import Settings, carregar_settings
from valuation.data.cvm import url_cadastro, url_documento, url_fca
from valuation.perfil import registro as reg
from valuation.perfil.questionario import QUESTIONARIO


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


@pytest.fixture
def weg_sintetica(ambiente_offline: Path) -> Path:
    """WEGE3 baixada pela fixture e com as demonstrações trocadas por uma DFP sintética completa."""
    assert CliRunner().invoke(app, ["atualizar", "--tickers", "WEGE3"]).exit_code == 0
    pasta = ambiente_offline / "processed" / "cvm" / "5410"
    dados = juntar(dfp_completa(2024, cd_cvm=5410), dfp_completa(2025, cd_cvm=5410))
    dados.to_parquet(pasta / "demonstracoes.parquet", index=False)
    return ambiente_offline


def test_qa(weg_sintetica: Path) -> None:
    resultado = CliRunner().invoke(app, ["qa", "WEGE3"])
    assert resultado.exit_code == 0, resultado.output
    assert "Nenhum problema encontrado" in resultado.output
    assert "100%" in resultado.output
    assert (weg_sintetica / "processed" / "qa" / "qa_WEGE3.json").is_file()
    assert (weg_sintetica / "processed" / "cvm" / "5410" / "contas_padronizadas.parquet").is_file()


def test_qa_com_erro_sai_com_1(weg_sintetica: Path) -> None:
    pasta = weg_sintetica / "processed" / "cvm" / "5410"
    dados = juntar(dfp_completa(2024, cd_cvm=5410), dfp_completa(2025, cd_cvm=5410, BPA={"1": 999}))
    dados.to_parquet(pasta / "demonstracoes.parquet", index=False)
    resultado = CliRunner().invoke(app, ["qa", "WEGE3"])
    assert resultado.exit_code == 1
    assert "balanco_fecha" in resultado.output


def test_qa_sem_dados(ambiente_offline: Path) -> None:
    resultado = CliRunner().invoke(app, ["qa", "WEGE3"])
    assert resultado.exit_code == 1
    assert "valuation atualizar --tickers WEGE3" in " ".join(resultado.output.split())


def test_historico(weg_sintetica: Path) -> None:
    resultado = CliRunner().invoke(app, ["historico", "WEGE3", "--anos", "2"])
    assert resultado.exit_code == 0, resultado.output
    assert "LTM 12/2025" in resultado.output
    assert "Receita líquida" in resultado.output
    trimestral = CliRunner().invoke(app, ["historico", "WEGE3", "--trimestral"])
    assert trimestral.exit_code == 0, trimestral.output
    assert "4T25" in trimestral.output


def test_cobertura(weg_sintetica: Path) -> None:
    resultado = CliRunner().invoke(app, ["cobertura", "--tickers", "WEGE3"])
    assert resultado.exit_code == 0, resultado.output
    assert "Média geral: 100.0%" in resultado.output
    assert CliRunner().invoke(app, ["cobertura"]).exit_code == 1


@pytest.fixture
def caminho_perfil(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    caminho = tmp_path / "perfil" / "perfil_investidor.json"
    monkeypatch.setattr(cli, "CAMINHO_PERFIL", caminho)
    return caminho


def test_perfil_questionario_grava_json(caminho_perfil: Path) -> None:
    # "9" é inválido e deve ser perguntado de novo; depois, alternativa 3 em tudo (30 pontos).
    entrada = "9\n" + "3\n" * 10
    resultado = CliRunner().invoke(app, ["perfil"], input=entrada)
    assert resultado.exit_code == 0, resultado.output
    assert "Digite um número de 1 a 5" in resultado.output
    assert "Perfil: moderado (pontuação 30 de 50" in resultado.output
    assert "Selic + 5,0 p.p." in resultado.output
    registro = reg.ler(caminho_perfil)
    assert registro.perfil == "moderado"
    assert registro.data == dt.date.today()


def test_perfil_valido_nao_repergunta(caminho_perfil: Path) -> None:
    respostas = {p.chave: 5 for p in QUESTIONARIO}
    reg.gravar(reg.criar_registro(respostas, dt.date.today()), caminho_perfil)
    resultado = CliRunner().invoke(app, ["perfil"])
    assert resultado.exit_code == 0, resultado.output
    assert "Já existe um perfil válido" in resultado.output
    assert "arrojado" in resultado.output
    mostrar = CliRunner().invoke(app, ["perfil", "--mostrar"])
    assert mostrar.exit_code == 0
    assert "Margem de segurança" in mostrar.output


def test_perfil_refazer_e_vencido(caminho_perfil: Path) -> None:
    respostas = {p.chave: 5 for p in QUESTIONARIO}
    antigo = dt.date.today() - dt.timedelta(days=800)
    reg.gravar(reg.criar_registro(respostas, antigo), caminho_perfil)
    assert "vencido em" in CliRunner().invoke(app, ["perfil", "--mostrar"]).output
    resultado = CliRunner().invoke(app, ["perfil"], input="1\n" * 10)
    assert resultado.exit_code == 0, resultado.output
    assert "venceu em" in resultado.output
    assert reg.ler(caminho_perfil).perfil == "conservador"
    refeito = CliRunner().invoke(app, ["perfil", "--refazer"], input="5\n" * 10)
    assert refeito.exit_code == 0, refeito.output
    assert reg.ler(caminho_perfil).perfil == "arrojado"


def test_perfil_erros(caminho_perfil: Path) -> None:
    assert CliRunner().invoke(app, ["perfil", "--mostrar"]).exit_code == 1
    assert CliRunner().invoke(app, ["perfil", "--mostrar", "--refazer"]).exit_code == 1
    caminho_perfil.parent.mkdir(parents=True)
    caminho_perfil.write_text("{", encoding="utf-8")
    quebrado = CliRunner().invoke(app, ["perfil"])
    assert quebrado.exit_code == 1
    assert "--refazer" in quebrado.output
    refeito = CliRunner().invoke(app, ["perfil", "--refazer"], input="3\n" * 10)
    assert refeito.exit_code == 0, refeito.output
