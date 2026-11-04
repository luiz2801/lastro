"""`servicos/historico_mercado.py`: série do que está em disco, à mão e sem rede."""

import datetime as dt
import math
from pathlib import Path

import pandas as pd
import pytest

from sintetico import dfp_completa, documento, juntar
from valuation.config import Settings, carregar_settings
from valuation.contabil import padronizacao as pad
from valuation.data import cvm
from valuation.data import precos as prc
from valuation.data.cadastro import ClasseAcao, Empresa
from valuation.data.validacao import ErroDadosExternos
from valuation.projecao import premissas as pm
from valuation.servicos import empresa as emp
from valuation.servicos import historico_mercado as hm

BASE = dt.date(2026, 4, 30)
AGORA = dt.datetime(2026, 4, 30, 12, tzinfo=dt.UTC)
TICKER = "XXXX3"
EMPRESA = Empresa(
    cnpj="00.000.000/0001-00",
    cd_cvm=1234,
    razao_social="X",
    nome_comercial="X",
    setor_cvm="s",
    tipo_modelo="nao_financeira",
    escala_acoes=1,
    classes=(ClasseAcao(TICKER, "ON"),),
)


def _padronizada(dados: pd.DataFrame) -> emp.Padronizada:
    premissas = pm.premissas_padrao(TICKER, "nao_financeira", EMPRESA.tickers)
    plano = pad.carregar_mapeamento(tipo="nao_financeira")
    selecionadas = pad.selecionar_reapresentacoes(dados, consolidado=True)
    contas = pad.padronizar(selecionadas, plano, ticker=TICKER)
    return emp.Padronizada(EMPRESA, plano, selecionadas, contas, "BRL", premissas, Path("x.yaml"))


def _pasta(raiz: Path) -> Path:
    pasta = raiz / "processed" / "cvm" / "1234"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _composicao(raiz: Path, *linhas: tuple[str, int]) -> None:
    pd.DataFrame(
        {
            "dt_refer": [pd.Timestamp(d) for d, _ in linhas],
            "qt_acao_ordin_cap_integr": [q for _, q in linhas],
            "qt_acao_pref_cap_integr": 0,
            "qt_acao_total_cap_integr": [q for _, q in linhas],
            "qt_acao_ordin_tesouro": 0,
            "qt_acao_pref_tesouro": 0,
            "qt_acao_total_tesouro": 0,
        }
    ).to_parquet(_pasta(raiz) / "composicao_capital.parquet", index=False)


def _cotacao(raiz: Path, closes: dict[str, float], ticker: str = TICKER) -> None:
    dir_precos = raiz / "raw" / "precos"
    dir_precos.mkdir(parents=True, exist_ok=True)
    indice = pd.DatetimeIndex(list(closes), name="data")
    valores = list(closes.values())
    pd.DataFrame({"close": valores, "adj_close": valores, "volume": 1.0}, index=indice).to_parquet(
        dir_precos / f"yf_{ticker}.SA_20160430_20260430.parquet"
    )


def _splits(raiz: Path, *pares: tuple[str, float]) -> None:
    dir_precos = raiz / "raw" / "precos"
    dir_precos.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {"fator": [f for _, f in pares]},
        index=pd.DatetimeIndex([d for d, _ in pares], name="data"),
    ).astype("float64").to_parquet(dir_precos / f"splits_{TICKER}.SA.parquet")


def _divulgacoes(raiz: Path, *pares: tuple[str, str]) -> None:
    pd.DataFrame(
        {
            "fonte": "DFP",
            "dt_refer": [pd.Timestamp(a) for a, _ in pares],
            "dt_receb": [pd.Timestamp(b) for _, b in pares],
        }
    ).to_parquet(_pasta(raiz) / cvm.ARQUIVO_DIVULGACOES, index=False)


@pytest.fixture
def settings() -> Settings:
    return carregar_settings()


@pytest.fixture
def p(tmp_path: Path) -> emp.Padronizada:
    dados = juntar(dfp_completa(2023), dfp_completa(2024), dfp_completa(2025))
    dados.to_parquet(_pasta(tmp_path) / "demonstracoes.parquet", index=False)
    return _padronizada(dados)


