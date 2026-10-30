from pathlib import Path

import pandas as pd
import pytest

from sintetico import documento, juntar
from valuation.config import ErroConfiguracao
from valuation.contabil import ErroContabil
from valuation.contabil import padronizacao as pad
from valuation.contabil.padronizacao import PlanoContas, RegraMapeamento


def _plano(**contas: list[dict[str, object]]) -> PlanoContas:
    return PlanoContas(
        tipo="nao_financeira",
        contas={k: tuple(RegraMapeamento.model_validate(r) for r in v) for k, v in contas.items()},
        criticas=(),
    )


def _valores(contas: pd.DataFrame, conta: str) -> dict[str, float]:
    linhas = contas[contas["conta_padrao"] == conta]
    return {f.date().isoformat(): v for f, v in zip(linhas["dt_fim"], linhas["valor"], strict=True)}


def test_yaml_real_carrega_e_criticas_existem() -> None:
    plano = pad.carregar_mapeamento()
    assert "receita_liquida" in plano.contas
    assert set(plano.criticas) <= set(plano.contas)
    assert plano.eh_saldo("caixa") and not plano.eh_saldo("da")


@pytest.mark.parametrize(
    "conteudo, trecho",
    [
        ("nao_financeira:\n  x: [{dem: DRE}]\n", "cd` ou `ds_regex"),
        ("nao_financeira:\n  x: [{dem: XYZ, cd: '1'}]\n", "regra inválida"),
        ("nao_financeira:\n  x: [{dem: DRE, ds_regex: '('}]\n", "regex inválida"),
        ("nao_financeira:\n  x: [{dem: DRE, cd: '3.01'}, {dem: BPA, cd: '1'}]\n", "mistura"),
        ("nao_financeira:\n  x: []\n", "lista não vazia"),
        ("outra: {}\n", "seção 'nao_financeira' ausente"),
        (
            "nao_financeira:\n  x: [{dem: DRE, cd: '3.01'}]\n"
            "contas_criticas: {nao_financeira: [y]}\n",
            "sem regra: y",
        ),
    ],
)
def test_yaml_invalido(tmp_path: Path, conteudo: str, trecho: str) -> None:
    caminho = tmp_path / "m.yaml"
    caminho.write_text(conteudo, encoding="utf-8")
    with pytest.raises(ErroConfiguracao, match=trecho):
        pad.carregar_mapeamento(caminho)


def test_mapeamento_extra_vem_antes(tmp_path: Path) -> None:
    caminho = tmp_path / "m.yaml"
    caminho.write_text("nao_financeira:\n  caixa: [{dem: BPA, cd: '1.01.01'}]\n", encoding="utf-8")
    plano = pad.carregar_mapeamento(
        caminho,
        extra={"caixa": [{"dem": "BPA", "cd": "1.01.09"}], "nova": [{"dem": "DRE", "cd": "3.99"}]},
    )
    assert [r.cd for r in plano.contas["caixa"]] == ["1.01.09", "1.01.01"]
    assert "nova" in plano.contas
    with pytest.raises(ErroConfiguracao, match="troca saldo"):
        pad.carregar_mapeamento(caminho, extra={"caixa": [{"dem": "DRE", "cd": "3.01"}]})


