import datetime as dt
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest

from conftest import DIR_FIXTURES_CVM, SessaoFalsa
from valuation.data import cadastro as cad
from valuation.data.cvm import url_cadastro, url_fca

DATA_REF = dt.date(2026, 10, 30)
CABECALHO_MANUAL = "ticker;cnpj;especie;tipo_modelo;escala_acoes;observacao\n"


@pytest.fixture
def cadastro_cvm() -> pd.DataFrame:
    return cad.ler_cadastro_cvm(DIR_FIXTURES_CVM / "cad_cia_aberta.csv")


@pytest.fixture
def valores_mobiliarios(zip_cvm: Callable[[str], Path]) -> pd.DataFrame:
    return cad.ler_valores_mobiliarios(
        [zip_cvm("fca_cia_aberta_2025"), zip_cvm("fca_cia_aberta_2026")], DATA_REF
    )


def _manual(tmp_path: Path, linhas: str = "") -> pd.DataFrame:
    caminho = tmp_path / "cadastro_manual.csv"
    caminho.write_text("# comentário\n" + CABECALHO_MANUAL + linhas, encoding="utf-8")
    return cad.ler_cadastro_manual(caminho)


def test_cadastro_cvm_prefere_registro_ativo(cadastro_cvm: pd.DataFrame) -> None:
    assert cadastro_cvm["cnpj"].is_unique
    itau = cadastro_cvm.loc[cadastro_cvm["cnpj"] == "60.872.504/0001-23"].iloc[0]
    assert itau["cd_cvm"] == 19348  # o registro 1279 está CANCELADO
    assert itau["situacao"] == "ATIVO"


def test_valores_mobiliarios(valores_mobiliarios: pd.DataFrame) -> None:
    por_ticker = valores_mobiliarios.set_index("ticker")["especie"].to_dict()
    assert por_ticker["PETR3"] == "ON"
    assert por_ticker["PETR4"] == "PN"
    assert por_ticker["ENGI11"] == "UNIT"
    assert "BRFS3" not in por_ticker  # negociação encerrada em 2025-09-22
    assert "NÃO HÁ" not in por_ticker
    assert valores_mobiliarios["ticker"].is_unique  # CRTE3 aparece como ON e PN no FCA


def test_valores_mobiliarios_antes_do_fim_da_negociacao(zip_cvm: Callable[[str], Path]) -> None:
    vm = cad.ler_valores_mobiliarios([zip_cvm("fca_cia_aberta_2025")], dt.date(2025, 1, 1))
    assert "BRFS3" in set(vm["ticker"])


def test_classificar_tipo_modelo() -> None:
    assert cad.classificar_tipo_modelo("Bancos") == "financeira"
    assert cad.classificar_tipo_modelo("Emp. Adm. Part. - Seguradoras e Corretoras") == (
        "financeira"
    )
    assert cad.classificar_tipo_modelo("Petróleo e Gás") == "nao_financeira"
    # WEG está em "Emp. Adm. Part." e é operacional: holding só via cadastro manual.
    assert cad.classificar_tipo_modelo("Emp. Adm. Part. - Máqs., Equip., Veíc. e Peças") == (
        "nao_financeira"
    )
    assert cad.classificar_tipo_modelo("Securitização de Recebíveis") == "nao_suportada"


def test_montar_cadastro(
    tmp_path: Path, cadastro_cvm: pd.DataFrame, valores_mobiliarios: pd.DataFrame
) -> None:
    df = cad.montar_cadastro(cadastro_cvm, valores_mobiliarios, _manual(tmp_path))
    petr4 = df.set_index("ticker").loc["PETR4"]
    assert petr4["cd_cvm"] == 9512
    assert petr4["tipo_modelo"] == "nao_financeira"
    assert petr4["escala_acoes"] == 1
    assert df.set_index("ticker").loc["ITUB4", "tipo_modelo"] == "financeira"
    assert list(df.columns) == cad.COLUNAS_CADASTRO


def test_cadastro_manual_sobrescreve(
    tmp_path: Path, cadastro_cvm: pd.DataFrame, valores_mobiliarios: pd.DataFrame
) -> None:
    manual = _manual(
        tmp_path,
        "VALE3;;;;1000;milhares\nITSA4;61.532.644/0001-15;PN;holding;;fora do FCA da fixture\n",
    )
    df = cad.montar_cadastro(cadastro_cvm, valores_mobiliarios, manual).set_index("ticker")
    assert df.loc["VALE3", "escala_acoes"] == 1000
    assert df.loc["ITSA4", "tipo_modelo"] == "holding"
    assert df.loc["ITSA4", "cd_cvm"] == 7617
    assert df.loc["ITSA4", "origem"] == "manual"


def test_cadastro_manual_ticker_novo_exige_cnpj(
    tmp_path: Path, cadastro_cvm: pd.DataFrame, valores_mobiliarios: pd.DataFrame
) -> None:
    manual = _manual(tmp_path, "XPTO3;;;holding;;\n")
    with pytest.raises(cad.ErroCadastro, match="XPTO3"):
        cad.montar_cadastro(cadastro_cvm, valores_mobiliarios, manual)


