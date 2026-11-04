"""Adaptadores das séries longas da GUI: ITR antigos, divulgações e splits, sem rede."""

import datetime as dt
import sys
import types
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from conftest import SessaoFalsa
from valuation.data import cvm
from valuation.data import precos as prc
from valuation.data.precos import ErroPrecos

AGORA = dt.datetime(2026, 11, 4, 12, tzinfo=dt.UTC)
TTL = dt.timedelta(hours=12)
CNPJ = "84.429.695/0001-11"
INDICE = (
    "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;CATEG_DOC;ID_DOC;DT_RECEB;LINK_DOC\n"
    f"{CNPJ};2020-03-31;1;WEG;005410;ITR;1;2020-05-05;x\n"
    f"{CNPJ};2020-03-31;2;WEG;005410;ITR;2;2020-06-20;x\n"
    f"{CNPJ};2020-06-30;1;WEG;005410;ITR;3;;x\n"
    "11.111.111/0001-11;2020-03-31;1;OUTRA;000001;ITR;4;2020-01-01;x\n"
)
COMPOSICAO = (
    "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;QT_ACAO_ORDIN_CAP_INTEGR;QT_ACAO_PREF_CAP_INTEGR;"
    "QT_ACAO_TOTAL_CAP_INTEGR;QT_ACAO_ORDIN_TESOURO;QT_ACAO_PREF_TESOURO;QT_ACAO_TOTAL_TESOURO\n"
    f"{CNPJ};2020-03-31;1;WEG;100;0;100;1;0;1\n"
)


def _zip(caminho: Path, arquivos: dict[str, str]) -> bytes:
    with zipfile.ZipFile(caminho, "w") as zf:
        for nome, texto in arquivos.items():
            zf.writestr(nome, texto.encode("latin-1"))
    return caminho.read_bytes()


def test_ler_divulgacoes_usa_a_primeira_versao_e_ignora_sem_data(tmp_path: Path) -> None:
    arq = tmp_path / "i.zip"
    _zip(arq, {"itr_cia_aberta_2020.csv": INDICE})
    d = cvm.ler_divulgacoes(arq, "ITR", 2020, CNPJ)
    assert d.to_dict("records") == [
        {
            "fonte": "ITR",
            "dt_refer": pd.Timestamp("2020-03-31"),
            "dt_receb": pd.Timestamp("2020-05-05"),
        }
    ]


def test_ler_divulgacoes_sem_indice_fica_vazio(tmp_path: Path) -> None:
    arq = tmp_path / "i.zip"
    _zip(arq, {"outro.csv": "a\n"})
    assert cvm.ler_divulgacoes(arq, "ITR", 2020, CNPJ).empty


def test_coletar_series_grava_a_parte_e_tolera_o_ano_nao_publicado(
    tmp_path: Path, sessao_falsa: SessaoFalsa
) -> None:
    ano_base = 2022
    # ITR 2019 sem composição (como o arquivo real), ITR 2020 com; o resto é só o índice.
    for ano in (2019, 2020, 2021):
        arquivos = {f"itr_cia_aberta_{ano}.csv": INDICE}
        if ano == 2020:
            arquivos["itr_cia_aberta_composicao_capital_2020.csv"] = COMPOSICAO
        conteudo = _zip(tmp_path / f"itr{ano}.zip", arquivos)
        sessao_falsa.rotas[cvm.url_documento("ITR", ano)] = (200, conteudo, {})
    for ano in (2021, 2022):
        conteudo = _zip(tmp_path / f"dfp{ano}.zip", {f"dfp_cia_aberta_{ano}.csv": INDICE})
        sessao_falsa.rotas[cvm.url_documento("DFP", ano)] = (200, conteudo, {})

    cvm.coletar_series(
        cvm.AlvoCVM(CNPJ, 5410),
        ano_base,
        1,
        dir_raw=tmp_path / "raw",
        dir_processed=tmp_path / "proc",
        ttl=TTL,
        sessao=sessao_falsa,
        agora=AGORA,
    )
    pasta = tmp_path / "proc" / "cvm" / "5410"
    assert sorted(p.name for p in pasta.iterdir()) == [
        cvm.ARQUIVO_DIVULGACOES,
        cvm.ARQUIVO_SERIES_COMPOSICAO,
        cvm.ARQUIVO_SERIES_ITR,
    ]
    assert not (pasta / "demonstracoes.parquet").exists()
    comp = cvm.ler_composicao_serie(tmp_path / "proc", 5410)
    assert comp is not None
    assert comp["qt_acao_ordin_cap_integr"].tolist() == [100]
    divulgacoes = cvm.ler_datas_divulgacao(tmp_path / "proc", 5410)
    assert divulgacoes is not None
    assert set(divulgacoes["fonte"]) == {"ITR", "DFP"}