def _carregar(p: emp.Padronizada, settings: Settings, raiz: Path) -> hm.SeriesMercado:
    r = hm.carregar_series(
        p,
        TICKER,
        settings,
        BASE,
        dir_raw=raiz / "raw",
        dir_processed=raiz / "processed",
    )
    assert r is not None
    return r


def test_sem_cotacao_em_cache_devolve_none(
    tmp_path: Path, p: emp.Padronizada, settings: Settings
) -> None:
    r = hm.carregar_series(
        p, TICKER, settings, BASE, dir_raw=tmp_path / "raw", dir_processed=tmp_path / "processed"
    )
    assert r is None


def test_pl_a_mao_com_a_data_de_divulgacao(
    tmp_path: Path, p: emp.Padronizada, settings: Settings
) -> None:
    _cotacao(tmp_path, {"2026-01-30": 10.0, "2026-02-27": 20.0, "2026-03-31": 30.0})
    _composicao(tmp_path, ("2025-12-31", 9))
    _splits(tmp_path, ("2010-01-01", 2.0))  # anterior à composição: não conta
    _divulgacoes(tmp_path, ("2024-12-31", "2025-03-01"), ("2025-12-31", "2026-03-10"))
    r = _carregar(p, settings, tmp_path)
    assert r.market_cap.tolist() == [90.0, 180.0, 270.0]
    assert list(r.vigencia) == [
        pd.Timestamp("2024-12-31"),
        pd.Timestamp("2024-12-31"),  # 2025 só divulgado em 10/03/2026
        pd.Timestamp("2025-12-31"),
    ]
    assert r.multiplos["p_l"].tolist() == pytest.approx([10.0, 20.0, 30.0])  # lucro 9
    assert r.multiplos["p_vp"].iloc[0] == pytest.approx(90 / 95)  # PL da controladora
    # EV = 90 + dívida 100 - caixa 30 + minoritários 5 = 165; EBITDA = 20 + 8 = 28
    assert r.multiplos["ev_ebitda"].iloc[0] == pytest.approx(165 / 28)
    assert r.multiplos["dividend_yield"].isna().all()  # DFP sintética sem dividendos: lacuna
    assert r.avisos == ["Sem os ITR antigos em disco: LTM anual até 2024. Clique em Atualizar."]


def test_antes_da_composicao_fica_lacuna_com_aviso(
    tmp_path: Path, p: emp.Padronizada, settings: Settings
) -> None:
    _cotacao(tmp_path, {"2025-12-30": 10.0, "2026-02-27": 20.0})
    _composicao(tmp_path, ("2026-01-31", 9))
    _splits(tmp_path, ("2010-01-01", 2.0))
    r = _carregar(p, settings, tmp_path)
    assert math.isnan(r.market_cap.iloc[0]) and math.isnan(r.multiplos["p_l"].iloc[0])
    assert r.market_cap.iloc[1] == 180.0
    assert r.inicio_composicao == dt.date(2026, 1, 31)
    assert any("só publica a quantidade de ações desde 31/01/2026" in a for a in r.avisos)


def test_split_entre_composicao_e_preco_nao_faz_degrau(
    tmp_path: Path, p: emp.Padronizada, settings: Settings
) -> None:
    """Close já ajustado (10 antes e depois do 2:1); a composição de jan é da base antiga."""
    _cotacao(tmp_path, {"2026-01-30": 10.0, "2026-03-31": 10.0})
    _composicao(tmp_path, ("2026-01-01", 5))
    _splits(tmp_path, ("2026-02-15", 2.0))
    r = _carregar(p, settings, tmp_path)
    assert r.market_cap.tolist() == [100.0, 100.0]


def test_divergencia_de_splits_vira_aviso(
    tmp_path: Path, p: emp.Padronizada, settings: Settings
) -> None:
    _cotacao(tmp_path, {"2026-03-31": 10.0})
    _composicao(tmp_path, ("2025-06-30", 5), ("2025-12-31", 10))
    _splits(tmp_path, ("2010-01-01", 1.0))
    r = _carregar(p, settings, tmp_path)
    assert any("Ações da CVM variaram 2.00x" in a for a in r.avisos)


