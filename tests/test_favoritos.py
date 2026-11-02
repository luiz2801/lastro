import datetime as dt
from pathlib import Path

import pytest
from rich.console import Console
from typer.testing import CliRunner

from valuation import cli
from valuation.cli import app
from valuation.config import ConfigCsv, ErroConfiguracao
from valuation.saida import favoritos as fav
from valuation.saida.csv import INTERNACIONAL
from valuation.universo import EmpresaUniverso, SetorCVM

BR = ConfigCsv()


def _resumo(
    dir_saida: Path, ticker: str, data: str, cfg: ConfigCsv = BR, avisos: str = "a | b"
) -> None:
    pasta = dir_saida / ticker / data
    pasta.mkdir(parents=True)
    num = lambda x: str(x).replace(".", cfg.decimal)  # noqa: E731
    linhas = [
        "ticker;data_base;perfil;preco;valor_ponderado;preco_maximo_compra;upside;avisos".replace(
            ";", cfg.separador
        ),
        cfg.separador.join(
            [ticker, data, "moderado", num(10.5), num(15.0), num(12.0), num(0.4286), f'"{avisos}"']
        ),
    ]
    (pasta / "resumo.csv").write_text("\n".join(linhas) + "\n", encoding=cfg.encoding)


def test_carregar_sem_arquivo_e_normalizacao(tmp_path: Path) -> None:
    caminho = tmp_path / "f.yaml"
    assert fav.carregar_favoritos(caminho) == []
    caminho.write_text("favoritos: [petr4, WEGE3, PETR4]\n", encoding="utf-8")
    assert fav.carregar_favoritos(caminho) == ["PETR4", "WEGE3"]


def test_carregar_chave_desconhecida_falha(tmp_path: Path) -> None:
    caminho = tmp_path / "f.yaml"
    caminho.write_text("outra: [PETR4]\n", encoding="utf-8")
    with pytest.raises(ErroConfiguracao, match="favoritos"):
        fav.carregar_favoritos(caminho)


def test_gravar_e_recarregar(tmp_path: Path) -> None:
    caminho = tmp_path / "sub" / "f.yaml"
    fav.gravar_favoritos(["VALE3", "ITUB4"], caminho)
    assert fav.carregar_favoritos(caminho) == ["VALE3", "ITUB4"]


def test_ultimo_resumo_pega_a_pasta_mais_recente(tmp_path: Path) -> None:
    _resumo(tmp_path, "PETR4", "2026-10-01")
    _resumo(tmp_path, "PETR4", "2026-10-30")
    r = fav.ultimo_resumo("PETR4", tmp_path, BR)
    assert r is not None
    assert r.data_base == dt.date(2026, 10, 30)
    assert r.valor_ponderado == pytest.approx(15.0)
    assert r.upside == pytest.approx(0.4286)
    assert r.n_avisos == 2
    assert r.idade_dias(dt.date(2026, 11, 2)) == 3


def test_ultimo_resumo_aceita_formato_internacional_e_sem_avisos(tmp_path: Path) -> None:
    _resumo(tmp_path, "VALE3", "2026-10-30", INTERNACIONAL, avisos="")
    r = fav.ultimo_resumo("VALE3", tmp_path, BR)
    assert r is not None
    assert r.preco == pytest.approx(10.5)
    assert r.n_avisos == 0


def test_ultimo_resumo_sem_rodada(tmp_path: Path) -> None:
    assert fav.ultimo_resumo("PETR4", tmp_path, BR) is None


@pytest.fixture
def ambiente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(cli, "CAMINHO_FAVORITOS", tmp_path / "favoritos.yaml")
    monkeypatch.setattr(cli, "DIR_SAIDA", tmp_path / "saida")
    monkeypatch.setattr(
        cli,
        "carregar_universo",
        lambda: [
            EmpresaUniverso("PETR4", SetorCVM.PETROLEO_E_GAS, "nao_financeira"),
            EmpresaUniverso("VALE3", SetorCVM.EXTRACAO_MINERAL, "nao_financeira"),
        ],
    )
    monkeypatch.setattr(cli.reg, "resolver_perfil", lambda *a, **k: None)
    monkeypatch.setattr(cli, "console", Console(width=220))
    return tmp_path


def test_cli_adicionar_remover_e_listar(ambiente: Path) -> None:
    runner = CliRunner()
    assert runner.invoke(app, ["favoritos", "adicionar", "petr4", "VALE3"]).exit_code == 0
    _resumo(ambiente / "saida", "PETR4", "2026-10-30")
    tabela = runner.invoke(app, ["favoritos"])
    assert tabela.exit_code == 0
    assert "PETR4" in tabela.stdout and "sem rodada" in tabela.stdout  # VALE3 sem rodada
    assert runner.invoke(app, ["favoritos", "remover", "VALE3"]).exit_code == 0
    assert fav.carregar_favoritos(ambiente / "favoritos.yaml") == ["PETR4"]


def test_cli_adicionar_fora_do_universo_e_remover_ausente(ambiente: Path) -> None:
    runner = CliRunner()
    assert runner.invoke(app, ["favoritos", "adicionar", "XXXX3"]).exit_code == 1
    assert runner.invoke(app, ["favoritos", "remover", "PETR4"]).exit_code == 1


def test_cli_lista_vazia_orienta(ambiente: Path) -> None:
    resultado = CliRunner().invoke(app, ["favoritos"])
    assert resultado.exit_code == 0
    assert "Nenhum favorito" in resultado.stdout


def test_atualizar_pula_em_dia_roda_antigo_e_sai_com_1_se_falhar(
    ambiente: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import typer

    fav.gravar_favoritos(["PETR4", "VALE3", "ITUB4"], ambiente / "favoritos.yaml")
    hoje = dt.date.today().isoformat()
    _resumo(ambiente / "saida", "PETR4", hoje)
    _resumo(ambiente / "saida", "VALE3", "2020-01-01")
    chamadas: list[str] = []

    def rodar_falso(**kwargs: object) -> None:
        chamadas.append(str(kwargs["ticker"]))
        if kwargs["ticker"] == "ITUB4":
            raise typer.Exit(code=1)

    monkeypatch.setattr(cli, "rodar", rodar_falso)
    resultado = CliRunner().invoke(app, ["favoritos", "atualizar", "--sem-graficos"])
    assert chamadas == ["VALE3", "ITUB4"]
    assert "em dia" in resultado.stdout
    assert resultado.exit_code == 1
