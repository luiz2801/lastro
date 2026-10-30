"""Construtores de dados sintéticos no formato dos parquets (testes da camada contábil)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

import pandas as pd

from valuation.contabil.padronizacao import periodicidade
from valuation.data.cvm import COLUNAS_DEMONSTRACOES

DS_PADRAO = {
    "1": "Ativo Total",
    "1.01": "Ativo Circulante",
    "1.01.01": "Caixa e Equivalentes de Caixa",
    "1.01.02": "Aplicações Financeiras",
    "1.02": "Ativo Não Circulante",
    "1.02.03": "Imobilizado",
    "2": "Passivo Total",
    "2.01": "Passivo Circulante",
    "2.01.04": "Empréstimos e Financiamentos",
    "2.01.04.03": "Financiamento por Arrendamento",
    "2.02": "Passivo Não Circulante",
    "2.02.01": "Empréstimos e Financiamentos",
    "2.03": "Patrimônio Líquido Consolidado",
    "3.01": "Receita de Venda de Bens e/ou Serviços",
    "3.02": "Custo dos Bens e/ou Serviços Vendidos",
    "3.03": "Resultado Bruto",
    "3.04": "Despesas/Receitas Operacionais",
    "3.05": "Resultado Antes do Resultado Financeiro e dos Tributos",
    "3.06": "Resultado Financeiro",
    "3.07": "Resultado Antes dos Tributos sobre o Lucro",
    "3.08": "Imposto de Renda e Contribuição Social sobre o Lucro",
    "3.11": "Lucro/Prejuízo Consolidado do Período",
    "3.11.01": "Atribuído a Sócios da Empresa Controladora",
    "3.11.02": "Atribuído a Sócios Não Controladores",
    "6.01": "Caixa Líquido Atividades Operacionais",
    "6.01.01.04": "Depreciação, amortização e exaustão",
    "6.02.01": "Aquisições de imobilizado",
    "7.04.01": "Depreciação, Amortização e Exaustão",
}


def documento(
    contas: Mapping[str, float | tuple[str, float]],
    *,
    dem: str,
    dt_fim: str,
    dt_ini: str | None = None,
    dt_refer: str | None = None,
    fonte: str = "DFP",
    versao: int = 1,
    ordem: str = "ÚLTIMO",
    consolidado: bool = True,
    moeda: str = "REAL",
    escala: str = "MIL",
    cd_cvm: int = 1234,
) -> pd.DataFrame:
    """Linhas de uma demonstração num período. Conta = valor ou (descrição, valor)."""
    linhas = []
    for cd, item in contas.items():
        ds, valor = item if isinstance(item, tuple) else (DS_PADRAO.get(cd, f"Conta {cd}"), item)
        linhas.append(
            {
                "cnpj": "00.000.000/0001-00",
                "cd_cvm": cd_cvm,
                "denom_cia": "SINTETICA S.A.",
                "fonte": fonte,
                "dt_refer": pd.Timestamp(dt_refer or dt_fim),
                "versao": versao,
                "demonstracao": dem,
                "consolidado": consolidado,
                "moeda": moeda,
                "escala_moeda": escala,
                "ordem_exerc": ordem,
                "dt_ini": pd.Timestamp(dt_ini) if dt_ini else pd.NaT,
                "dt_fim": pd.Timestamp(dt_fim),
                "coluna_df": "",
                "cd_conta": cd,
                "ds_conta": ds,
                "valor": float(valor),
                "st_conta_fixa": "S",
                "arquivo": f"{fonte.lower()}_sintetico.csv",
            }
        )
    return pd.DataFrame(linhas, columns=COLUNAS_DEMONSTRACOES)


BPA = {
    "1": 200,
    "1.01": 80,
    "1.01.01": 20,
    "1.01.02": 10,
    "1.01.03": ("Contas a Receber", 50),
    "1.02": 120,
    "1.02.03": 100,
    "1.02.04": ("Intangível", 20),
}
BPP = {
    "2": 200,
    "2.01": 50,
    "2.01.04": 50,
    "2.02": 50,
    "2.02.01": 50,
    "2.03": 100,
    "2.03.09": ("Participação dos Acionistas Não Controladores", 5),
}
DRE = {
    "3.01": 100,
    "3.02": -60,
    "3.03": 40,
    "3.04": -20,
    "3.05": 20,
    "3.06": -5,
    "3.07": 15,
    "3.08": -5,
    "3.11": 10,
    "3.11.01": 9,
    "3.11.02": 1,
}
DFC = {"6.01": 25, "6.01.01.04": 8, "6.02.01": -12}
DVA = {"7.04.01": -8}


def dfp_completa(ano: int, escala: str = "MIL", **trocas: dict[str, object]) -> pd.DataFrame:
    """DFP consistente de `ano` (só ÚLTIMO), com todas as contas críticas.

    `trocas` = {"DRE": {"3.01": 200}, ...}; `None` remove a conta.
    """
    partes = []
    for dem, base in (("BPA", BPA), ("BPP", BPP), ("DRE", DRE), ("DFC_MI", DFC), ("DVA", DVA)):
        contas = {**base, **trocas.get(dem.split("_")[0], {})}
        contas = {k: v for k, v in contas.items() if v is not None}
        if not contas:
            continue
        fluxo = dem not in ("BPA", "BPP")
        partes.append(
            documento(
                contas,
                dem=dem,
                dt_ini=f"{ano}-01-01" if fluxo else None,
                dt_fim=f"{ano}-12-31",
                escala=escala,
            )
        )
    return juntar(*partes)


def juntar(*partes: pd.DataFrame) -> pd.DataFrame:
    return pd.concat(partes, ignore_index=True)


def contas_padronizadas(
    registros: Iterable[tuple[str, str | None, str, float]], cd_cvm: int = 1234
) -> pd.DataFrame:
    """Tabela `contas_padronizadas` mínima: (conta, dt_ini ou None, dt_fim, valor)."""
    linhas = []
    for conta, ini, fim, valor in registros:
        dt_ini = pd.Timestamp(ini) if ini else pd.NaT
        dt_fim = pd.Timestamp(fim)
        linhas.append(
            {
                "cd_cvm": cd_cvm,
                "ticker": "SINT3",
                "dt_refer": dt_fim,
                "dt_ini": dt_ini,
                "dt_fim": dt_fim,
                "periodicidade": periodicidade(dt_ini, dt_fim),
                "demonstracao": "BPA" if ini is None else "DRE",
                "conta_padrao": conta,
                "valor": float(valor),
                "moeda": "REAL",
                "escala_aplicada": "MIL",
                "versao": 1,
                "fonte_arquivo": "sintetico",
                "regra": 0,
                "cd_contas": "",
            }
        )
    return pd.DataFrame(linhas)


def ano(conta: str, a: int, valor: float) -> tuple[str, str, str, float]:
    return (conta, f"{a}-01-01", f"{a}-12-31", valor)


def ytd(conta: str, fim: str, valor: float) -> tuple[str, str, str, float]:
    return (conta, f"{fim[:4]}-01-01", fim, valor)


def saldo(conta: str, data: str, valor: float) -> tuple[str, None, str, float]:
    return (conta, None, data, valor)


def historico_anual(
    crescimento: Iterable[float],
    margem: Iterable[float],
    *,
    inicio: int = 2016,
    receita_inicial: float = 100.0,
    da: float = 0.05,
    capex: Iterable[float] | float = 0.06,
    nwc: float = 0.10,
    arrendamento: float = 0.01,
    aliquota: Iterable[float] | float = 0.30,
) -> pd.DataFrame:
    """Métricas anuais mínimas para o sugestor/projetor: razões sobre a receita viram valores.

    `crescimento` tem um valor a menos que `margem` (o primeiro ano não tem crescimento).
    """
    margens = list(margem)
    receitas = [receita_inicial]
    for g in crescimento:
        receitas.append(receitas[-1] * (1 + g))
    if len(receitas) != len(margens):
        raise ValueError("crescimento deve ter um valor a menos que margem")
    n = len(margens)

    def lista(valor: Iterable[float] | float) -> list[float]:
        return [float(valor)] * n if isinstance(valor, int | float) else list(valor)

    receita = pd.Series(receitas, index=pd.RangeIndex(inicio, inicio + n, name="ano"))
    return pd.DataFrame(
        {
            "receita_liquida": receita,
            "ebitda_ajustado": receita * margens,
            "da": receita * da,
            "capex": receita * lista(capex),
            "nwc": receita * nwc,
            "pagamento_arrendamento": receita * arrendamento,
            "aliquota_efetiva": lista(aliquota),
        }
    )


# Banco no plano de contas de bancos antigo (lucro em 3.09, PL em 2.08), em milhares.
BANCO = {
    "BPA": {
        "1": ("Ativo Total", 1000),
        "1.01": ("Caixa e Equivalentes de Caixa", 50),
        "1.02": ("Ativos Financeiros", 950),
    },
    "BPP": {
        "2": ("Passivo Total", 1000),
        "2.03": ("Passivos Financeiros ao Custo Amortizado", 880),
        "2.08": ("Patrimônio Líquido Consolidado", 120),
        "2.08.09": ("Participação dos Acionistas Não Controladores", 20),
    },
    "DRE": {
        "3.01": ("Receitas da Intermediação Financeira", 200),
        "3.02": ("Despesas da Intermediação Financeira", -150),
        "3.03": ("Resultado Bruto Intermediação Financeira", 50),
        "3.05": ("Resultado Antes dos Tributos sobre o Lucro", 30),
        "3.06": ("Imposto de Renda e Contribuição Social sobre o Lucro", -6),
        "3.09": ("Lucro/Prejuízo Consolidado do Período", 24),
        "3.09.01": ("Atribuído a Sócios da Empresa Controladora", 22),
        "3.09.02": ("Atribuído a Sócios Não Controladores", 2),
    },
    "DFC": {
        "6.03.05": ("Dividendos e Juros sobre o Capital Próprio Pagos", -11),
        "6.03.06": ("Dividendos e JCP Pagos a Acionistas não Controladores", -1),
    },
}


def dfp_banco(
    ano: int, cd_cvm: int = 1234, **trocas: dict[str, float | tuple[str, float] | None]
) -> pd.DataFrame:
    """DFP de banco consistente (só ÚLTIMO); `trocas` como em `dfp_completa`."""
    partes = []
    for dem, base in BANCO.items():
        contas = {**base, **trocas.get(dem, {})}
        contas = {k: v for k, v in contas.items() if v is not None}
        fluxo = dem not in ("BPA", "BPP")
        partes.append(
            documento(
                contas,
                dem="DFC_MI" if dem == "DFC" else dem,
                dt_ini=f"{ano}-01-01" if fluxo else None,
                dt_fim=f"{ano}-12-31",
                cd_cvm=cd_cvm,
            )
        )
    return juntar(*partes)


def criar_empresa_sintetica(
    anos: Iterable[int] = (2023, 2024, 2025),
    escala: str = "MIL",
    cd_cvm: int = 1234,
    banco: bool = False,
    **trocas: dict[str, object],
) -> pd.DataFrame:
    """Gera demonstrações sintéticas completas multi-anuais (formato CVM) para testes.

    Permite testar pipelines de contabilidade, QA, padronização e modelos de valuation
    sem realizar downloads da CVM nem tocar a rede ou ler arquivos externos.
    """
    partes = []
    for a in anos:
        if banco:
            partes.append(dfp_banco(a, cd_cvm=cd_cvm, **trocas))  # type: ignore[arg-type]
        else:
            partes.append(dfp_completa(a, escala=escala, **trocas))
    return juntar(*partes)
