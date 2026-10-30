from pathlib import Path

import pytest
from typer.testing import CliRunner

from valuation import cli
from valuation.cli import app
from valuation.config import CAMINHO_UNIVERSO, ErroConfiguracao
from valuation.universo import (
    EmpresaUniverso,
    SetorCVM,
    buscar_setor,
    carregar_universo,
    empresas_do_setor,
)


def test_enum_coincide_com_o_universo_versionado() -> None:
    setores_csv = {e.setor for e in carregar_universo(CAMINHO_UNIVERSO)}
    assert setores_csv == set(SetorCVM)
    assert len(SetorCVM) == 33


def test_buscar_setor_por_nome_ou_texto_da_cvm() -> None:
    assert buscar_setor("BANCOS") is SetorCVM.BANCOS
    assert buscar_setor("bancos") is SetorCVM.BANCOS
    assert buscar_setor("Petróleo e Gás") is SetorCVM.PETROLEO_E_GAS
    assert buscar_setor("petroleo e gas") is SetorCVM.PETROLEO_E_GAS


def test_buscar_setor_desconhecido_falha() -> None:
    with pytest.raises(ErroConfiguracao, match="não existe"):
        buscar_setor("Criptomoedas")


def test_carregar_universo_ignora_comentarios_e_valida_setor(tmp_path: Path) -> None:
    caminho = tmp_path / "universo.csv"
    caminho.write_text(
        "# comentário\nticker;cnpj;setor_cvm;tipo_modelo\nITUB4;x;Bancos;financeira\n",
        encoding="utf-8",
    )
    assert carregar_universo(caminho) == [EmpresaUniverso("ITUB4", SetorCVM.BANCOS, "financeira")]


def test_carregar_universo_setor_fora_do_enum_falha(tmp_path: Path) -> None:
    caminho = tmp_path / "universo.csv"
    caminho.write_text("ticker;cnpj;setor_cvm;tipo_modelo\nXPTO3;x;Inventado;nao_financeira\n")
    with pytest.raises(ErroConfiguracao, match="não está no enum"):
        carregar_universo(caminho)


def test_empresas_do_setor_na_ordem_do_csv() -> None:
    universo = carregar_universo(CAMINHO_UNIVERSO)
    tickers = [e.ticker for e in empresas_do_setor(universo, SetorCVM.BANCOS)]
    assert tickers[:2] == ["BBAS3", "BBDC3"]
    assert "ITUB4" in tickers


def test_cli_lista_setores() -> None:
    resultado = CliRunner().invoke(app, ["setores"])
    assert resultado.exit_code == 0
    assert "BANCOS" in resultado.stdout


def test_cli_lista_empresas_do_setor() -> None:
    resultado = CliRunner().invoke(app, ["setores", "bancos"])
    assert resultado.exit_code == 0
    assert "ITUB4" in resultado.stdout


def test_cli_setor_desconhecido_sai_com_1() -> None:
    resultado = CliRunner().invoke(app, ["setores", "xyz"])
    assert resultado.exit_code == 1


@pytest.fixture
def universo_pequeno(monkeypatch: pytest.MonkeyPatch) -> None:
    universo = [
        EmpresaUniverso("ITUB4", SetorCVM.BANCOS, "financeira"),
        EmpresaUniverso("BBDC4", SetorCVM.BANCOS, "financeira"),
        EmpresaUniverso("BRAP4", SetorCVM.BANCOS, "holding"),
        EmpresaUniverso("VALE3", SetorCVM.EXTRACAO_MINERAL, "nao_financeira"),
    ]
    monkeypatch.setattr(cli, "carregar_universo", lambda: universo)
    monkeypatch.setattr(cli.reg, "resolver_perfil", lambda *a, **k: None)


def test_rodar_setor_roda_cada_empresa_e_pula_holding(
    universo_pequeno: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    chamadas: list[str] = []

    def rodar_falso(**kwargs: object) -> None:
        chamadas.append(str(kwargs["ticker"]))

    monkeypatch.setattr(cli, "rodar", rodar_falso)
    resultado = CliRunner().invoke(app, ["rodar-setor", "BANCOS", "--sem-graficos"])
    assert resultado.exit_code == 0
    assert chamadas == ["ITUB4", "BBDC4"]
    assert "fora da v1" in resultado.stdout


def test_rodar_setor_continua_apos_falha_e_sai_com_1(
    universo_pequeno: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    chamadas: list[str] = []

    def rodar_falso(**kwargs: object) -> None:
        chamadas.append(str(kwargs["ticker"]))
        if kwargs["ticker"] == "ITUB4":
            raise cli.typer.Exit(code=1)

    monkeypatch.setattr(cli, "rodar", rodar_falso)
    resultado = CliRunner().invoke(app, ["rodar-setor", "bancos"])
    assert resultado.exit_code == 1
    assert chamadas == ["ITUB4", "BBDC4"]
    assert "ITUB4" in resultado.stdout


def test_rodar_setor_sem_perfil_falha_antes_de_rodar(
    universo_pequeno: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    def sem_perfil(*_: object, **__: object) -> None:
        raise cli.ErroPerfil("Perfil ausente.")

    monkeypatch.setattr(cli.reg, "resolver_perfil", sem_perfil)
    monkeypatch.setattr(cli, "rodar", pytest.fail)
    resultado = CliRunner().invoke(app, ["rodar-setor", "BANCOS"])
    assert resultado.exit_code == 1
    assert "Perfil ausente" in resultado.stdout