def test_sem_splits_em_disco_avisa_e_nao_ajusta(
    tmp_path: Path, p: emp.Padronizada, settings: Settings
) -> None:
    _cotacao(tmp_path, {"2026-03-31": 10.0})
    _composicao(tmp_path, ("2025-12-31", 5))
    r = _carregar(p, settings, tmp_path)
    assert r.market_cap.tolist() == [50.0]
    assert any("sem lista de splits" in a for a in r.avisos)


def test_sem_composicao_todos_os_multiplos_em_lacuna(
    tmp_path: Path, p: emp.Padronizada, settings: Settings
) -> None:
    _cotacao(tmp_path, {"2026-03-31": 10.0})
    r = _carregar(p, settings, tmp_path)
    assert r.multiplos.isna().all().all()
    assert not r.cotacao.empty  # a cotação aparece mesmo assim
    assert any("sem composição" in a for a in r.avisos)


def test_itr_antigos_entram_so_em_memoria(
    tmp_path: Path, p: emp.Padronizada, settings: Settings
) -> None:
    """O ITR de 03/2025 cria um ponto novo de LTM sem regravar `contas_padronizadas.parquet`."""
    fim = "2025-03-31"
    dre = {"3.01": 25, "3.05": 5, "3.11": 3, "3.11.01": 3}
    itr = juntar(
        documento(dre, dem="DRE", dt_ini="2025-01-01", dt_fim=fim, fonte="ITR"),
        documento({"1": 200, "1.01.01": 20}, dem="BPA", dt_fim=fim, fonte="ITR"),
        documento({"2": 200, "2.03": 100}, dem="BPP", dt_fim=fim, fonte="ITR"),
    )
    itr.to_parquet(_pasta(tmp_path) / cvm.ARQUIVO_SERIES_ITR, index=False)
    antes = p.contas.copy()
    contas = hm._contas_da_serie(p, tmp_path / "processed")
    assert pd.Timestamp(fim) in set(contas["dt_fim"])
    pd.testing.assert_frame_equal(p.contas, antes)
    assert not pad.caminho_padronizadas(tmp_path / "processed", 1234).exists()


def test_baixar_series_exige_a_cotacao_do_papel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    class Provedor:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        def historico(self, *_: object) -> pd.DataFrame:
            raise prc.ErroPrecos("fora do ar")

    monkeypatch.setattr(hm.prc, "YFinanceProvider", Provedor)
    with pytest.raises(ErroDadosExternos, match="fora do ar"):
        hm.baixar_series(EMPRESA, TICKER, settings, BASE, AGORA, sessao=object())


def test_baixar_series_outras_faltas_viram_aviso(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    empresa = Empresa(
        **{
            **EMPRESA.__dict__,
            "classes": (ClasseAcao(TICKER, "ON"), ClasseAcao("XXXX4", "PN")),
        }
    )
    pedidos: list[tuple[str, dt.date, dt.date]] = []

    class Provedor:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        def historico(self, simbolo: str, inicio: dt.date, fim: dt.date) -> pd.DataFrame:
            pedidos.append((simbolo, inicio, fim))
            if simbolo.startswith("XXXX4"):
                raise prc.ErroPrecos("sem dados")
            return pd.DataFrame()

        def splits(self, _: str) -> pd.Series:
            raise prc.ErroPrecos("sem splits")

    coletas: list[object] = []
    monkeypatch.setattr(hm.prc, "YFinanceProvider", Provedor)
    monkeypatch.setattr(hm.cvm, "coletar_series", lambda *a, **k: coletas.append(a))
    avisos = hm.baixar_series(empresa, TICKER, settings, BASE, AGORA, sessao=object())
    assert [a.split(":")[0] for a in avisos] == [
        "XXXX4 sem histórico de cotação",
        "XXXX3 sem lista de splits",
    ]
    assert pedidos[0] == ("XXXX3.SA", dt.date(2016, 4, 30), BASE)  # historico_anos = 10
    assert len(coletas) == 1
