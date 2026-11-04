"""`servicos/mercado.py`: preços, market cap e macro sem terminal e sem rede."""

import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from valuation import cli
from valuation.config import Settings, carregar_settings
from valuation.data import macro as mac
from valuation.data import precos as prc
from valuation.data.cadastro import ClasseAcao, Empresa
from valuation.data.validacao import ErroDadosExternos, manual
from valuation.servicos import mercado as mer

BASE = dt.date(2026, 10, 30)
AGORA = dt.datetime(2026, 10, 30, 12, tzinfo=dt.UTC)
EMPRESA = Empresa(
    cnpj="00.000.000/0001-00",
    cd_cvm=1234,
    razao_social="SINTETICA S.A.",
    nome_comercial="SINTETICA",
    setor_cvm="s",
    tipo_modelo="nao_financeira",
    escala_acoes=1,
    classes=(ClasseAcao("XXXX3", "ON"), ClasseAcao("XXXX4", "PN")),
)


class Falso:
    """Provedor que só conhece os símbolos de `fechamentos`."""

    nome = "falso"

    def __init__(self, fechamentos: dict[str, float]) -> None:
        self.fechamentos = fechamentos

    def historico(self, simbolo: str, inicio: dt.date, fim: dt.date) -> pd.DataFrame:
        simbolo = simbolo.removesuffix(".SA")
        if simbolo not in self.fechamentos:
            raise prc.ErroPrecos(f"{simbolo} fora do ar")
        v = self.fechamentos[simbolo]
        indice = pd.DatetimeIndex(["2026-10-29"], name="data")
        return pd.DataFrame({"close": [v], "adj_close": [v], "volume": [1.0]}, index=indice)

    def cotacao(self, simbolo: str) -> prc.Cotacao:
        raise prc.ErroPrecos("sem segunda fonte")


def _macro_falso() -> mac.Macro:
    return mac.Macro(
        BASE,
        selic=manual("Selic", 0.15),
        ipca_12m=manual("IPCA", 0.05),
        cambio=manual("Dólar", 5.0),
        rf_brl=manual("Rf", 0.13),
        ipca_esperado={},
        data_focus=None,
    )


def _composicao(tmp_path: Path) -> Path:
    pasta = tmp_path / "cvm" / "1234"
    pasta.mkdir(parents=True)
    pd.DataFrame(
        {
            "dt_refer": [pd.Timestamp("2026-06-30")],
            "qt_acao_ordin_cap_integr": [100],
            "qt_acao_pref_cap_integr": [50],
            "qt_acao_ordin_tesouro": [0],
            "qt_acao_pref_tesouro": [0],
        }
    ).to_parquet(pasta / "composicao_capital.parquet", index=False)
    return tmp_path


@pytest.fixture
def settings() -> Settings:
    return carregar_settings()


def test_cotacoes_marca_classe_sem_preco(tmp_path: Path, settings: Settings) -> None:
    yf = Falso({"XXXX3": 10.0})
    precos, cap, avisos = mer.cotacoes(
        EMPRESA, settings, BASE, yf, Falso({}), dir_processed=_composicao(tmp_path)
    )
    assert set(precos) == {"XXXX3"}
    assert precos["XXXX3"].valor == 10.0
    assert cap.valor == 1500.0  # 150 ações: a PN sem preço usa o preço de R$ 10 da ON
    assert len(avisos) == 1
    assert avisos[0].startswith("XXXX4 sem preço:")


def test_cotacoes_sem_nenhum_preco_falha_com_os_avisos_nas_notas(
    tmp_path: Path, settings: Settings
) -> None:
    with pytest.raises(ErroDadosExternos, match="Nenhum preço") as erro:
        mer.cotacoes(EMPRESA, settings, BASE, Falso({}), Falso({}), dir_processed=tmp_path)
    assert [n.split(":")[0] for n in erro.value.__notes__] == ["XXXX3 sem preço", "XXXX4 sem preço"]


def test_cotacoes_sem_composicao_pede_atualizar(tmp_path: Path, settings: Settings) -> None:
    yf = Falso({"XXXX3": 10.0, "XXXX4": 8.0})
    with pytest.raises(ErroDadosExternos, match="valuation atualizar --tickers XXXX3"):
        mer.cotacoes(EMPRESA, settings, BASE, yf, Falso({}), dir_processed=tmp_path)


