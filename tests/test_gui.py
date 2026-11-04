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


def _com_series(raiz: Path) -> None:
    """Série sintética: 9 ações a R$ 10; DFP sintética tem lucro 9 e PL 100 (5 de minoritários)."""
    _com_dados(raiz)
    precos = raiz / "raw" / "precos"
    precos.mkdir(parents=True)
    indice = pd.date_range(end="2026-10-30", periods=24, freq="ME", name="data")
    pd.DataFrame({"close": 10.0, "adj_close": 10.0, "volume": 1.0}, index=indice).to_parquet(
        precos / "yf_WEGE3.SA_20161030_20261030.parquet"
    )
    pd.DataFrame(
        {"fator": []}, index=pd.DatetimeIndex([], name="data"), dtype="float64"
    ).to_parquet(precos / "splits_WEGE3.SA.parquet")
    pd.DataFrame(
        {
            "dt_refer": [indice[12]],
            "qt_acao_ordin_cap_integr": [9],
            "qt_acao_pref_cap_integr": [0],
            "qt_acao_total_cap_integr": [9],
            "qt_acao_ordin_tesouro": [0],
            "qt_acao_pref_tesouro": [0],
            "qt_acao_total_tesouro": [0],
        }
    ).to_parquet(raiz / "processed" / "cvm" / "5410" / "composicao_capital.parquet")


def _metricas(at: AppTest) -> dict[str, str]:
    return {m.label: m.value for m in at.metric}


def test_aba_geral_mostra_cartoes_e_graficos_do_cache(ambiente: Path) -> None:
    _com_series(ambiente)
    at = _abrir("WEGE3")
    assert not at.exception
    metricas = _metricas(at)
    assert metricas["Preço"] == "R$ 10,00"
    assert metricas["Market cap (R$ mi)"] == "0,00"  # 90 reais: formato em milhões, sem casas
    assert metricas["Margem líquida"] == "9,00%"
    assert len(at.get("plotly_chart")) == 2
    assert "ponto(s) fora da referência" in _textos(at)
    assert "A CVM só publica a quantidade de ações" in _textos(at)  # lacuna com o motivo


def test_seletores_trocam_sem_rede(ambiente: Path) -> None:
    _com_series(ambiente)
    at = _abrir("WEGE3")
    at.selectbox(key="referencia_serie").select("media_simples").run()
    assert not at.exception
    assert "sensível a extremos" in _textos(at)
    at.selectbox(key="indicador_serie").select("p_vp").run()
    assert not at.exception
    at.radio(key="janela_serie").set_value("5 anos").run()
    at.radio(key="periodo_cotacao").set_value("Máximo").run()
    at.radio(key="visao_indicadores").set_value("Histórico").run()
    assert not at.exception
    tabela = at.dataframe[0].value
    assert "Margem líquida" in tabela.index


def test_sem_cotacao_em_disco_nao_vai_a_rede(ambiente: Path) -> None:
    _com_dados(ambiente)
    at = _abrir("WEGE3")
    assert not at.exception
    assert "sem cotação de WEGE3 em disco" in _textos(at)
    assert _metricas(at)["Margem líquida"] == "9,00%"  # indicadores contábeis seguem


def test_comparacao_com_ibovespa_so_no_clique_e_com_o_que_esta_em_disco(ambiente: Path) -> None:
    _com_series(ambiente)
    at = _abrir("WEGE3")
    colunas = at.dataframe[0].value.columns
    assert not any("Ibovespa" in c for c in colunas)
    at.button(key="botao_ibovespa_WEGE3").click().run()
    assert not at.exception
    assert "Ibovespa (n = 1)" in at.dataframe[0].value.columns