def test_cadastro_manual_cnpj_divergente(
    tmp_path: Path, cadastro_cvm: pd.DataFrame, valores_mobiliarios: pd.DataFrame
) -> None:
    manual = _manual(tmp_path, "VALE3;84.429.695/0001-11;;;;\n")
    with pytest.raises(cad.ErroCadastro, match="difere do FCA"):
        cad.montar_cadastro(cadastro_cvm, valores_mobiliarios, manual)


@pytest.mark.parametrize(
    ("linha", "erro"),
    [
        ("VALE3;;;banco;;\n", "tipo_modelo"),
        ("VALE3;;XX;;;\n", "especie"),
        ("VALE3;;;;10;\n", "escala_acoes"),
    ],
)
def test_cadastro_manual_invalido(tmp_path: Path, linha: str, erro: str) -> None:
    with pytest.raises(cad.ErroCadastro, match=erro):
        _manual(tmp_path, linha)


def test_cadastro_manual_ausente(tmp_path: Path) -> None:
    assert cad.ler_cadastro_manual(tmp_path / "nao_existe.csv").empty


def test_cadastro_manual_do_repositorio_e_valido() -> None:
    from valuation.config import CAMINHO_CADASTRO_MANUAL

    df = cad.ler_cadastro_manual(CAMINHO_CADASTRO_MANUAL)
    assert "VALE3" in set(df["ticker"])


@pytest.fixture
def cadastro(
    tmp_path: Path, cadastro_cvm: pd.DataFrame, valores_mobiliarios: pd.DataFrame
) -> pd.DataFrame:
    return cad.montar_cadastro(cadastro_cvm, valores_mobiliarios, _manual(tmp_path))


def test_empresa_por_ticker_agrupa_classes(cadastro: pd.DataFrame) -> None:
    empresa = cad.empresa_por_ticker(cadastro, "petr4.sa")
    assert empresa.cd_cvm == 9512
    assert empresa.tickers == ("PETR3", "PETR4")
    assert {c.especie for c in empresa.classes} == {"ON", "PN"}


def test_empresa_por_ticker_inexistente_sugere(cadastro: pd.DataFrame) -> None:
    with pytest.raises(cad.ErroCadastro, match="PETR3, PETR4"):
        cad.empresa_por_ticker(cadastro, "PETR9")


def test_empresa_com_classes_inconsistentes(cadastro: pd.DataFrame) -> None:
    cadastro.loc[cadastro["ticker"] == "PETR3", "escala_acoes"] = 1000
    with pytest.raises(cad.ErroCadastro, match="escala_acoes"):
        cad.empresa_por_ticker(cadastro, "PETR4")


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("petrobras", {"PETR3", "PETR4"}),
        ("PETRÓLEO", {"PETR3", "PETR4"}),
        ("itau", {"ITUB4"}),
        ("wege", {"WEGE3"}),
        ("33.592.510", {"VALE3"}),
        ("33592510", {"VALE3"}),
    ],
)
def test_buscar(cadastro: pd.DataFrame, texto: str, esperado: set[str]) -> None:
    assert set(cad.buscar(cadastro, texto)["ticker"]) == esperado


def _rotas_cadastro(sessao: SessaoFalsa, zip_cvm: Callable[[str], Path]) -> None:
    sessao.rotas[url_cadastro()] = (
        200,
        (DIR_FIXTURES_CVM / "cad_cia_aberta.csv").read_bytes(),
        {},
    )
    for ano in (2025, 2026):
        sessao.rotas[url_fca(ano)] = (200, zip_cvm(f"fca_cia_aberta_{ano}").read_bytes(), {})


def test_atualizar_cadastro(
    tmp_path: Path, sessao_falsa: SessaoFalsa, zip_cvm: Callable[[str], Path]
) -> None:
    _rotas_cadastro(sessao_falsa, zip_cvm)
    df = cad.atualizar_cadastro(
        ano=2026,
        data_ref=DATA_REF,
        dir_raw=tmp_path / "raw",
        dir_processed=tmp_path / "processed",
        caminho_manual=tmp_path / "nao_existe.csv",
        ttl=dt.timedelta(hours=1),
        sessao=sessao_falsa,
        agora=dt.datetime(2026, 10, 30, tzinfo=dt.UTC),
    )
    assert "WEGE3" in set(df["ticker"])
    gravado = pd.read_parquet(tmp_path / "processed" / "cadastro.parquet")
    assert len(gravado) == len(df)


def test_atualizar_cadastro_fca_do_ano_ainda_nao_publicado(
    tmp_path: Path, sessao_falsa: SessaoFalsa, zip_cvm: Callable[[str], Path]
) -> None:
    _rotas_cadastro(sessao_falsa, zip_cvm)
    del sessao_falsa.rotas[url_fca(2026)]
    df = cad.atualizar_cadastro(
        ano=2026,
        data_ref=dt.date(2025, 6, 1),
        dir_raw=tmp_path / "raw",
        dir_processed=tmp_path / "processed",
        caminho_manual=tmp_path / "nao_existe.csv",
        ttl=dt.timedelta(hours=1),
        sessao=sessao_falsa,
        agora=dt.datetime(2026, 10, 30, tzinfo=dt.UTC),
    )
    assert set(df["ticker"]) == {"BRFS3", "WEGE3"}
