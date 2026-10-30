import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from conftest import SessaoFalsa
from valuation.data import precos
from valuation.data.cadastro import ClasseAcao, Empresa
from valuation.data.validacao import ErroDadosExternos

BASE = dt.date(2026, 10, 30)
AGORA = dt.datetime(2026, 10, 30, 12, tzinfo=dt.UTC)


def hist(*pares: tuple[str, float]) -> pd.DataFrame:
    idx = pd.DatetimeIndex([p[0] for p in pares], name="data")
    return pd.DataFrame(
        {"close": [p[1] for p in pares], "adj_close": [p[1] for p in pares], "volume": 1.0},
        index=idx,
    )


class Falso:
    def __init__(self, nome: str, h: pd.DataFrame | None, c: precos.Cotacao | None) -> None:
        self.nome, self._h, self._c = nome, h, c

    def historico(self, simbolo: str, inicio: dt.date, fim: dt.date) -> pd.DataFrame:
        if self._h is None:
            raise precos.ErroPrecos("fora do ar")
        return self._h

    def cotacao(self, simbolo: str) -> precos.Cotacao:
        if self._c is None:
            raise precos.ErroPrecos("fora do ar")
        return self._c


def cot(preco: float, data: dt.date) -> precos.Cotacao:
    return precos.Cotacao("X", preco, data, None, "brapi")


def test_simbolo_yahoo() -> None:
    assert precos.simbolo_yahoo("PETR4") == "PETR4.SA"
    assert precos.simbolo_yahoo("^BVSP") == "^BVSP"
    assert precos.simbolo_yahoo("BRL=X") == "BRL=X"


def test_fechamento_ate_ignora_datas_futuras() -> None:
    h = hist(("2026-10-28", 10.0), ("2026-10-29", 11.0), ("2026-11-02", 99.0))
    assert precos.fechamento_ate(h, BASE) == (dt.date(2026, 10, 29), 11.0)
    with pytest.raises(precos.ErroPrecos):
        precos.fechamento_ate(h, dt.date(2026, 1, 1))


def test_preco_validado_concorda() -> None:
    p = Falso("yfinance", hist(("2026-10-29", 52.51)), None)
    a = Falso("brapi", None, cot(52.20, dt.date(2026, 10, 30)))
    v = precos.preco_validado("PETR4", BASE, p, a, tolerancia_rel=0.02)
    assert (v.status, v.valor, v.fonte_alt) == ("ok", 52.51, "brapi")


def test_preco_validado_divergente() -> None:
    p = Falso("yfinance", hist(("2026-10-29", 50.0)), None)
    a = Falso("brapi", None, cot(55.0, dt.date(2026, 10, 30)))
    assert precos.preco_validado("PETR4", BASE, p, a, tolerancia_rel=0.02).status == "divergente"


def test_cotacao_de_outra_data_nao_e_comparada() -> None:
    p = Falso("yfinance", hist(("2026-10-29", 50.0)), None)
    a = Falso("brapi", None, cot(80.0, dt.date(2026, 10, 1)))  # cotação de 29 dias antes
    assert precos.preco_validado("PETR4", BASE, p, a, tolerancia_rel=0.02).status == "sem_validacao"


def test_segunda_fonte_fora_do_ar_nao_e_erro() -> None:
    p = Falso("yfinance", hist(("2026-10-29", 50.0)), None)
    a = Falso("brapi", None, None)
    assert precos.preco_validado("WEGE3", BASE, p, a, tolerancia_rel=0.02).status == "sem_validacao"
    assert precos.preco_validado("WEGE3", BASE, p, None, tolerancia_rel=0.02).valor == 50.0


def test_fonte_principal_fora_do_ar_e_erro() -> None:
    p = Falso("yfinance", None, None)
    with pytest.raises(ErroDadosExternos):
        precos.preco_validado("WEGE3", BASE, p, None, tolerancia_rel=0.02)


def test_brapi_cotacao_e_mensagem_de_token(sessao_falsa: SessaoFalsa) -> None:
    corpo = (
        b'{"results":[{"symbol":"PETR4","regularMarketPrice":52.2,'
        b'"regularMarketTime":"2026-10-30T04:30:44.000Z","marketCap":716786125000}]}'
    )
    sessao_falsa.rotas["https://brapi.dev/api/quote/PETR4"] = (200, corpo, {})
    sessao_falsa.rotas["https://brapi.dev/api/quote/WEGE3"] = (
        401,
        b'{"error":true,"message":"Token de autentica\xc3\xa7\xc3\xa3o n\xc3\xa3o fornecido"}',
        {},
    )
    brapi = precos.BrapiProvider(sessao_falsa, token=None)
    c = brapi.cotacao("PETR4")
    assert (c.preco, c.data, c.market_cap) == (52.2, dt.date(2026, 10, 30), 716786125000.0)
    with pytest.raises(precos.ErroPrecos, match="BRAPI_TOKEN"):
        brapi.cotacao("WEGE3")


def test_brapi_envia_token_quando_existe(sessao_falsa: SessaoFalsa) -> None:
    sessao_falsa.rotas["https://brapi.dev/api/quote/WEGE3?token=abc"] = (
        200,
        b'{"results":[{"regularMarketPrice":40.0,"regularMarketTime":"2026-10-30T00:00:00Z"}]}',
        {},
    )
    assert precos.BrapiProvider(sessao_falsa, token="abc").cotacao("WEGE3").preco == 40.0


