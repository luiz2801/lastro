"""GUI: fumaça com `AppTest`, sobre fixtures sintéticas e sem rede."""

from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from sintetico import dfp_completa, juntar
from valuation import cli
from valuation.cli import app
from valuation.config import ConfigCsv
from valuation.saida.csv import gravar_csv

pytest.importorskip("streamlit")

import streamlit as st
from streamlit.testing.v1 import AppTest

from valuation import config as cfg
from valuation.servicos import atualizacao as atu

APP = str(Path(cli.__file__).parent / "gui" / "app.py")
BR = ConfigCsv(separador=";", decimal=",", encoding="utf-8-sig")
UNIVERSO = """ticker;setor_cvm;tipo_modelo
WEGE3;Máquinas, Equipamentos, Veículos e Peças;nao_financeira
ITSA4;Bancos;holding
"""
CADASTRO = pd.DataFrame(
    [
        {
            "ticker": "WEGE3",
            "cnpj": "84.429.695/0001-11",
            "cd_cvm": 5410,
            "razao_social": "WEG S.A.",
            "nome_comercial": "WEG",
            "setor_cvm": "Máquinas",
            "tipo_modelo": "nao_financeira",
            "escala_acoes": 1,
            "especie": "ON",
            "acoes_por_unit": 0,
        }
    ]
)


@pytest.fixture
def ambiente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """O que a GUI lê do `config` aponta para `tmp_path`; a chamada à CLI é trocada."""
    (tmp_path / "universo.csv").write_text(UNIVERSO, encoding="utf-8")
    monkeypatch.setattr(cfg, "CAMINHO_UNIVERSO", tmp_path / "universo.csv")
    monkeypatch.setattr(cfg, "CAMINHO_FAVORITOS", tmp_path / "favoritos.yaml")
    monkeypatch.setattr(cfg, "DIR_RAW", tmp_path / "raw")
    monkeypatch.setattr(cfg, "DIR_PROCESSED", tmp_path / "processed")
    monkeypatch.setattr(cfg, "DIR_SAIDA", tmp_path / "saida")
    monkeypatch.setattr(cfg, "DIR_EMPRESAS", tmp_path / "empresas")

    def nao_chamar(*_: object, **__: object) -> atu.Execucao:
        raise AssertionError("a GUI chamou a rede sem pedido")

    monkeypatch.setattr(atu, "executar", nao_chamar)
    st.cache_data.clear()
    yield tmp_path
    st.cache_data.clear()


def _com_dados(raiz: Path) -> None:
    pasta = raiz / "processed" / "cvm" / "5410"
    pasta.mkdir(parents=True)
    CADASTRO.to_parquet(raiz / "processed" / "cadastro.parquet", index=False)
    juntar(dfp_completa(2024), dfp_completa(2025)).to_parquet(
        pasta / "demonstracoes.parquet", index=False
    )


def _abrir(ticker: str | None = None) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=30)
    if ticker:
        at.query_params["ticker"] = ticker
    return at.run()


def _textos(at: AppTest) -> str:
    partes = [
        *(e.value for e in at.error),
        *(e.value for e in at.warning),
        *(e.value for e in at.info),
        *(e.value for e in at.caption),
        *(e.value for e in at.title),
    ]
    return " ".join(partes)


def test_inicio_sem_favoritas(ambiente: Path) -> None:
    at = _abrir()
    assert not at.exception
    assert "Nenhuma favorita" in _textos(at)
    assert "não é recomendação" in _textos(at)


def test_inicio_mostra_favoritas_do_cache(ambiente: Path) -> None:
    (ambiente / "favoritos.yaml").write_text("favoritos: [WEGE3, ITSA4]\n", encoding="utf-8")
    linha = {
        "ticker": "WEGE3",
        "data_base": "2026-10-30",
        "perfil": "moderado",
        "preco": 40.0,
        "valor_ponderado": 50.5,
        "preco_maximo_compra": 40.4,
        "upside": 0.2625,
        "avisos": "um | dois",
    }
    gravar_csv(pd.DataFrame([linha]), ambiente / "saida/WEGE3/2026-10-30/resumo.csv", BR)
    at = _abrir()
    assert not at.exception
    tabela = at.dataframe[0].value.set_index("Ticker")
    assert tabela.loc["WEGE3", "Valor ponderado"] == "R$ 50,50"
    assert tabela.loc["WEGE3", "Upside"] == "26,2%"
    assert tabela.loc["WEGE3", "Avisos"] == "2"
    assert tabela.loc["ITSA4", "Última rodada"] == "sem rodada"
    assert tabela.loc["ITSA4", "Valor ponderado"] == "—"


