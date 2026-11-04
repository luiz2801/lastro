"""Carteira pessoal, Etapa C2: posição, preço médio, resultado e `carteira posicao`."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from typer.testing import CliRunner

from valuation import cli
from valuation.carteira import posicao as ps
from valuation.carteira import transacoes as tr
from valuation.cli import app

D = dt.date


def t(data: dt.date, ticker: str, tipo: str, q: float, **kw: float | None) -> tr.Transacao:
    return tr.nova_transacao(data, ticker, tipo, q, **kw)


# Caso calculado à mão (PETR4), custo e quantidade ao fim de cada passo:
#   compra 100 x 10,00 + 5 taxas       -> 100 ações, custo 1.005,00, PM 10,05
#   compra 100 x 12,00 + 5 taxas       -> 200 ações, custo 2.210,00, PM 11,05
#   venda   50 x 15,00 - 5 taxas       -> baixa 2.210 x 50/200 = 552,50; líquido 745,00;
#                                         realizado 192,50; 150 ações, custo 1.657,50, PM 11,05
#   desdobramento 2x                   -> 300 ações, custo 1.657,50, PM 5,525
#   bonificação 30                     -> 330 ações, custo 1.657,50, PM 5,0227...
#   provento 100 - 15 retido           -> 85,00
HISTORICO = [
    t(D(2026, 1, 5), "PETR4", "compra", 100, preco=10, taxas=5),
    t(D(2026, 2, 5), "PETR4", "compra", 100, preco=12, taxas=5),
    t(D(2026, 3, 5), "PETR4", "venda", 50, preco=15, taxas=5),
    t(D(2026, 4, 5), "PETR4", "desdobramento", 2),
    t(D(2026, 5, 5), "PETR4", "bonificacao", 30),
    t(D(2026, 6, 5), "PETR4", "provento", 330, valor=100, taxas=15),
]


def test_preco_medio_passo_a_passo() -> None:
    esperado = [
        (D(2026, 1, 5), 100, 1005.0, 10.05),
        (D(2026, 2, 5), 200, 2210.0, 11.05),
        (D(2026, 3, 5), 150, 1657.5, 11.05),
        (D(2026, 4, 5), 300, 1657.5, 5.525),
        (D(2026, 5, 5), 330, 1657.5, 1657.5 / 330),
        (D(2026, 6, 5), 330, 1657.5, 1657.5 / 330),
    ]
    for data, qtd, custo, pm in esperado:
        p = ps.calcular_posicoes(HISTORICO, data)["PETR4"]
        assert p.quantidade == pytest.approx(qtd)
        assert p.custo == pytest.approx(custo)
        assert p.preco_medio == pytest.approx(pm)


def test_acumulados_e_realizado() -> None:
    p = ps.calcular_posicoes(HISTORICO, D(2026, 6, 30))["PETR4"]
    assert p.compras == pytest.approx(2210.0)
    assert p.vendas == pytest.approx(745.0)
    assert p.realizado == pytest.approx(192.5)
    assert p.proventos == pytest.approx(85.0)


def test_resultado_total_confere_com_realizado_mais_nao_realizado_mais_proventos() -> None:
    posicoes = ps.calcular_posicoes(HISTORICO, D(2026, 6, 30))
    r = ps.avaliar(posicoes, {"PETR4": ps.Preco(8.0, D(2026, 6, 30))}, D(2026, 6, 30))
    ln = r.linhas[0]
    p = ln.posicao
    assert ln.patrimonio == pytest.approx(2640.0)
    assert ln.nao_realizado == pytest.approx(982.5)
    assert ln.resultado == pytest.approx(1260.0)  # 2.640 + 745 + 85 - 2.210
    assert ln.resultado == pytest.approx(ln.nao_realizado + p.realizado + p.proventos)
    assert ln.resultado_pct == pytest.approx(1260 / 2210)
    assert (r.patrimonio, r.resultado, r.completo, r.avisos) == (
        pytest.approx(2640.0),
        pytest.approx(1260.0),
        True,
        (),
    )


def test_data_base_ignora_transacoes_posteriores() -> None:
    posicoes = ps.calcular_posicoes(HISTORICO, D(2026, 2, 4))
    assert posicoes["PETR4"].quantidade == 100
    assert ps.calcular_posicoes(HISTORICO, D(2025, 12, 31)) == {}


def test_agrupamento_mantem_o_custo() -> None:
    hist = [
        t(D(2026, 1, 5), "VALE3", "compra", 100, preco=2),
        t(D(2026, 2, 5), "VALE3", "agrupamento", 4),
    ]
    p = ps.calcular_posicoes(hist, D(2026, 3, 1))["VALE3"]
    assert (p.quantidade, p.custo, p.preco_medio) == (25, 200.0, 8.0)


def test_venda_total_zera_posicao_e_custo() -> None:
    hist = [
        t(D(2026, 1, 5), "WEGE3", "compra", 3, preco=10.1),
        t(D(2026, 2, 5), "WEGE3", "venda", 3, preco=12),
    ]
    p = ps.calcular_posicoes(hist, D(2026, 3, 1))["WEGE3"]
    assert p.encerrada and p.custo == 0.0 and p.preco_medio is None
    assert p.realizado == pytest.approx(36 - 30.3)
    r = ps.avaliar({"WEGE3": p}, {}, D(2026, 3, 1))  # encerrada não precisa de cotação
    assert r.completo and r.resultado == pytest.approx(5.7) and r.patrimonio == 0.0


def test_provento_de_ticker_sem_posicao_atual() -> None:
    hist = [
        t(D(2026, 1, 5), "ITUB4", "compra", 10, preco=30),
        t(D(2026, 1, 6), "ITUB4", "venda", 10, preco=30),
    ]
    hist.append(t(D(2026, 1, 7), "ITUB4", "provento", 10, valor=20))
    p = ps.calcular_posicoes(hist, D(2026, 2, 1))["ITUB4"]
    assert p.proventos == 20.0 and p.encerrada


def test_sem_cotacao_gera_aviso_e_totais_parciais() -> None:
    hist = [
        t(D(2026, 1, 5), "PETR4", "compra", 10, preco=10),
        t(D(2026, 1, 5), "VALE3", "compra", 10, preco=50),
    ]
    posicoes = ps.calcular_posicoes(hist, D(2026, 1, 10))
    r = ps.avaliar(posicoes, {"PETR4": ps.Preco(11.0, D(2026, 1, 9))}, D(2026, 1, 10))
    assert not r.completo
    assert any("sem cotação para VALE3" in a for a in r.avisos)
    assert r.patrimonio == pytest.approx(110.0) and r.compras == pytest.approx(100.0)
    vale = next(ln for ln in r.linhas if ln.posicao.ticker == "VALE3")
    assert vale.patrimonio is None and vale.resultado is None


def test_cotacao_defasada_avisa() -> None:
    compra = t(D(2026, 1, 5), "PETR4", "compra", 10, preco=10)
    posicoes = ps.calcular_posicoes([compra], D(2026, 1, 31))
    r = ps.avaliar(posicoes, {"PETR4": ps.Preco(11.0, D(2026, 1, 20))}, D(2026, 1, 31))
    assert any("defasada" in a and "11 dias" in a for a in r.avisos)
    ok = ps.avaliar(posicoes, {"PETR4": ps.Preco(11.0, D(2026, 1, 26))}, D(2026, 1, 31))
    assert ok.avisos == ()


def test_venda_acima_da_posicao_e_erro_de_programacao() -> None:
    # `calcular_posicoes` presume histórico validado; sem isso falha alto, não em silêncio
    venda = tr.Transacao(D(2026, 1, 5), "PETR4", tr.TipoTransacao.VENDA, 1, 10.0, 10.0, 0.0, "")
    with pytest.raises(ValueError, match="acima da posição"):
        ps.calcular_posicoes([venda], D(2026, 2, 1))


# --- comando -----------------------------------------------------------------------------------


@pytest.fixture
def carteira_com_historico(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    caminho = tmp_path / "carteira" / "transacoes.csv"
    monkeypatch.setattr(cli, "CAMINHO_TRANSACOES", caminho)
    return caminho


def test_cli_posicao_carteira_vazia(carteira_com_historico: Path) -> None:
    r = CliRunner().invoke(app, ["carteira", "posicao", "--data-base", "2026-06-30"])
    assert r.exit_code == 0, r.output
    assert "Carteira vazia" in r.output


def test_cli_posicao_tabela_e_avisos(
    carteira_com_historico: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cmd = CliRunner()
    for args in (
        ["compra", "PETR4", "100", "--preco", "10", "--taxas", "5", "--data", "2026-01-05"],
        ["compra", "PETR4", "100", "--preco", "12", "--taxas", "5", "--data", "2026-02-05"],
        ["venda", "PETR4", "50", "--preco", "15", "--taxas", "5", "--data", "2026-03-05"],
        ["compra", "VALE3", "10", "--preco", "50", "--data", "2026-03-06"],
    ):
        assert cmd.invoke(app, ["carteira", "lancar", *args]).exit_code == 0

    pedidos: list[list[str]] = []

    def cotar(tickers: list[str], *_: object) -> tuple[dict[str, ps.Preco], list[str]]:
        pedidos.append(tickers)
        return {"PETR4": ps.Preco(8.0, D(2026, 6, 30))}, ["VALE3 sem preço: fora do ar"]

    monkeypatch.setattr(cli, "_cotar_carteira", cotar)
    r = cmd.invoke(
        app, ["carteira", "posicao", "--data-base", "2026-06-30"], env={"COLUMNS": "200"}
    )
    assert r.exit_code == 0, r.output
    assert pedidos == [["PETR4", "VALE3"]]
    assert "Carteira em 2026-06-30" in r.output
    assert "R$ 11,05" in r.output  # preço médio da PETR4
    assert "R$ 1.657,50" in r.output  # custo da PETR4 aberta
    assert "sem cotação para VALE3" in r.output
    assert "VALE3 sem preço" in r.output


def test_cli_posicao_data_base_invalida(carteira_com_historico: Path) -> None:
    r = CliRunner().invoke(app, ["carteira", "posicao", "--data-base", "ontem"])
    assert r.exit_code == 1
    assert "--data-base inválida" in r.output