def test_composicao_da_coleta_normal_vence_na_mesma_data(tmp_path: Path) -> None:
    pasta = tmp_path / "cvm" / "1"
    pasta.mkdir(parents=True)
    linha = {"dt_refer": pd.Timestamp("2024-12-31"), "qt_acao_ordin_cap_integr": 1}
    pd.DataFrame([linha]).to_parquet(pasta / cvm.ARQUIVO_SERIES_COMPOSICAO)
    pd.DataFrame(
        [
            {**linha, "qt_acao_ordin_cap_integr": 2},
            {"dt_refer": pd.Timestamp("2025-12-31"), "qt_acao_ordin_cap_integr": 3},
        ]
    ).to_parquet(pasta / "composicao_capital.parquet")
    comp = cvm.ler_composicao_serie(tmp_path, 1)
    assert comp is not None
    assert comp["qt_acao_ordin_cap_integr"].tolist() == [2, 3]
    assert cvm.ler_composicao_serie(tmp_path, 2) is None


def _serie_splits() -> pd.Series:
    indice = pd.DatetimeIndex(["2021-04-28 10:00:00"], tz="America/Sao_Paulo")
    return pd.Series([2.0], index=indice, name="Stock Splits")


def _yf_falso(monkeypatch: pytest.MonkeyPatch, splits: object) -> list[str]:
    chamadas: list[str] = []

    class Ticker:
        def __init__(self, simbolo: str) -> None:
            chamadas.append(simbolo)

        @property
        def splits(self) -> object:
            if isinstance(splits, Exception):
                raise splits
            return splits

    monkeypatch.setitem(sys.modules, "yfinance", types.SimpleNamespace(Ticker=Ticker))
    return chamadas


def _provedor(tmp_path: Path, agora: dt.datetime = AGORA) -> prc.YFinanceProvider:
    return prc.YFinanceProvider(tmp_path, TTL, agora)