def test_ticker_fora_do_universo(ambiente: Path) -> None:
    at = _abrir("ZZZZ3")
    assert not at.exception
    assert "fora do universo" in _textos(at)


def test_holding_fora_da_v1(ambiente: Path) -> None:
    at = _abrir("itsa4")
    assert not at.exception
    assert "fora da v1" in _textos(at)


def test_ativo_com_cache_abre_sem_rede(ambiente: Path) -> None:
    _com_dados(ambiente)
    at = _abrir("WEGE3")
    assert not at.exception
    texto = _textos(at)
    assert "WEGE3 — WEG" in texto
    assert "CVM:" in texto and "Preços: sem cache" in texto and "Valuation: sem cache" in texto


def test_ativo_sem_cache_baixa_com_erro_visivel_e_uma_tentativa(
    ambiente: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chamadas: list[object] = []

    def falha(comandos: object, ao_ler: object = None) -> atu.Execucao:
        chamadas.append(comandos)
        return atu.Execucao(False, ["sem internet"], "valuation atualizar")

    monkeypatch.setattr(atu, "executar", falha)
    at = _abrir("WEGE3")
    assert not at.exception
    assert len(chamadas) == 1
    assert "Falhou em `valuation atualizar`" in _textos(at)
    assert "sem internet" in " ".join(c.value for c in at.code)
    at.run()
    assert len(chamadas) == 1  # a página reexecuta sem repetir o download


def test_ativo_sem_cache_baixa_e_abre(ambiente: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def baixa(comandos: object, ao_ler: object = None) -> atu.Execucao:
        _com_dados(ambiente)
        return atu.Execucao(True, ["ok"])

    monkeypatch.setattr(atu, "executar", baixa)
    at = _abrir("WEGE3")
    assert not at.exception
    assert "WEGE3 — WEG" in _textos(at)


def test_botao_atualizar_chama_o_fluxo_da_cli(
    ambiente: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _com_dados(ambiente)
    at = _abrir("WEGE3")
    chamadas: list[object] = []

    def registra(comandos: object, ao_ler: object = None) -> atu.Execucao:
        chamadas.append(comandos)
        return atu.Execucao(False, ["yfinance fora do ar"], "valuation rodar WEGE3")

    monkeypatch.setattr(atu, "executar", registra)
    at.button(key="atualizar_ativo").click().run()
    assert not at.exception
    assert chamadas == [atu.atualizar_ativo("WEGE3")]
    assert "Falhou em `valuation rodar WEGE3`" in _textos(at)


def test_gui_sem_dependencia_de_terminal() -> None:
    pasta = Path(APP).parent
    for arquivo in pasta.rglob("*.py"):
        texto = arquivo.read_text(encoding="utf-8")
        for proibido in ("rich", "typer", "console.print"):
            assert proibido not in texto, f"{arquivo.name} contém {proibido!r}"


def test_comando_gui_sem_streamlit_explica_e_sai_com_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli.importlib.util, "find_spec", lambda _: None)
    resultado = CliRunner().invoke(app, ["gui"])
    assert resultado.exit_code == 1
    assert "uv sync --group gui" in resultado.output


def test_comando_gui_escuta_so_em_127_e_sem_telemetria(monkeypatch: pytest.MonkeyPatch) -> None:
    recebido: list[list[str]] = []
    monkeypatch.setattr(cli.subprocess, "call", lambda a: recebido.append(a) or 0)
    assert CliRunner().invoke(app, ["gui"]).exit_code == 0
    assert "--server.address=127.0.0.1" in recebido[0]
    assert "--browser.gatherUsageStats=false" in recebido[0]


def test_data_de_hoje_nao_entra_nos_servicos() -> None:
    pasta = Path(APP).parent.parent / "servicos"
    for arquivo in pasta.rglob("*.py"):
        assert ".today(" not in arquivo.read_text(encoding="utf-8"), arquivo.name
