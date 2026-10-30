import datetime as dt
import zipfile
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest

from conftest import DIR_FIXTURES_CVM, SessaoFalsa, montar_zip
from valuation.data import cvm
from valuation.data.http import ArquivoNaoEncontrado

WEG = "84.429.695/0001-11"
PETROBRAS = "33.000.167/0001-01"


def test_urls() -> None:
    assert cvm.url_documento("DFP", 2025) == (
        "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_2025.zip"
    )
    assert cvm.url_documento("ITR", 2026).endswith("/DOC/ITR/DADOS/itr_cia_aberta_2026.zip")
    assert cvm.url_cadastro().endswith("/CAD/DADOS/cad_cia_aberta.csv")
    assert cvm.url_fca(2026).endswith("/DOC/FCA/DADOS/fca_cia_aberta_2026.zip")


def test_anos_a_coletar() -> None:
    anos = cvm.anos_a_coletar(2026, 10)
    assert anos["DFP"] == list(range(2016, 2027))
    assert anos["ITR"] == [2025, 2026]


def test_demonstracoes_aplicam_escala_e_tipos(zip_cvm: Callable[[str], Path]) -> None:
    df = cvm.ler_demonstracoes(zip_cvm("dfp_cia_aberta_2025"), "DFP", 2025, [WEG])

    receita = df.loc[
        (df["demonstracao"] == "DRE")
        & df["consolidado"]
        & (df["cd_conta"] == "3.01")
        & (df["ordem_exerc"] == "ÚLTIMO")
    ]
    assert len(receita) == 1
    linha = receita.iloc[0]
    # VL_CONTA = 40804110 em MIL
    assert linha["valor"] == pytest.approx(40_804_110_000)
    assert linha["cd_cvm"] == 5410
    assert linha["dt_ini"] == pd.Timestamp("2025-01-01")
    assert linha["dt_fim"] == pd.Timestamp("2025-12-31")
    assert linha["fonte"] == "DFP"
    assert linha["moeda"] == "REAL"
    assert list(df.columns) == cvm.COLUNAS_DEMONSTRACOES


def test_balanco_sem_dt_ini(zip_cvm: Callable[[str], Path]) -> None:
    df = cvm.ler_demonstracoes(zip_cvm("dfp_cia_aberta_2025"), "DFP", 2025, [WEG], ["BPA"])
    assert not df.empty
    assert df["dt_ini"].isna().all()
    assert set(df["cd_conta"]) == {"1", "1.01.01"}


def test_dmpl_tem_coluna_df(zip_cvm: Callable[[str], Path]) -> None:
    df = cvm.ler_demonstracoes(zip_cvm("dfp_cia_aberta_2025"), "DFP", 2025, [WEG], ["DMPL"])
    assert set(df["coluna_df"]) == {"Capital Social Integralizado"}


def test_consolidado_e_individual(zip_cvm: Callable[[str], Path]) -> None:
    df = cvm.ler_demonstracoes(zip_cvm("dfp_cia_aberta_2025"), "DFP", 2025, [WEG], ["DRE"])
    assert set(df["consolidado"]) == {True, False}
    assert set(df["arquivo"]) == {
        "dfp_cia_aberta_DRE_con_2025.csv",
        "dfp_cia_aberta_DRE_ind_2025.csv",
    }


def test_filtra_por_cnpj(zip_cvm: Callable[[str], Path]) -> None:
    df = cvm.ler_demonstracoes(zip_cvm("dfp_cia_aberta_2025"), "DFP", 2025, [PETROBRAS])
    assert df.empty
    assert list(df.columns) == cvm.COLUNAS_DEMONSTRACOES


def test_itr_traz_trimestre_e_acumulado(zip_cvm: Callable[[str], Path]) -> None:
    df = cvm.ler_demonstracoes(zip_cvm("itr_cia_aberta_2026"), "ITR", 2026, [PETROBRAS], ["DRE"])
    jun = df.loc[(df["dt_refer"] == "2026-06-30") & (df["ordem_exerc"] == "ÚLTIMO")]
    periodos = {(r.dt_ini.date(), r.valor) for r in jun.itertuples()}
    assert periodos == {
        (dt.date(2026, 1, 1), 293_216_000_000),  # acumulado no ano
        (dt.date(2026, 4, 1), 169_530_000_000),  # trimestre
    }