def test_periodicidade() -> None:
    p = pad.periodicidade
    assert p(pd.NaT, pd.Timestamp("2025-12-31")) == "S"
    assert p(pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-31")) == "A"
    assert p(pd.Timestamp("2025-04-01"), pd.Timestamp("2025-06-30")) == "T"
    assert p(pd.Timestamp("2025-01-01"), pd.Timestamp("2025-03-31")) == "T"
    assert p(pd.Timestamp("2025-01-01"), pd.Timestamp("2025-09-30")) == "YTD"


def test_reapresentacao_mais_recente_vence() -> None:
    """Custo com sinal invertido na DFP 2022, corrigido como PENÚLTIMO na DFP 2023 (caso Vale)."""
    dfp22 = documento(
        {"3.01": 100, "3.02": 60}, dem="DRE", dt_ini="2022-01-01", dt_fim="2022-12-31"
    )
    dfp23 = juntar(
        documento(
            {"3.01": 100, "3.02": -60},
            dem="DRE",
            dt_ini="2022-01-01",
            dt_fim="2022-12-31",
            dt_refer="2023-12-31",
            ordem="PENÚLTIMO",
        ),
        documento({"3.01": 120, "3.02": -70}, dem="DRE", dt_ini="2023-01-01", dt_fim="2023-12-31"),
    )
    sel = pad.selecionar_reapresentacoes(juntar(dfp22, dfp23))
    custo = sel[sel["cd_conta"] == "3.02"].set_index("dt_fim")["valor"]
    assert custo[pd.Timestamp("2022-12-31")] == -60
    assert set(sel["dt_refer"]) == {pd.Timestamp("2023-12-31")}


def test_reapresentacao_usa_maior_versao_e_documento_inteiro() -> None:
    """Todas as contas de um período vêm do mesmo documento, mesmo com códigos diferentes."""
    v1 = documento(
        {"6.01.01.05": ("Depreciação", 10)}, dem="DFC_MI", dt_ini="2025-01-01", dt_fim="2025-06-30"
    )
    v2 = documento(
        {"6.01.01.06": ("Depreciação", 11)},
        dem="DFC_MI",
        dt_ini="2025-01-01",
        dt_fim="2025-06-30",
        versao=2,
    )
    sel = pad.selecionar_reapresentacoes(juntar(v1, v2))
    assert list(sel["cd_conta"]) == ["6.01.01.06"]


def test_dfc_direta_descartada_quando_ha_indireta() -> None:
    mi = documento({"6.01": 50}, dem="DFC_MI", dt_ini="2025-01-01", dt_fim="2025-12-31")
    md = documento({"6.01": 50}, dem="DFC_MD", dt_ini="2025-01-01", dt_fim="2025-12-31")
    sel = pad.selecionar_reapresentacoes(juntar(mi, md))
    assert list(sel["demonstracao"]) == ["DFC_MI"]
    so_md = pad.selecionar_reapresentacoes(md)
    assert list(so_md["familia"]) == ["DFC"]


def test_filtra_consolidado_e_falha_sem_dados() -> None:
    ind = documento({"1": 10}, dem="BPA", dt_fim="2025-12-31", consolidado=False)
    with pytest.raises(ErroContabil, match="consolidadas"):
        pad.selecionar_reapresentacoes(ind)
    assert len(pad.selecionar_reapresentacoes(ind, consolidado=False)) == 1


def test_regra_por_codigo_regex_prefixo_e_exclusao() -> None:
    bpp = documento(
        {
            "2.01.04": 100,
            "2.01.04.03": ("Financiamento por Arrendamento", 0),
            "2.01.05.02.07": ("Arrendamentos", 30),
            "2.01.05.02.08": ("Arrendamento mercantil a pagar - partes relacionadas", 5),
        },
        dem="BPP",
        dt_fim="2025-12-31",
    )
    sel = pad.selecionar_reapresentacoes(bpp)
    plano = _plano(
        emprestimos_cp=[{"dem": "BPP", "cd": "2.01.04"}],
        arr_outros=[
            {
                "dem": "BPP",
                "cd_prefixo": "2.01",
                "cd_excluir": "2.01.04",
                "ds_regex": "arrendamento",
                "ds_excluir": "partes relacionadas",
            }
        ],
    )
    contas = pad.padronizar(sel, plano, ticker="SINT3")
    assert _valores(contas, "emprestimos_cp") == {"2025-12-31": 100}
    assert _valores(contas, "arr_outros") == {"2025-12-31": 30}
    linha = contas[contas["conta_padrao"] == "arr_outros"].iloc[0]
    assert linha["cd_contas"] == "2.01.05.02.07"
    assert linha["periodicidade"] == "S"
    assert linha["ticker"] == "SINT3"


def test_regex_ignora_acento_e_caixa() -> None:
    dre = documento(
        {"3.04.06": ("Resultado de EQUIVALÊNCIA Patrimonial", 7)},
        dem="DRE",
        dt_ini="2025-01-01",
        dt_fim="2025-12-31",
    )
    plano = _plano(eq=[{"dem": "DRE", "ds_regex": "equivalencia patrimonial"}])
    contas = pad.padronizar(pad.selecionar_reapresentacoes(dre), plano, ticker="X")
    assert _valores(contas, "eq") == {"2025-12-31": 7}


def test_soma_so_contas_de_nivel_mais_alto() -> None:
    bpa = documento(
        {
            "1.02.01.01": ("Aplicações Financeiras Avaliadas a Valor Justo", 10),
            "1.02.01.01.01": ("Aplicações financeiras - títulos", 10),
            "1.02.01.03": ("Aplicações Financeiras Avaliadas ao Custo Amortizado", 5),
        },
        dem="BPA",
        dt_fim="2025-12-31",
    )
    plano = _plano(
        aplic=[{"dem": "BPA", "cd_prefixo": "1.02.01", "ds_regex": "^aplicacoes financeiras"}]
    )
    contas = pad.padronizar(pad.selecionar_reapresentacoes(bpa), plano, ticker="X")
    assert _valores(contas, "aplic") == {"2025-12-31": 15}
    assert contas["cd_contas"].iloc[0] == "1.02.01.01;1.02.01.03"


def test_primeira_regra_que_casa_vence_por_periodo_e_sinal() -> None:
    """D&A: DFC quando existe; DVA (negativa, `sinal: -1`) no ano em que a DFC não tem a linha."""
    dados = juntar(
        documento({"6.01.01.04": 40}, dem="DFC_MI", dt_ini="2025-01-01", dt_fim="2025-12-31"),
        documento({"7.04.01": -41}, dem="DVA", dt_ini="2025-01-01", dt_fim="2025-12-31"),
        documento(
            {"7.04.01": -30},
            dem="DVA",
            dt_ini="2024-01-01",
            dt_fim="2024-12-31",
            dt_refer="2025-12-31",
            ordem="PENÚLTIMO",
        ),
    )
    plano = _plano(
        da=[
            {"dem": "DFC", "cd_prefixo": "6.01.01", "ds_regex": "deprecia"},
            {"dem": "DVA", "cd": "7.04.01", "sinal": -1},
        ]
    )
    contas = pad.padronizar(pad.selecionar_reapresentacoes(dados), plano, ticker="X")
    assert _valores(contas, "da") == {"2024-12-31": 30, "2025-12-31": 40}
    assert dict(zip(contas["dt_fim"].dt.year, contas["regra"], strict=True)) == {2024: 1, 2025: 0}


def test_codigo_que_muda_entre_trimestres_com_regex() -> None:
    """D&A da Vale: 6.01.01.06 no 1T26 e 6.01.01.05 no 2T26."""
    dados = juntar(
        documento(
            {"6.01.01.06": ("Depreciação, amortização e exaustão", 4)},
            dem="DFC_MI",
            dt_ini="2026-01-01",
            dt_fim="2026-03-31",
            fonte="ITR",
        ),
        documento(
            {
                "6.01.01.05": ("Depreciação, amortização e exaustão", 9),
                "6.01.01.06": ("Resultado na alienação de bens do imobilizado", 1),
            },
            dem="DFC_MI",
            dt_ini="2026-01-01",
            dt_fim="2026-06-30",
            fonte="ITR",
        ),
    )
    plano = pad.carregar_mapeamento()
    contas = pad.padronizar(pad.selecionar_reapresentacoes(dados), plano, ticker="VALE3")
    assert _valores(contas, "da") == {"2026-03-31": 4, "2026-06-30": 9}


def test_padronizar_sem_casamento_falha() -> None:
    bpa = documento({"1": 10}, dem="BPA", dt_fim="2025-12-31")
    plano = _plano(receita=[{"dem": "DRE", "cd": "3.01"}])
    with pytest.raises(ErroContabil, match="Nenhuma conta"):
        pad.padronizar(pad.selecionar_reapresentacoes(bpa), plano, ticker="X")


def test_cobertura() -> None:
    dados = juntar(
        documento({"3.01": 10}, dem="DRE", dt_ini="2024-01-01", dt_fim="2024-12-31"),
        documento({"3.01": 12, "3.11": 2}, dem="DRE", dt_ini="2025-01-01", dt_fim="2025-12-31"),
        # Trimestre não conta como exercício.
        documento({"3.11": 1}, dem="DRE", dt_ini="2026-01-01", dt_fim="2026-03-31", fonte="ITR"),
    )
    plano = _plano(receita=[{"dem": "DRE", "cd": "3.01"}], ll=[{"dem": "DRE", "cd": "3.11"}])
    contas = pad.padronizar(pad.selecionar_reapresentacoes(dados), plano, ticker="X")
    cob = pad.cobertura(contas, ["receita", "ll", "inexistente"])
    assert cob.to_dict() == {"receita": 1.0, "ll": 0.5, "inexistente": 0.0}


def test_ler_demonstracoes_sem_arquivo(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        pad.ler_demonstracoes(tmp_path, 9512)
    assert pad.caminho_padronizadas(tmp_path, 9512).name == "contas_padronizadas.parquet"
