import datetime as dt
import json
from pathlib import Path

import pandas as pd
import pytest
import requests

from conftest import resposta
from valuation.config import ValidacaoCruzada
from valuation.data import macro
from valuation.data.validacao import ErroDadosExternos, Leitura

BASE = dt.date(2026, 10, 30)
AGORA = dt.datetime(2026, 10, 30, 12, tzinfo=dt.UTC)
TTL = dt.timedelta(hours=12)
TOL = ValidacaoCruzada(
    preco_rel=0.02,
    cambio_rel=0.015,
    market_cap_rel=0.1,
    selic_abs=0.003,
    ipca_abs=0.0005,
    rf_abs=0.025,
)

TESOURO_CSV = (
    "Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manha;Taxa Venda Manha;"
    "PU Compra Manha;PU Venda Manha;PU Base Manha\n"
    "Tesouro Prefixado com Juros Semestrais;01/01/2037;28/10/2026;14,87;14,97;1;1;1\n"
    "Tesouro Prefixado com Juros Semestrais;01/01/2031;28/10/2026;15,03;15,13;1;1;1\n"
    "Tesouro Prefixado com Juros Semestrais;01/01/2037;27/10/2026;99,00;99,00;1;1;1\n"
    "Tesouro IPCA+ com Juros Semestrais;15/05/2037;28/10/2026;7,72;7,80;1;1;1\n"
    "Tesouro Selic;01/03/2028;28/10/2026;0,02;0,03;1;1;1\n"
)


class SessaoPorPrefixo:
    """Responde pelo trecho da URL; conta as chamadas por trecho."""

    def __init__(self, rotas: dict[str, tuple[int, bytes]]) -> None:
        self.rotas = rotas
        self.chamadas: list[str] = []

    def get(self, url: str, *, headers: dict[str, str], timeout: float, stream: bool):  # type: ignore[no-untyped-def]
        self.chamadas.append(url)
        for trecho, (status, corpo) in self.rotas.items():
            if trecho in url:
                return resposta(status, corpo)
        return resposta(404)


def sgs(*pares: tuple[str, str]) -> tuple[int, bytes]:
    return 200, json.dumps([{"data": d, "valor": v} for d, v in pares]).encode()


def rotas_ok() -> dict[str, tuple[int, bytes]]:
    mensal = [(f"01/{m:02d}/2026", "0.40") for m in range(1, 10)] + [
        (f"01/{m:02d}/2025", "0.40") for m in (10, 11, 12)
    ]
    focus = {
        "value": [
            {"Data": "2026-10-23", "DataReferencia": "2029", "Mediana": 3.5},
            {"Data": "2026-10-23", "DataReferencia": "2030", "Mediana": 3.5},
            {"Data": "2026-10-22", "DataReferencia": "2030", "Mediana": 9.9},
        ]
    }
    return {
        "sgs.432/": sgs(("29/10/2026", "13.75"), ("30/10/2026", "13.75"), ("02/11/2026", "99")),
        "sgs.11/": sgs(("29/10/2026", "0.0507"), ("30/10/2026", "0.0507")),
        "sgs.13522/": sgs(("01/09/2026", "4.91")),
        "sgs.433/": sgs(*mensal),
        "sgs.1/": sgs(("29/10/2026", "5.3744")),
        "ExpectativasMercadoAnuais": (200, json.dumps(focus).encode()),
        "precotaxatesourodireto": (200, TESOURO_CSV.encode("latin-1")),
    }


def carregar(sessao: SessaoPorPrefixo, tmp_path: Path, **kw: object) -> macro.Macro:
    args = {
        "tolerancias": TOL,
        "rf_override": None,
        "cambio_alternativo": Leitura(5.38, "yf"),
        "dir_raw": tmp_path,
        "ttl": TTL,
        "sessao": sessao,
        "agora": AGORA,
    }
    return macro.carregar_macro(BASE, **{**args, **kw})  # type: ignore[arg-type]


def test_serie_sgs_converte_e_ordena(tmp_path: Path) -> None:
    sessao = SessaoPorPrefixo({"sgs.1/": sgs(("29/10/2026", "5.37"), ("28/10/2026", "5.34"))})
    s = macro.serie_sgs(
        1, BASE - dt.timedelta(days=5), BASE, dir_raw=tmp_path, ttl=TTL, sessao=sessao, agora=AGORA
    )
    assert list(s) == [5.34, 5.37]
    assert s.index[0] == pd.Timestamp(2026, 10, 28)


def test_serie_sgs_vazia_e_erro(tmp_path: Path) -> None:
    sessao = SessaoPorPrefixo({"sgs.1/": (200, b"[]")})
    with pytest.raises(ErroDadosExternos):
        macro.serie_sgs(1, BASE, BASE, dir_raw=tmp_path, ttl=TTL, sessao=sessao, agora=AGORA)