def _zip_com_linhas_extra(tmp_path: Path, membro: str, linhas: list[str]) -> Path:
    """Copia a fixture da DFP 2025 acrescentando linhas a um dos CSVs."""
    pasta = tmp_path / "dfp_cia_aberta_2025"
    pasta.mkdir()
    for origem in (DIR_FIXTURES_CVM / "dfp_cia_aberta_2025").glob("*.csv"):
        conteudo = origem.read_bytes()
        if origem.name == membro:
            conteudo = conteudo.rstrip(b"\r\n") + b"\n" + "\n".join(linhas).encode("latin-1")
        (pasta / origem.name).write_bytes(conteudo)
    return montar_zip(pasta, tmp_path / "dfp.zip")


LINHA_DRE = (
    "84.429.695/0001-11;2025-12-31;{versao};WEG S.A.;005410;"
    "DF Consolidado - Demonstração do Resultado;REAL;{escala};ÚLTIMO;2025-01-01;2025-12-31;"
    "3.99;Conta de teste;{valor};N"
)


def test_mantem_maior_versao(tmp_path: Path) -> None:
    # A fixture real é VERSAO 1; uma VERSAO 2 da mesma data substitui o documento inteiro.
    caminho = _zip_com_linhas_extra(
        tmp_path,
        "dfp_cia_aberta_DRE_con_2025.csv",
        [LINHA_DRE.format(versao=2, escala="MIL", valor="5.0")],
    )
    df = cvm.ler_demonstracoes(caminho, "DFP", 2025, [WEG], ["DRE"])
    con = df.loc[df["consolidado"]]
    assert set(con["versao"]) == {2}
    assert list(con["cd_conta"]) == ["3.99"]


def test_escala_unidade(tmp_path: Path) -> None:
    caminho = _zip_com_linhas_extra(
        tmp_path,
        "dfp_cia_aberta_DRE_con_2025.csv",
        [LINHA_DRE.format(versao=1, escala="UNIDADE", valor="123.0")],
    )
    df = cvm.ler_demonstracoes(caminho, "DFP", 2025, [WEG], ["DRE"])
    assert df.loc[df["cd_conta"] == "3.99", "valor"].item() == 123.0


def test_escala_desconhecida_falha(tmp_path: Path) -> None:
    caminho = _zip_com_linhas_extra(
        tmp_path,
        "dfp_cia_aberta_DRE_con_2025.csv",
        [LINHA_DRE.format(versao=1, escala="MILHAO", valor="1.0")],
    )
    with pytest.raises(cvm.ErroDadosCVM, match="MILHAO"):
        cvm.ler_demonstracoes(caminho, "DFP", 2025, [WEG], ["DRE"])


def test_aspas_literais_em_ds_conta(tmp_path: Path) -> None:
    linha = LINHA_DRE.format(versao=1, escala="MIL", valor="1.0").replace(
        "Conta de teste", 'Títulos - valor justo ("VJORA")'
    )
    caminho = _zip_com_linhas_extra(tmp_path, "dfp_cia_aberta_DRE_con_2025.csv", [linha])
    df = cvm.ler_demonstracoes(caminho, "DFP", 2025, [WEG], ["DRE"])
    assert df.loc[df["cd_conta"] == "3.99", "ds_conta"].item() == 'Títulos - valor justo ("VJORA")'


def test_arquivo_ausente_no_zip_e_ignorado(zip_cvm: Callable[[str], Path]) -> None:
    df = cvm.ler_demonstracoes(zip_cvm("dfp_cia_aberta_2025"), "DFP", 2025, [WEG], ["DVA"])
    assert df.empty


def test_composicao_capital(zip_cvm: Callable[[str], Path]) -> None:
    df = cvm.ler_composicao_capital(zip_cvm("dfp_cia_aberta_2025"), "DFP", 2025, [WEG])
    assert len(df) == 1
    assert df["qt_acao_total_cap_integr"].item() == 4_197_317_998
    assert df["qt_acao_total_tesouro"].item() == 1_622_025


def test_composicao_capital_ausente(tmp_path: Path) -> None:
    caminho = tmp_path / "vazio.zip"
    with zipfile.ZipFile(caminho, "w") as zf:
        zf.writestr("outro.csv", "x")
    assert cvm.ler_composicao_capital(caminho, "DFP", 2016, [WEG]).empty


def _acoes(totais: list[int]) -> pd.DataFrame:
    datas = pd.date_range("2020-12-31", periods=len(totais), freq="YE")
    return pd.DataFrame(
        {
            "cnpj": PETROBRAS,
            "fonte": "DFP",
            "dt_refer": datas,
            "versao": 1,
            **{c: totais for c in cvm.COLUNAS_ACOES},
        }
    )