def test_comando_series_baixa_e_avisa(ambiente: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _com_dados(ambiente)
    monkeypatch.setattr(cli, "DIR_RAW", ambiente / "raw")
    monkeypatch.setattr(cli, "DIR_PROCESSED", ambiente / "processed")
    monkeypatch.setattr(cli, "criar_sessao", lambda: object())
    monkeypatch.setattr(cli, "_carregar_cadastro", lambda *_: CADASTRO)
    monkeypatch.setattr(cli.hm, "baixar_series", lambda *a, **k: ["XXXX4 sem cotação"])
    resultado = CliRunner().invoke(app, ["series", "wege3"])
    assert resultado.exit_code == 0, resultado.output
    assert "XXXX4 sem cotação" in resultado.output
    assert "Séries de WEGE3 gravadas" in " ".join(resultado.output.split())


def _rodada_dcf(raiz: Path) -> Path:
    pasta = raiz / "saida" / "WEGE3" / "2026-10-30"
    linha = {
        "ticker": "WEGE3",
        "data_base": "2026-10-30",
        "perfil": "moderado",
        "preco": 40.0,
        "valor_pessimista": 30.25,
        "valor_base": 50.5,
        "valor_otimista": 70.75,
        "valor_ponderado": 50.5,
        "preco_maximo_compra": 40.4,
        "upside": 0.2625,
        "ke_implicito": 0.14,
        "hurdle": 0.20,
        "wacc": 0.13,
        "g": 0.05,
        "vt_sobre_ev": 0.80,
        "avisos": "aviso gravado na rodada",
    }
    gravar_csv(pd.DataFrame([linha]), pasta / "resumo.csv", BR)
    gravar_csv(
        pd.DataFrame(
            {
                "item": ["valor_da_firma", "divida_bruta", "equity", "acoes", "valor_por_acao"],
                "base": [200.0, -50.0, 150.0, 3.0, 50.0],
            }
        ),
        pasta / "ponte_ev_equity.csv",
        BR,
    )
    gravar_csv(
        pd.DataFrame(
            {
                "componente": ["ke", "wacc", "moeda", "aviso"],
                "valor": [0.16, 0.13, None, None],
                "detalhe": ["", "", "BRL", "aviso do custo de capital"],
            }
        ),
        pasta / "wacc.csv",
        BR,
    )
    gravar_csv(pd.DataFrame({"ano": [2027], "fcff": [10.0]}), pasta / "projecao_base.csv", BR)
    return pasta


def test_aba_valuation_mostra_os_numeros_do_resumo(ambiente: Path) -> None:
    _com_series(ambiente)
    _rodada_dcf(ambiente)
    at = _abrir("WEGE3")
    assert not at.exception
    metricas = _metricas(at)
    assert metricas["Pessimista"] == "R$ 30,25"
    assert metricas["Base"] == "R$ 50,50"
    assert metricas["Otimista"] == "R$ 70,75"
    assert metricas["Valor ponderado"] == "R$ 50,50"
    assert metricas["Preço máximo de compra"] == "R$ 40,40"
    assert metricas["Upside"] == "26,25%"
    assert metricas["Retorno esperado x hurdle"] == "14,00% x 20,00%"
    assert len(at.get("plotly_chart")) == 4  # cotação, múltiplo, football e ponte
    texto = _textos(at)
    assert "aviso gravado na rodada" in texto and "aviso do custo de capital" in texto
    assert "qa.json não existe" in texto  # rodada incompleta avisa, sem inventar
    checagens = next(d.value for d in at.dataframe if "Checagem" in d.value.columns)
    resultado = dict(zip(checagens["Checagem"], checagens["Resultado"], strict=True))
    assert resultado["g < WACC"] == "✅ ok"
    assert resultado["VT / EV"] == "⚠️ atenção"  # 80% acima do alerta de 75%


def test_aba_valuation_sem_rodada_oferece_o_botao(
    ambiente: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _com_dados(ambiente)
    at = _abrir("WEGE3")
    assert "ainda não tem valuation" in _textos(at)
    chamadas: list[object] = []

    def registra(comandos: object, ao_ler: object = None) -> atu.Execucao:
        chamadas.append(comandos)
        return atu.Execucao(False, ["sem perfil"], "valuation rodar WEGE3")

    monkeypatch.setattr(atu, "executar", registra)
    at.button(key="rodar_valuation").click().run()
    assert not at.exception
    assert chamadas == [atu.rodar_valuation("WEGE3")]
    assert "Falhou em `valuation rodar WEGE3`" in _textos(at)


def test_nenhum_modulo_da_gui_esconde_um_pacote() -> None:
    """O Streamlit põe a pasta do script no `sys.path`: `gui/valuation.py` esconderia o pacote."""
    nomes = {a.stem for a in Path(APP).parent.glob("*.py")}
    assert not nomes & {"valuation", "streamlit", "plotly", "pandas", "numpy"}


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


def test_grade_de_balanco_com_o_motivo_de_cada_lacuna(ambiente: Path) -> None:
    _com_dados(ambiente)
    at = _abrir("WEGE3")
    assert not at.exception
    rotulos = {m.label for m in at.metric}
    assert {
        "Dívida bruta / PL",
        "Cobertura de juros",
        "Liquidez corrente",
        "Caixa / Ativos",
    } <= rotulos


def test_historico_do_balanco_troca_o_indicador_sem_rede(ambiente: Path) -> None:
    _com_dados(ambiente)
    at = _abrir("WEGE3")
    at.radio(key="visao_indicadores").set_value("Histórico").run()
    assert not at.exception
    at.selectbox(key="indicador_balanco").set_value("caixa_aplicacoes").run()
    assert not at.exception
    assert any("sem referência" in c.value for c in at.caption)