def test_brapi_historico(sessao_falsa: SessaoFalsa) -> None:
    ts = int(pd.Timestamp("2026-10-29").timestamp())
    sessao_falsa.rotas["https://brapi.dev/api/quote/PETR4?range=1y&interval=1d"] = (
        200,
        (
            b'{"results":[{"historicalDataPrice":[{"date":%d,"close":50.0,"volume":10,'
            b'"adjustedClose":49.0}]}]}' % ts
        ),
        {},
    )
    h = precos.BrapiProvider(sessao_falsa, token=None).historico(
        "PETR4", dt.date(2026, 10, 1), BASE
    )
    assert h.loc["2026-10-29", "close"] == 50.0
    assert h.loc["2026-10-29", "adj_close"] == 49.0


def test_yfinance_cacheia_e_usa_copia_vencida_se_falhar(tmp_path: Path) -> None:
    chamadas = []

    class Y(precos.YFinanceProvider):
        falhar = False

        def _baixar(self, simbolo: str, inicio: dt.date, fim: dt.date) -> pd.DataFrame:
            chamadas.append(simbolo)
            if self.falhar:
                raise precos.ErroPrecos("fora do ar")
            return hist(("2026-10-29", 10.0))

    ttl = dt.timedelta(hours=12)
    y = Y(tmp_path, ttl, AGORA)
    inicio = dt.date(2026, 10, 1)
    y.historico("PETR4.SA", inicio, BASE)
    y.historico("PETR4.SA", inicio, BASE)
    assert len(chamadas) == 1  # segunda leitura veio do cache

    vencido = Y(tmp_path, ttl, AGORA + dt.timedelta(days=2))
    vencido.falhar = True
    assert vencido.historico("PETR4.SA", inicio, BASE)["close"].iloc[0] == 10.0  # cópia vencida
    assert len(chamadas) == 2

    novo = Y(tmp_path, ttl, AGORA + dt.timedelta(days=2), forcar=True)
    novo.falhar = True
    with pytest.raises(precos.ErroPrecos):
        novo.historico("PETR4.SA", inicio, BASE)


def test_yfinance_tenta_de_novo_e_desiste(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import yfinance

    n = {"x": 0}

    class T:
        def __init__(self, _: str) -> None: ...

        def history(self, **_: object) -> pd.DataFrame:
            n["x"] += 1
            return pd.DataFrame()

    monkeypatch.setattr(yfinance, "Ticker", T)
    esperas: list[float] = []
    y = precos.YFinanceProvider(tmp_path, dt.timedelta(hours=1), AGORA, espera=esperas.append)
    with pytest.raises(precos.ErroPrecos, match=r"PETR4\.SA"):
        y.historico("PETR4.SA", dt.date(2026, 10, 1), BASE)
    assert n["x"] == 3 and esperas == [2.0, 4.0]


def empresa(*classes: tuple[str, str]) -> Empresa:
    return Empresa(
        cnpj="1",
        cd_cvm=1,
        razao_social="X",
        nome_comercial="X",
        setor_cvm="s",
        tipo_modelo="nao_financeira",
        escala_acoes=1,
        classes=tuple(ClasseAcao(t, e) for t, e in classes),  # type: ignore[arg-type]
    )


def composicao(on: int, pn: int, on_tes: int = 0, pn_tes: int = 0) -> pd.DataFrame:
    base = {
        "qt_acao_ordin_cap_integr": on,
        "qt_acao_pref_cap_integr": pn,
        "qt_acao_ordin_tesouro": on_tes,
        "qt_acao_pref_tesouro": pn_tes,
    }
    return pd.DataFrame(
        [
            {"dt_refer": pd.Timestamp("2025-12-31"), **{k: 1 for k in base}},
            {"dt_refer": pd.Timestamp("2026-06-30"), **base},
            {"dt_refer": pd.Timestamp("2027-01-01"), **{k: 7 for k in base}},  # futuro
        ]
    )


def test_market_cap_duas_classes_sem_tesouraria() -> None:
    mc = precos.market_cap(
        empresa(("XXXX3", "ON"), ("XXXX4", "PN")),
        composicao(100, 50, on_tes=10, pn_tes=0),
        {"XXXX3": 10.0, "XXXX4": 8.0},
        BASE,
    )
    assert mc.valor == 90 * 10.0 + 50 * 8.0
    assert mc.data_acoes == dt.date(2026, 6, 30)
    assert mc.avisos == ()


def test_market_cap_classe_sem_ticker_usa_a_outra_com_aviso() -> None:
    mc = precos.market_cap(empresa(("XXXX3", "ON")), composicao(100, 50), {"XXXX3": 10.0}, BASE)
    assert mc.valor == 150 * 10.0
    assert len(mc.avisos) == 1 and "PN" in mc.avisos[0]


def test_market_cap_classe_sem_acoes_e_ignorada() -> None:
    mc = precos.market_cap(empresa(("VALE3", "ON")), composicao(100, 0), {"VALE3": 2.0}, BASE)
    assert mc.valor == 200.0 and mc.avisos == ()


def test_market_cap_sem_preco_ou_sem_composicao() -> None:
    e = empresa(("XXXX3", "ON"))
    with pytest.raises(precos.ErroPrecos, match="preço"):
        precos.market_cap(e, composicao(1, 1), {}, BASE)
    with pytest.raises(precos.ErroPrecos, match="composição"):
        precos.market_cap(e, composicao(1, 1), {"XXXX3": 1.0}, dt.date(2020, 1, 1))