def test_splits_baixa_normaliza_data_e_grava(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chamadas = _yf_falso(monkeypatch, _serie_splits())
    s = _provedor(tmp_path).splits("WEGE3.SA")
    assert s.loc[pd.Timestamp("2021-04-28")] == 2.0
    assert s.index.tz is None
    em_cache = prc.splits_em_cache("WEGE3.SA", tmp_path)
    assert em_cache is not None
    pd.testing.assert_series_equal(em_cache, s, check_freq=False)
    _provedor(tmp_path).splits("WEGE3.SA")
    assert chamadas == ["WEGE3.SA"]  # dentro do TTL, não consulta


def test_splits_vazio_e_dado_valido(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vazio = pd.Series(
        [], index=pd.DatetimeIndex([], tz="America/Sao_Paulo"), dtype="float64", name="x"
    )
    _yf_falso(monkeypatch, vazio)
    assert _provedor(tmp_path).splits("PETR4.SA").empty
    em_cache = prc.splits_em_cache("PETR4.SA", tmp_path)
    assert em_cache is not None and em_cache.empty


def test_splits_falha_usa_copia_vencida_ou_erro(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _yf_falso(monkeypatch, RuntimeError("fora do ar"))
    with pytest.raises(ErroPrecos, match="fora do ar"):
        _provedor(tmp_path).splits("WEGE3.SA")
    assert prc.splits_em_cache("WEGE3.SA", tmp_path) is None
    _yf_falso(monkeypatch, _serie_splits())
    _provedor(tmp_path).splits("WEGE3.SA")
    _yf_falso(monkeypatch, RuntimeError("fora do ar"))
    depois = AGORA + dt.timedelta(days=30)
    assert _provedor(tmp_path, depois).splits("WEGE3.SA").iloc[0] == 2.0


def test_historico_em_cache_pega_a_maior_janela_sem_juntar(tmp_path: Path) -> None:
    def grava(inicio: str, fim: str, valor: float) -> None:
        df = pd.DataFrame({"close": [valor]}, index=pd.DatetimeIndex([fim]))
        df.to_parquet(tmp_path / f"yf_PETR4.SA_{inicio}_{fim}.parquet")

    assert prc.historico_em_cache("PETR4.SA", tmp_path) is None
    grava("20261015", "20261030", 1.0)
    grava("20161030", "20261030", 2.0)
    grava("20161104", "20261104", 3.0)  # mesma duração em dias; a mais recente vence
    (tmp_path / "yf_PETR4.SA_lixo.parquet").write_bytes(b"")
    df = prc.historico_em_cache("PETR4.SA", tmp_path)
    assert df is not None
    assert df["close"].iloc[0] == 3.0


def test_caches_nao_cruzam_tickers_parecidos(tmp_path: Path) -> None:
    pd.DataFrame({"close": [1.0]}).to_parquet(tmp_path / "yf_PETR3.SA_20200101_20260101.parquet")
    assert prc.historico_em_cache("PETR4.SA", tmp_path) is None


def _janela(pasta: Path, inicio: str, fim: str, *pares: tuple[str, float]) -> None:
    indice = pd.DatetimeIndex([d for d, _ in pares], name="data")
    pd.DataFrame({"close": [v for _, v in pares]}, index=indice).to_parquet(
        pasta / f"yf_PETR4.SA_{inicio}_{fim}.parquet"
    )


def test_historico_em_cache_anexa_os_dias_novos_se_a_base_coincidir(tmp_path: Path) -> None:
    _janela(tmp_path, "20161104", "20261104", ("2016-11-04", 8.0), ("2026-10-30", 60.0))
    _janela(tmp_path, "20261020", "20261104", ("2026-10-30", 60.1), ("2026-11-03", 57.8))
    df = prc.historico_em_cache("PETR4.SA", tmp_path)
    assert df is not None
    assert df["close"].tolist() == [8.0, 60.0, 57.8]


def test_historico_em_cache_nao_junta_bases_de_split_diferentes(tmp_path: Path) -> None:
    _janela(tmp_path, "20161104", "20261104", ("2016-11-04", 8.0), ("2026-10-30", 60.0))
    _janela(tmp_path, "20261020", "20261104", ("2026-10-30", 30.0), ("2026-11-03", 28.0))
    df = prc.historico_em_cache("PETR4.SA", tmp_path)
    assert df is not None
    assert df["close"].tolist() == [8.0, 60.0]


def test_historico_em_cache_janela_curta_nao_sobrepoe_a_longa(tmp_path: Path) -> None:
    _janela(tmp_path, "20161104", "20261104", ("2016-11-04", 8.0), ("2026-10-30", 60.0))
    _janela(tmp_path, "20261103", "20261104", ("2026-11-03", 57.8))  # sem dia comum
    df = prc.historico_em_cache("PETR4.SA", tmp_path)
    assert df is not None
    assert df["close"].tolist() == [8.0, 60.0]