def test_focus_pega_ultima_pesquisa_e_converte_para_decimal(tmp_path: Path) -> None:
    sessao = SessaoPorPrefixo(rotas_ok())
    data, por_ano = macro.focus_anual(
        "IPCA", BASE, dir_raw=tmp_path, ttl=TTL, sessao=sessao, agora=AGORA
    )
    assert data == dt.date(2026, 10, 23)
    assert por_ano == {2029: 0.035, 2030: 0.035}
    assert "Indicador%20eq%20%27IPCA%27" in sessao.chamadas[0]


def test_titulo_longo_usa_ultima_data_e_vencimento_perto_de_10_anos(tmp_path: Path) -> None:
    sessao = SessaoPorPrefixo(rotas_ok())
    taxas = macro.carregar_taxas_tesouro(dir_raw=tmp_path, ttl=TTL, sessao=sessao, agora=AGORA)
    assert set(taxas["tipo"]) == {macro.TITULO_NTNF, macro.TITULO_NTNB}  # Selic descartado
    t = macro.titulo_longo(taxas, macro.TITULO_NTNF, BASE)
    assert (t.vencimento, t.data_base, t.taxa) == (
        dt.date(2037, 1, 1),
        dt.date(2026, 10, 28),
        0.1487,
    )


def test_titulo_longo_sem_vencimento_adequado(tmp_path: Path) -> None:
    sessao = SessaoPorPrefixo(rotas_ok())
    taxas = macro.carregar_taxas_tesouro(dir_raw=tmp_path, ttl=TTL, sessao=sessao, agora=AGORA)
    taxas = taxas.loc[taxas["vencimento"].dt.year == 2031]
    with pytest.raises(ErroDadosExternos, match="vencimento"):
        macro.titulo_longo(taxas, macro.TITULO_NTNF, BASE)


def test_macro_completo_valida_cada_dado(tmp_path: Path) -> None:
    m = carregar(SessaoPorPrefixo(rotas_ok()), tmp_path)
    assert m.selic.valor == 0.1375 and m.selic.data == dt.date(2026, 10, 30)  # ignora 02/11
    assert m.selic.status == "ok"
    assert m.ipca_12m.valor == pytest.approx(0.0491)
    assert m.ipca_12m.status == "ok"
    assert m.cambio.valor == 5.3744 and m.cambio.status == "ok"
    assert m.rf_brl.valor == 0.1487
    # (1+7,72%)*(1+3,5%)-1 = 11,49% contra 14,87%: 3,4 p.p. > 2,5 p.p.
    assert m.rf_brl.status == "divergente"
    assert m.ipca_esperado == {2029: 0.035, 2030: 0.035}
    assert m.pib_esperado == {2029: 0.035, 2030: 0.035}  # a rota falsa serve o mesmo JSON
    assert any("Rf BRL" in a for a in m.avisos)


def test_rf_manual_nao_baixa_tesouro(tmp_path: Path) -> None:
    sessao = SessaoPorPrefixo(rotas_ok())
    m = carregar(sessao, tmp_path, rf_override=0.12)
    assert (m.rf_brl.valor, m.rf_brl.status) == (0.12, "manual")
    assert not any("tesouro" in u for u in sessao.chamadas)


def test_fonte_fora_do_ar_nao_derruba_se_a_outra_responde(tmp_path: Path) -> None:
    rotas = rotas_ok()
    rotas["sgs.11/"] = (500, b"")
    # 500 sem retry na sessão falsa -> ErroDownload; a Selic meta cobre
    m = carregar(SessaoPorPrefixo(rotas), tmp_path)
    assert m.selic.status == "sem_validacao"
    assert m.selic.valor == 0.1375


def test_sem_nenhuma_fonte_de_um_dado_e_erro(tmp_path: Path) -> None:
    rotas = rotas_ok()
    rotas["sgs.432/"] = (500, b"")
    rotas["sgs.11/"] = (500, b"")
    with pytest.raises(ErroDadosExternos, match="Selic"):
        carregar(SessaoPorPrefixo(rotas), tmp_path)


def test_rede_fora_do_ar_propaga_para_tesouro(tmp_path: Path) -> None:
    class Quebrada:
        def get(self, url: str, **_: object) -> requests.Response:
            raise requests.ConnectionError("sem rede")

    with pytest.raises(ErroDadosExternos):
        carregar(Quebrada(), tmp_path)  # type: ignore[arg-type]


def test_focus_do_pib_consulta_o_indicador_pib_total(tmp_path: Path) -> None:
    sessao = SessaoPorPrefixo(rotas_ok())
    carregar(sessao, tmp_path)
    assert any("PIB%20Total" in c for c in sessao.chamadas)


def test_focus_do_pib_indisponivel_nao_derruba_o_macro(tmp_path: Path) -> None:
    rotas = rotas_ok()
    sessao = SessaoPorPrefixo(rotas)
    original = sessao.get

    def get(url: str, **kw: object) -> object:
        if "PIB" in url:
            raise OSError("fora do ar")
        return original(url, **kw)  # type: ignore[arg-type]

    sessao.get = get  # type: ignore[method-assign]
    m = carregar(sessao, tmp_path)
    assert m.pib_esperado == {}
    assert m.ipca_esperado