def test_carregar_macro_avisa_dolar_sem_segunda_fonte(
    monkeypatch: pytest.MonkeyPatch, settings: Settings, tmp_path: Path
) -> None:
    recebido: dict[str, object] = {}

    def carregar(base: dt.date, **kw: object) -> mac.Macro:
        recebido.update(kw)
        return _macro_falso()

    monkeypatch.setattr(mer.mac, "carregar_macro", carregar)
    macro, avisos = mer.carregar_macro(
        settings, BASE, AGORA, False, Falso({}), sessao=object(), dir_raw=tmp_path
    )
    assert macro.selic.valor == 0.15
    assert avisos[0].startswith("dólar sem segunda fonte:")
    assert recebido["cambio_alternativo"] is None
    assert recebido["dir_raw"] == tmp_path

    _, avisos = mer.carregar_macro(
        settings, BASE, AGORA, False, Falso({"BRL=X": 5.1}), sessao=object(), dir_raw=tmp_path
    )
    assert avisos == []
    assert recebido["cambio_alternativo"].valor == 5.1  # type: ignore[attr-defined]


@pytest.fixture
def provedores_falsos(monkeypatch: pytest.MonkeyPatch) -> None:
    fechamentos = {"XXXX3": 10.0, "^BVSP": 100.0}
    monkeypatch.setattr(mer.prc, "YFinanceProvider", lambda *a, **k: Falso(fechamentos))
    monkeypatch.setattr(mer.prc, "BrapiProvider", lambda *a: Falso({}))
    monkeypatch.setattr(mer.cad, "empresa_por_ticker", lambda *a: EMPRESA)


def test_carregar_mercado_separa_avisos_da_coleta(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    tmp_path: Path,
    provedores_falsos: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(mer.mac, "carregar_macro", lambda *a, **k: _macro_falso())
    m = mer.carregar_mercado(
        "XXXX3",
        pd.DataFrame(),
        settings,
        BASE,
        AGORA,
        False,
        sessao=object(),
        dir_raw=tmp_path,
        dir_processed=_composicao(tmp_path),
    )
    assert [a.split(":")[0] for a in m.avisos_coleta] == [
        "XXXX4 sem preço",
        "dólar sem segunda fonte",
    ]
    assert not set(m.avisos_coleta) & set(m.avisos)
    assert m.todos_os_avisos == [*m.avisos_coleta, *m.avisos]
    assert m.ibov.valor == 100.0
    assert capsys.readouterr().out == ""


def test_carregar_mercado_com_erro_mantem_a_ordem_dos_avisos(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    tmp_path: Path,
    provedores_falsos: None,
) -> None:
    def falha(*_: object, **__: object) -> mac.Macro:
        raise ErroDadosExternos("macro fora do ar")

    monkeypatch.setattr(mer.mac, "carregar_macro", falha)
    with pytest.raises(ErroDadosExternos, match="macro fora do ar") as erro:
        mer.carregar_mercado(
            "XXXX3",
            pd.DataFrame(),
            settings,
            BASE,
            AGORA,
            False,
            sessao=object(),
            dir_raw=tmp_path,
            dir_processed=_composicao(tmp_path),
        )
    assert [n.split(":")[0] for n in erro.value.__notes__] == [
        "XXXX4 sem preço",
        "dólar sem segunda fonte",
    ]


def test_cli_imprime_avisos_da_coleta_e_devolve_o_mesmo_retorno(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "DIR_PROCESSED", _composicao(tmp_path))
    precos, cap = cli._cotacoes(EMPRESA, settings, BASE, Falso({"XXXX3": 10.0}), Falso({}))
    assert set(precos) == {"XXXX3"} and cap.valor > 0
    assert "XXXX4 sem preço" in capsys.readouterr().out


def test_cli_imprime_avisos_antes_de_repassar_o_erro(
    settings: Settings, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(ErroDadosExternos, match="Nenhum preço"):
        cli._cotacoes(EMPRESA, settings, BASE, Falso({}), Falso({}))
    saida = capsys.readouterr().out
    assert saida.index("XXXX3 sem preço") < saida.index("XXXX4 sem preço")
