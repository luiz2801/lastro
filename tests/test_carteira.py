"""Carteira pessoal, Etapa C1: esquema das transações, histórico, CSV/XLSX e comandos."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from openpyxl import Workbook
from typer.testing import CliRunner

from valuation import cli
from valuation.carteira import ErroCarteira
from valuation.carteira import arquivo as arq
from valuation.carteira import transacoes as tr
from valuation.cli import app
from valuation.config import ConfigCsv
from valuation.saida.csv import INTERNACIONAL

BR = ConfigCsv()
D = dt.date


def nova(
    data: dt.date, ticker: str, tipo: str, quantidade: float, **kw: float | None
) -> tr.Transacao:
    return tr.nova_transacao(data, ticker, tipo, quantidade, **kw)


# --- esquema de cada linha ---------------------------------------------------------------------


def test_compra_calcula_valor_bruto_sem_taxas() -> None:
    t = nova(D(2026, 1, 5), " petr4 ", "Compra", 100, preco=35.5, taxas=4.9)
    assert (t.ticker, t.tipo, t.valor, t.taxas) == ("PETR4", tr.TipoTransacao.COMPRA, 3550.0, 4.9)


def test_tipo_aceita_acento_e_caixa() -> None:
    assert nova(D(2026, 1, 5), "PETR4", "BONIFICAÇÃO", 10).tipo is tr.TipoTransacao.BONIFICACAO


@pytest.mark.parametrize(
    ("tipo", "quantidade", "kw", "trecho"),
    [
        ("compra", 100, {}, "exige preco"),
        ("compra", 100, {"preco": 0}, "exige preco"),
        ("compra", 0, {"preco": 10}, "quantidade deve ser maior"),
        ("compra", -5, {"preco": 10}, "quantidade deve ser maior"),
        ("compra", 10, {"preco": -1}, "preco não pode ser negativo"),
        ("compra", 10, {"preco": 10, "valor": 150}, "difere de quantidade x preco"),
        ("compra", 10, {"preco": 10, "taxas": -1}, "taxas não pode ser negativa"),
        ("compra", float("nan"), {"preco": 10}, "não é um número finito"),
        ("provento", 100, {}, "exige valor"),
        ("provento", 100, {"valor": 0}, "maior que zero"),
        ("desdobramento", 1, {}, "fator"),
        ("agrupamento", 0.5, {}, "fator"),
        ("desdobramento", 2, {"preco": 10}, "não leva preco"),
        ("bonificacao", 10, {"valor": 5}, "não leva valor"),
        ("doacao", 10, {}, "tipo desconhecido"),
    ],
)
def test_linha_invalida(tipo: str, quantidade: float, kw: dict[str, float], trecho: str) -> None:
    with pytest.raises(ErroCarteira, match=trecho):
        nova(D(2026, 1, 5), "PETR4", tipo, quantidade, **kw)


@pytest.mark.parametrize("ticker", ["PET4", "PETR", "PETR4F", "PETR444", "PE TR4", ""])
def test_ticker_invalido(ticker: str) -> None:
    with pytest.raises(ErroCarteira, match="ticker inválido"):
        nova(D(2026, 1, 5), ticker, "compra", 1, preco=1)


def test_provento_por_quantidade_e_preco_ou_valor() -> None:
    assert nova(D(2026, 3, 1), "ITUB4", "provento", 200, preco=0.25).valor == 50.0
    assert nova(D(2026, 3, 1), "ITUB4", "provento", 200, valor=50, taxas=7.5).taxas == 7.5
    with pytest.raises(ErroCarteira, match="difere"):
        nova(D(2026, 3, 1), "ITUB4", "provento", 200, preco=0.25, valor=80)


def test_observacao_vira_uma_linha() -> None:
    t = nova(D(2026, 1, 5), "PETR4", "compra", 1, preco=1)
    assert (
        tr.nova_transacao(t.data, "PETR4", "compra", 1, 1, observacao="a\n  b").observacao == "a b"
    )


# --- histórico ---------------------------------------------------------------------------------


def historico(*ts: tr.Transacao, hoje: dt.date | None = None) -> None:
    tr.validar_historico(ts, hoje=hoje)


def test_venda_acima_da_posicao_aponta_a_transacao() -> None:
    compra = nova(D(2026, 1, 5), "PETR4", "compra", 100, preco=30)
    venda = nova(D(2026, 2, 5), "PETR4", "venda", 101, preco=35)
    with pytest.raises(ErroCarteira, match=r"transação 2: venda de 101 PETR4.*posição \(100\)"):
        historico(compra, venda)
    historico(compra, nova(D(2026, 2, 5), "PETR4", "venda", 100, preco=35))


def test_posicao_e_por_ticker_e_cronologica() -> None:
    venda = nova(D(2026, 1, 1), "VALE3", "venda", 10, preco=60)
    compra_outra = nova(D(2026, 1, 1), "PETR4", "compra", 10, preco=30)
    compra_tarde = nova(D(2026, 2, 1), "VALE3", "compra", 10, preco=60)
    with pytest.raises(ErroCarteira, match="transação 1"):
        historico(venda, compra_outra, compra_tarde)
    # fora de ordem no arquivo, mas a compra é anterior à venda: vale
    historico(nova(D(2026, 3, 1), "VALE3", "venda", 10, preco=60), compra_tarde)


def test_mesmo_dia_vale_a_ordem_do_arquivo() -> None:
    compra = nova(D(2026, 1, 5), "PETR4", "compra", 10, preco=30)
    venda = nova(D(2026, 1, 5), "PETR4", "venda", 10, preco=31)
    historico(compra, venda)
    with pytest.raises(ErroCarteira, match="ordem do arquivo"):
        historico(venda, compra)


def test_desdobramento_agrupamento_e_bonificacao_mudam_a_posicao() -> None:
    compra = nova(D(2026, 1, 5), "WEGE3", "compra", 100, preco=40)
    desdobra = nova(D(2026, 2, 1), "WEGE3", "desdobramento", 2)  # 200
    bonus = nova(D(2026, 3, 1), "WEGE3", "bonificacao", 20)  # 220
    historico(compra, desdobra, bonus, nova(D(2026, 4, 1), "WEGE3", "venda", 220, preco=20))
    agrupa = nova(D(2026, 3, 1), "WEGE3", "agrupamento", 10)  # 200 / 10 = 20
    with pytest.raises(ErroCarteira, match="venda de 21"):
        historico(compra, desdobra, agrupa, nova(D(2026, 4, 1), "WEGE3", "venda", 21, preco=1))
    historico(compra, desdobra, agrupa, nova(D(2026, 4, 1), "WEGE3", "venda", 20, preco=1))


def test_evento_sem_posicao_e_data_futura_e_todos_os_erros_juntos() -> None:
    evento = nova(D(2026, 1, 5), "WEGE3", "desdobramento", 2)
    futura = nova(D(2027, 1, 5), "PETR4", "compra", 1, preco=1)
    with pytest.raises(ErroCarteira) as e:
        historico(evento, futura, hoje=D(2026, 10, 31))
    assert len(e.value.erros) == 2
    assert "sem posição" in e.value.erros[0]
    assert "no futuro" in e.value.erros[1]


def test_proventos_nao_alteram_a_posicao() -> None:
    provento = nova(D(2026, 1, 5), "ITUB4", "provento", 100, valor=30)
    historico(provento, nova(D(2026, 1, 6), "ITUB4", "compra", 100, preco=30))


# --- leitura de CSV e XLSX ---------------------------------------------------------------------

CSV_BR = (
    "data;ticker;tipo;quantidade;preco;valor;taxas;observacao\n"
    "2026-01-05;PETR4;compra;1.000;35,5;;4,9;primeira\n"
    "06/02/2026;petr4;venda;400;40;;;\n"
    "2026-03-10;PETR4;provento;600;;120,5;18,07;JCP\n"
)


def escrever(caminho: Path, texto: str, encoding: str = "utf-8-sig") -> Path:
    caminho.write_text(texto, encoding=encoding)
    return caminho


def esperadas() -> list[tr.Transacao]:
    return [
        nova(D(2026, 1, 5), "PETR4", "compra", 1000, preco=35.5, taxas=4.9, observacao="primeira"),
        nova(D(2026, 2, 6), "PETR4", "venda", 400, preco=40),
        nova(D(2026, 3, 10), "PETR4", "provento", 600, valor=120.5, taxas=18.07, observacao="JCP"),
    ]


def test_ler_csv_br_com_milhar_data_br_e_linha_de_cada_registro(tmp_path: Path) -> None:
    ts, linhas = arq.ler_arquivo(escrever(tmp_path / "t.csv", CSV_BR), BR)
    assert ts == esperadas()
    assert linhas == [2, 3, 4]


def test_xlsx_e_csv_equivalentes(tmp_path: Path) -> None:
    pasta = Workbook()
    aba = pasta.active
    assert aba is not None
    aba.append(list(arq.COLUNAS))
    aba.append([dt.datetime(2026, 1, 5), "PETR4", "compra", 1000, "35,5", None, 4.9, "primeira"])
    aba.append([None] * 8)  # linha em branco é ignorada, mas conta na numeração
    aba.append([dt.date(2026, 2, 6), "PETR4", "venda", 400, 40, None, None, None])
    aba.append([dt.datetime(2026, 3, 10), "PETR4", "provento", 600, None, 120.5, 18.07, "JCP"])
    caminho = tmp_path / "t.xlsx"
    pasta.save(caminho)
    ts, linhas = arq.ler_arquivo(caminho, BR)
    assert ts == esperadas()
    assert linhas == [2, 4, 5]


def test_csv_internacional(tmp_path: Path) -> None:
    texto = 'data,ticker,tipo,quantidade,preco\n2026-01-05,PETR4,compra,"1,000",35.5\n'
    ts, _ = arq.ler_arquivo(escrever(tmp_path / "t.csv", texto, "utf-8"), INTERNACIONAL)
    assert (ts[0].quantidade, ts[0].preco) == (1000.0, 35.5)


def test_arquivo_inteiro_recusado_com_todas_as_linhas_com_erro(tmp_path: Path) -> None:
    texto = (
        "data;ticker;tipo;quantidade;preco\n"
        "2026-01-05;PETR4;compra;100;35,5\n"
        "2026-13-05;PETR4;compra;100;35,5\n"
        "2026-01-06;PETR4;compra;1.5;35,5\n"
        "2026-01-07;PETR4;compra;;35,5\n"
        "2026-01-08;PETR4;compra;10;-3\n"
    )
    with pytest.raises(ErroCarteira) as e:
        arq.ler_arquivo(escrever(tmp_path / "t.csv", texto), BR)
    erros = e.value.erros
    assert [m.split(":")[0] for m in erros] == ["linha 3", "linha 4", "linha 5", "linha 6"]
    assert "data inválida" in erros[0]
    assert "número inválido '1.5'" in erros[1]  # não vira 15
    assert "coluna 'quantidade' vazia" in erros[2]
    assert "preco não pode ser negativo" in erros[3]


@pytest.mark.parametrize(
    ("cabecalho", "trecho"),
    [
        ("data;ticker;tipo", "faltam as colunas quantidade"),
        ("data;ticker;tipo;quantidade;corretora", "colunas desconhecidas: corretora"),
    ],
)
def test_cabecalho_invalido(tmp_path: Path, cabecalho: str, trecho: str) -> None:
    with pytest.raises(ErroCarteira, match=trecho):
        arq.ler_arquivo(escrever(tmp_path / "t.csv", cabecalho + "\n"), BR)


def test_arquivo_ausente_vazio_ou_de_outro_formato(tmp_path: Path) -> None:
    with pytest.raises(ErroCarteira, match="não encontrado"):
        arq.ler_arquivo(tmp_path / "nao_existe.csv", BR)
    with pytest.raises(ErroCarteira, match="vazio"):
        arq.ler_arquivo(escrever(tmp_path / "v.csv", ""), BR)
    with pytest.raises(ErroCarteira, match="não suportado"):
        arq.ler_arquivo(escrever(tmp_path / "t.pdf", "x"), BR)


# --- gravação ----------------------------------------------------------------------------------


def test_acrescentar_cria_com_cabecalho_e_bom_uma_vez_e_nao_reescreve(tmp_path: Path) -> None:
    caminho = tmp_path / "carteira" / "transacoes.csv"
    primeira, segunda, terceira = esperadas()
    assert arq.acrescentar(caminho, BR, [primeira]) == 1
    antes = caminho.read_bytes()
    assert antes.startswith(
        b"\xef\xbb\xbfdata;ticker;tipo;quantidade;preco;valor;taxas;observacao\n"
    )
    arq.acrescentar(caminho, BR, [segunda, terceira])
    depois = caminho.read_bytes()
    assert depois.startswith(antes)  # histórico intacto
    assert depois.count(b"\xef\xbb\xbf") == 1
    assert depois.decode("utf-8-sig").splitlines()[1:] == [
        "2026-01-05;PETR4;compra;1000;35,5;35500;4,9;primeira",
        "2026-02-06;PETR4;venda;400;40;16000;;",
        "2026-03-10;PETR4;provento;600;;120,5;18,07;JCP",
    ]
    ts, linhas = arq.carregar(caminho, BR)
    assert ts == esperadas()
    assert linhas == [2, 3, 4]


def test_acrescentar_completa_arquivo_sem_quebra_final(tmp_path: Path) -> None:
    caminho = escrever(tmp_path / "t.csv", CSV_BR.rstrip("\n"))
    arq.acrescentar(caminho, BR, [nova(D(2026, 4, 1), "PETR4", "compra", 10, preco=1)])
    assert len(arq.carregar(caminho, BR)[0]) == 4


def test_acrescentar_nao_grava_nada_se_o_historico_nao_fecha(tmp_path: Path) -> None:
    caminho = tmp_path / "t.csv"
    arq.acrescentar(caminho, BR, [esperadas()[0]])
    antes = caminho.read_bytes()
    excesso = nova(D(2026, 5, 1), "PETR4", "venda", 1001, preco=40)
    with pytest.raises(ErroCarteira, match=r"nova, linha 7: venda de 1001 PETR4"):
        arq.acrescentar(caminho, BR, [excesso], [7])
    assert caminho.read_bytes() == antes


def test_reimportacao_e_recusada_salvo_pedido(tmp_path: Path) -> None:
    caminho = tmp_path / "t.csv"
    compra = esperadas()[0]
    arq.acrescentar(caminho, BR, [compra])
    with pytest.raises(ErroCarteira, match="idêntica"):
        arq.acrescentar(caminho, BR, [compra])
    arq.acrescentar(caminho, BR, [compra], permitir_duplicadas=True)
    assert len(arq.carregar(caminho, BR)[0]) == 2


def test_carregar_ausente_e_carteira_vazia_e_arquivo_adulterado_falha(tmp_path: Path) -> None:
    assert arq.carregar(tmp_path / "nada.csv", BR) == ([], [])
    ruim = escrever(
        tmp_path / "t.csv",
        "data;ticker;tipo;quantidade;preco\n2026-01-05;PETR4;venda;10;30\n",
    )
    with pytest.raises(ErroCarteira, match="linha 2: venda de 10"):
        arq.carregar(ruim, BR)


# --- comandos ----------------------------------------------------------------------------------


@pytest.fixture
def caminho_carteira(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    caminho = tmp_path / "carteira" / "transacoes.csv"
    monkeypatch.setattr(cli, "CAMINHO_TRANSACOES", caminho)
    return caminho


def test_cli_lancar_grava_e_valida(caminho_carteira: Path) -> None:
    cmd = CliRunner()
    r = cmd.invoke(
        app, ["carteira", "lancar", "compra", "PETR4", "100", "--preco", "35,5".replace(",", ".")]
    )
    assert r.exit_code == 0, r.output
    assert "Gravado: compra PETR4" in r.output
    assert arq.carregar(caminho_carteira, BR)[0][0].valor == 3550.0

    r = cmd.invoke(app, ["carteira", "lancar", "venda", "PETR4", "101", "--preco", "40"])
    assert r.exit_code == 1
    assert "acima da posição" in r.output

    r = cmd.invoke(
        app, ["carteira", "lancar", "compra", "PETR4", "1", "--preco", "40", "--data", "x"]
    )
    assert r.exit_code == 1
    assert "data inválida" in r.output

    futuro = (dt.date.today() + dt.timedelta(days=3)).isoformat()
    r = cmd.invoke(
        app, ["carteira", "lancar", "compra", "PETR4", "1", "--preco", "4", "--data", futuro]
    )
    assert r.exit_code == 1
    assert "no futuro" in r.output
    assert len(arq.carregar(caminho_carteira, BR)[0]) == 1


def test_cli_importar_csv_xlsx_e_recusa_do_arquivo_inteiro(
    caminho_carteira: Path, tmp_path: Path
) -> None:
    cmd = CliRunner()
    bom = escrever(tmp_path / "in.csv", CSV_BR)
    r = cmd.invoke(app, ["carteira", "importar", str(bom)])
    assert r.exit_code == 0, r.output
    assert "Importadas 3 transações" in r.output
    assert arq.carregar(caminho_carteira, BR)[0] == esperadas()

    r = cmd.invoke(app, ["carteira", "importar", str(bom)])
    assert r.exit_code == 1
    assert "idêntica" in r.output

    ruim = escrever(
        tmp_path / "ruim.csv",
        "data;ticker;tipo;quantidade;preco\n2026-04-01;VALE3;compra;10;60\n2026-04-02;X;compra;1;1\n",
    )
    r = cmd.invoke(app, ["carteira", "importar", str(ruim)])
    assert r.exit_code == 1
    assert "linha 3: ticker inválido" in r.output
    assert len(arq.carregar(caminho_carteira, BR)[0]) == 3  # nada da VALE3 entrou

    r = cmd.invoke(app, ["carteira", "importar", str(bom), "--formato-csv", "xx"])
    assert r.exit_code == 1