def test_corrige_data_isolada_em_milhares() -> None:
    # Caso real: Petrobras na DFP 2020 (13.044.497 contra 13.044.496.930 depois).
    df = cvm.corrigir_escala_acoes(_acoes([13_044_497, 13_044_496_930, 12_888_732_761]), 1)
    assert list(df["qt_acao_total_cap_integr"]) == [13_044_497_000, 13_044_496_930, 12_888_732_761]
    assert list(df["escala_acoes_aplicada"]) == [1000, 1, 1]


def test_desdobramento_nao_e_corrigido() -> None:
    # WEG: desdobramento 2:1 em 2021.
    df = cvm.corrigir_escala_acoes(_acoes([2_098_658_999, 4_197_317_998]), 1)
    assert list(df["escala_acoes_aplicada"]) == [1, 1]


def test_escala_base_do_cadastro() -> None:
    # Vale: todas as datas em milhares.
    df = cvm.corrigir_escala_acoes(_acoes([4_539_007, 4_262_534]), 1000)
    assert list(df["qt_acao_total_cap_integr"]) == [4_539_007_000, 4_262_534_000]
    assert list(df["escala_acoes_aplicada"]) == [1000, 1000]


def test_coletar_grava_parquet_por_companhia(
    tmp_path: Path, sessao_falsa: SessaoFalsa, zip_cvm: Callable[[str], Path]
) -> None:
    sessao_falsa.rotas[cvm.url_documento("DFP", 2025)] = (
        200,
        zip_cvm("dfp_cia_aberta_2025").read_bytes(),
        {},
    )
    sessao_falsa.rotas[cvm.url_documento("ITR", 2026)] = (
        200,
        zip_cvm("itr_cia_aberta_2026").read_bytes(),
        {},
    )
    alvos = [cvm.AlvoCVM(WEG, 5410), cvm.AlvoCVM(PETROBRAS, 9512)]

    resumo = cvm.coletar(
        alvos,
        {"DFP": [2025, 2026], "ITR": [2026]},
        dir_raw=tmp_path / "raw",
        dir_processed=tmp_path / "processed",
        ttl=dt.timedelta(hours=1),
        sessao=sessao_falsa,
        agora=dt.datetime(2026, 10, 30, tzinfo=dt.UTC),
    )

    assert resumo.anos_baixados == {"DFP": [2025], "ITR": [2026]}
    assert resumo.anos_indisponiveis == {"DFP": [2026], "ITR": []}
    assert (tmp_path / "raw" / "cvm" / "DFP" / "dfp_cia_aberta_2025.zip").is_file()
    weg = pd.read_parquet(tmp_path / "processed" / "cvm" / "5410" / "demonstracoes.parquet")
    assert set(weg["cnpj"]) == {WEG}
    petro = pd.read_parquet(tmp_path / "processed" / "cvm" / "9512" / "demonstracoes.parquet")
    assert set(petro["fonte"]) == {"ITR"}
    acoes = pd.read_parquet(tmp_path / "processed" / "cvm" / "9512" / "composicao_capital.parquet")
    assert set(acoes["fonte"]) == {"DFP", "ITR"}
    assert resumo.periodos_por_cd_cvm[9512] == [dt.date(2026, 3, 31), dt.date(2026, 6, 30)]


def test_coletar_404_em_ano_antigo_falha(tmp_path: Path, sessao_falsa: SessaoFalsa) -> None:
    with pytest.raises(ArquivoNaoEncontrado):
        cvm.coletar(
            [cvm.AlvoCVM(WEG, 5410)],
            {"DFP": [2015, 2016]},
            dir_raw=tmp_path / "raw",
            dir_processed=tmp_path / "processed",
            ttl=dt.timedelta(hours=1),
            sessao=sessao_falsa,
            agora=dt.datetime(2026, 10, 30, tzinfo=dt.UTC),
        )


def test_coletar_cd_cvm_divergente_falha(
    tmp_path: Path, sessao_falsa: SessaoFalsa, zip_cvm: Callable[[str], Path]
) -> None:
    sessao_falsa.rotas[cvm.url_documento("DFP", 2025)] = (
        200,
        zip_cvm("dfp_cia_aberta_2025").read_bytes(),
        {},
    )
    with pytest.raises(cvm.ErroDadosCVM, match="5410"):
        cvm.coletar(
            [cvm.AlvoCVM(WEG, 1)],
            {"DFP": [2025]},
            dir_raw=tmp_path / "raw",
            dir_processed=tmp_path / "processed",
            ttl=dt.timedelta(hours=1),
            sessao=sessao_falsa,
            agora=dt.datetime(2026, 10, 30, tzinfo=dt.UTC),
        )
