"""Controles de qualidade das demonstrações padronizadas (seção 7.5 do guia).

`verificar` devolve um `ResultadoQA` com uma `Verificacao` por regra que falhou (severidade
`erro`, `aviso` ou `info`), a cobertura das contas críticas e as contas relevantes que o plano
não mapeia. Erro significa que o valuation não deve rodar sem corrigir o mapeamento ou os dados.

Financeiras (plano `financeira`, ADR 0011) têm verificações próprias: não há EBIT, D&A nem
passivo circulante, e as contas não mapeadas do balanço de um banco (depósitos, captações) seriam
sempre "relevantes" sem servir ao DDM, por isso não são listadas.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from valuation.contabil import periodos
from valuation.contabil.padronizacao import PlanoContas, avaliar_regra, cobertura

Severidade = Literal["erro", "aviso", "info"]

TOL_BALANCO = 0.001  # ativo x passivo + PL, relativa ao ativo
TOL_SUBCONTAS = 0.005  # soma das filhas x conta-pai, relativa à conta-pai
TOL_DRE = 0.005  # identidades da DRE, relativa à receita
TOL_ATRIBUICAO = 0.005  # LL = controladora + não controladores, relativa ao LL
TOL_FONTES = 0.05  # duas regras da mesma conta no mesmo período
SALTO_ANUAL = 0.5  # variação a/a em contas-chave
LIMIAR_INTENSIVO = 0.2  # imobilizado / ativo acima disso => D&A é esperada
LIMIAR_RELEVANTE = 0.05  # conta não mapeada relevante: |valor| / base
CONTAS_DRE_NAO_RECORRENTES = ("3.04.03", "3.04.04", "3.04.05")
CONTAS_SALTO = ("receita_liquida", "ativo_total", "patrimonio_liquido_total", "imobilizado")
PAIS_SUBCONTAS = ("1", "1.01", "1.02", "2", "2.01", "2.02")
PAIS_SUBCONTAS_FINANCEIRA = ("1", "2")
CONTAS_SALTO_FINANCEIRA = ("ativo_total", "patrimonio_liquido_total", "lucro_liquido")

# Contas que as verificações leem (ausentes viram NaN e não geram falha; a ausência de conta
# crítica é apontada por `conta_critica_ausente`).
_SALDOS_USADOS = [
    "ativo_total",
    "passivo_total",
    "passivo_circulante",
    "passivo_nao_circulante",
    "patrimonio_liquido_total",
]
_FLUXOS_USADOS = [
    "receita_liquida",
    "custo_vendas",
    "despesas_operacionais",
    "ebit",
    "resultado_financeiro",
    "lair",
    "lucro_liquido",
    "lucro_liquido_controladora",
    "lucro_liquido_minoritarios",
]
_ANUAIS_USADOS = ["receita_liquida", "imobilizado", "ativo_total", "da"]


@dataclass(frozen=True)
class Verificacao:
    codigo: str
    severidade: Severidade
    mensagem: str
    periodos: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResultadoQA:
    ticker: str
    cd_cvm: int
    moeda: str
    verificacoes: tuple[Verificacao, ...]
    cobertura: dict[str, float] = field(default_factory=dict)
    nao_mapeadas: tuple[dict[str, Any], ...] = ()

    @property
    def erros(self) -> list[Verificacao]:
        return [v for v in self.verificacoes if v.severidade == "erro"]

    @property
    def avisos(self) -> list[Verificacao]:
        return [v for v in self.verificacoes if v.severidade == "aviso"]

    def para_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "cd_cvm": self.cd_cvm,
            "moeda": self.moeda,
            "n_erros": len(self.erros),
            "n_avisos": len(self.avisos),
            "verificacoes": [asdict(v) for v in self.verificacoes],
            "cobertura": self.cobertura,
            "nao_mapeadas": list(self.nao_mapeadas),
        }


def _rotulo(data: Any) -> str:
    return data.date().isoformat() if isinstance(data, pd.Timestamp) else str(data)


def _falhas(mascara: pd.Series) -> tuple[str, ...]:
    return tuple(_rotulo(i) for i in mascara[mascara.fillna(False)].index)


def _diferenca_relativa(a: pd.Series, b: pd.Series, base: pd.Series) -> pd.Series:
    return (a - b).abs() / base.abs().replace(0, np.nan)


def _rotulos_periodo(df: pd.DataFrame) -> pd.Index:
    """`AAAA-MM-DD` para saldos, `AAAA-MM-DD/AAAA-MM-DD` (início/fim) para fluxos."""
    fim = df["dt_fim"].dt.strftime("%Y-%m-%d")
    inicio = df["dt_ini"].dt.strftime("%Y-%m-%d")
    rotulos: pd.Series = inicio.where(df["dt_ini"].isna(), inicio + "/").fillna("") + fim
    indice: pd.Index = pd.Index(rotulos)
    return indice


def _todos_os_fluxos(contas: pd.DataFrame) -> pd.DataFrame:
    """Fluxos de todos os períodos (ano, YTD e trimestre), índice = `início/fim`."""
    fluxos = contas[contas["periodicidade"] != "S"]
    fluxos = fluxos.assign(periodo=_rotulos_periodo(fluxos).to_numpy())
    largo = fluxos.pivot_table(
        index="periodo", columns="conta_padrao", values="valor", aggfunc="first"
    )
    largo.columns.name = None
    return largo


def _balanco_fecha(bal: pd.DataFrame) -> Iterable[Verificacao]:
    passivo_pl = (
        bal["passivo_circulante"] + bal["passivo_nao_circulante"] + bal["patrimonio_liquido_total"]
    )
    for nome, outro in (("passivo + PL", passivo_pl), ("passivo total", bal["passivo_total"])):
        falhas = _falhas(
            _diferenca_relativa(bal["ativo_total"], outro, bal["ativo_total"]) > TOL_BALANCO
        )
        if falhas:
            yield Verificacao(
                "balanco_fecha",
                "erro",
                f"Ativo total difere de {nome} (> {TOL_BALANCO:.1%}).",
                falhas,
            )


def _subcontas(
    selecionadas: pd.DataFrame, pais: tuple[str, ...] = PAIS_SUBCONTAS
) -> Iterable[Verificacao]:
    bp = selecionadas[selecionadas["familia"].isin(["BPA", "BPP"])]
    falhas: list[str] = []
    for pai in pais:
        nivel = pai.count(".") + 1
        filhas = bp[
            bp["cd_conta"].str.startswith(pai + ".") & (bp["cd_conta"].str.count(r"\.") == nivel)
        ]
        soma = filhas.groupby("dt_fim")["valor"].sum()
        valor_pai = bp[bp["cd_conta"] == pai].groupby("dt_fim")["valor"].first()
        dif = _diferenca_relativa(valor_pai, soma.reindex(valor_pai.index), valor_pai)
        falhas += [f"{pai} em {d}" for d in _falhas(dif > TOL_SUBCONTAS)]
    if falhas:
        yield Verificacao(
            "subcontas",
            "aviso",
            "Soma das subcontas difere da conta-pai no balanço.",
            tuple(falhas),
        )


def _dre(fluxos: pd.DataFrame, anual: pd.DataFrame) -> Iterable[Verificacao]:
    falhas = _falhas(anual["receita_liquida"] <= 0)
    if falhas:
        yield Verificacao("receita_positiva", "erro", "Receita líquida não positiva.", falhas)

    receita = fluxos["receita_liquida"]
    calculado = receita + fluxos["custo_vendas"] + fluxos["despesas_operacionais"]
    falhas = _falhas(_diferenca_relativa(fluxos["ebit"], calculado, receita) > TOL_DRE)
    if falhas:
        yield Verificacao(
            "ebit_consistente",
            "erro",
            "EBIT difere de receita + custos + despesas operacionais (sinal invertido?).",
            falhas,
        )
    calculado = fluxos["ebit"] + fluxos["resultado_financeiro"]
    falhas = _falhas(_diferenca_relativa(fluxos["lair"], calculado, receita) > TOL_DRE)
    if falhas:
        yield Verificacao(
            "lair_consistente", "aviso", "LAIR difere de EBIT + resultado financeiro.", falhas
        )

    yield from _lucro_atribuido(fluxos)


def _lucro_atribuido(fluxos: pd.DataFrame) -> Iterable[Verificacao]:
    soma = fluxos["lucro_liquido_controladora"] + fluxos["lucro_liquido_minoritarios"].fillna(0)
    falhas = _falhas(
        _diferenca_relativa(fluxos["lucro_liquido"], soma, fluxos["lucro_liquido"]) > TOL_ATRIBUICAO
    )
    if falhas:
        yield Verificacao(
            "lucro_atribuido",
            "aviso",
            "LL consolidado difere de controladora + não controladores.",
            falhas,
        )


def _da(anual: pd.DataFrame) -> Iterable[Verificacao]:
    intensivo = anual["imobilizado"] / anual["ativo_total"] > LIMIAR_INTENSIVO
    sem_da = anual["da"].isna() | (anual["da"] == 0)
    falhas = _falhas(intensivo & sem_da)
    if falhas:
        yield Verificacao(
            "da_ausente", "aviso", "D&A ausente ou zero em empresa intensiva em capital.", falhas
        )


def _fontes_divergentes(selecionadas: pd.DataFrame, plano: PlanoContas) -> Iterable[Verificacao]:
    """Contas com mais de uma regra: compara a regra usada com as alternativas no mesmo período."""
    for conta, regras in plano.contas.items():
        if len(regras) < 2:
            continue
        valores: list[pd.Series] = []
        for regra in regras:
            v = avaliar_regra(selecionadas, regra)
            if not v.empty:
                valores.append(pd.Series(v["valor"].to_numpy(), index=_rotulos_periodo(v)))
        if len(valores) < 2:
            continue
        principal = valores[0]
        falhas: list[str] = []
        for alternativa in valores[1:]:
            comuns = principal.index.intersection(alternativa.index)
            dif = _diferenca_relativa(principal[comuns], alternativa[comuns], principal[comuns])
            falhas += _falhas(dif > TOL_FONTES)
        if falhas:
            yield Verificacao(
                "fontes_divergentes",
                "aviso",
                f"{conta}: regras alternativas do mapeamento divergem > {TOL_FONTES:.0%} "
                "(vale a primeira regra).",
                tuple(sorted(set(falhas))),
            )


def _saltos(anual: pd.DataFrame, contas: tuple[str, ...] = CONTAS_SALTO) -> Iterable[Verificacao]:
    for conta in contas:
        if conta not in anual:
            continue
        serie = anual[conta]
        variacao = (serie / serie.shift(1) - 1).abs()
        falhas = _falhas(variacao > SALTO_ANUAL)
        if falhas:
            yield Verificacao(
                "salto_anual", "aviso", f"{conta} variou mais de {SALTO_ANUAL:.0%} no ano.", falhas
            )


def _anos_faltantes(anual: pd.DataFrame, historico_anos: int) -> Iterable[Verificacao]:
    anos = sorted(int(a) for a in anual.index)
    if not anos:
        yield Verificacao("anos_faltantes", "erro", "Nenhum exercício (DFP) disponível.")
        return
    esperados = set(range(anos[-1] - historico_anos + 1, anos[-1] + 1))
    faltando = sorted(esperados - set(anos))
    if faltando:
        yield Verificacao(
            "anos_faltantes",
            "aviso",
            f"Exercícios ausentes nos últimos {historico_anos} anos.",
            tuple(str(a) for a in faltando),
        )


def _criticas(anual: pd.DataFrame, plano: PlanoContas) -> Iterable[Verificacao]:
    for conta in plano.criticas:
        serie = anual[conta] if conta in anual else pd.Series(np.nan, index=anual.index)
        falhas = _falhas(serie.isna())
        if falhas:
            yield Verificacao(
                "conta_critica_ausente", "aviso", f"{conta} sem valor mapeado.", falhas
            )


def _escala(selecionadas: pd.DataFrame) -> Iterable[Verificacao]:
    escalas = sorted(selecionadas["escala_moeda"].dropna().unique())
    if len(escalas) > 1:
        yield Verificacao(
            "escala_varia",
            "info",
            f"Escalas diferentes entre documentos ({', '.join(escalas)}); "
            "já normalizadas na ingestão.",
        )


def contas_nao_mapeadas(
    selecionadas: pd.DataFrame, contas: pd.DataFrame, limiar: float = LIMIAR_RELEVANTE
) -> list[dict[str, Any]]:
    """Contas de 3º nível (x.yy.zz) do último exercício com valor relevante e fora do mapeamento.

    Balanço: |valor| >= `limiar` * ativo total (sem as do PL). DRE: impairment e outras
    receitas/despesas operacionais (3.04.03 a 3.04.05, candidatas a não recorrentes) com
    |valor| >= `limiar` * receita.
    """
    anuais = contas[(contas["dt_fim"].dt.month == 12) & (contas["dt_fim"].dt.day == 31)]
    if anuais.empty:
        return []
    fim = anuais["dt_fim"].max()
    usados = {c for cs in contas.loc[contas["dt_fim"] == fim, "cd_contas"] for c in cs.split(";")}
    usados_detalhe = {c for c in usados if c.count(".") >= 2}

    def coberta(codigo: str) -> bool:
        return any(
            codigo == u or codigo.startswith(u + ".") or u.startswith(codigo + ".")
            for u in usados_detalhe
        )

    def base(conta: str) -> float:
        linha = anuais[(anuais["dt_fim"] == fim) & (anuais["conta_padrao"] == conta)]
        return abs(float(linha["valor"].iloc[0])) if not linha.empty else np.nan

    candidatas = selecionadas[
        (selecionadas["dt_fim"] == fim)
        & (selecionadas["cd_conta"].str.count(r"\.") == 2)
        & (
            (
                selecionadas["familia"].isin(["BPA", "BPP"])
                & ~selecionadas["cd_conta"].str.startswith("2.03")
            )
            | (
                (selecionadas["familia"] == "DRE")
                & selecionadas["cd_conta"].isin(CONTAS_DRE_NAO_RECORRENTES)
            )
        )
    ]
    if "dt_ini" in candidatas:
        candidatas = candidatas[candidatas["dt_ini"].isna() | (candidatas["dt_ini"].dt.month == 1)]
    bases = {"BPA": base("ativo_total"), "BPP": base("ativo_total"), "DRE": base("receita_liquida")}
    saida = []
    for linha in candidatas.itertuples():
        b = bases[str(linha.familia)]
        if coberta(str(linha.cd_conta)) or not b or np.isnan(b):
            continue
        fracao = abs(float(linha.valor)) / b
        if fracao >= limiar:
            saida.append(
                {
                    "data": fim.date().isoformat(),
                    "demonstracao": str(linha.familia),
                    "cd_conta": str(linha.cd_conta),
                    "ds_conta": str(linha.ds_conta),
                    "valor": float(linha.valor),
                    "fracao_da_base": round(fracao, 4),
                }
            )
    return saida


def verificar(
    selecionadas: pd.DataFrame,
    contas: pd.DataFrame,
    plano: PlanoContas,
    *,
    ticker: str,
    moeda: str,
    historico_anos: int,
) -> ResultadoQA:
    """Roda todas as verificações sobre as demonstrações selecionadas e as contas padronizadas."""
    anual = periodos.anual(contas)
    if plano.tipo == "financeira":
        verificacoes = list(_verificacoes_financeira(selecionadas, contas, anual))
        nao_mapeadas: list[dict[str, Any]] = []
    else:
        bal = periodos.saldos(contas).reindex(columns=_SALDOS_USADOS)
        anual = anual.reindex(columns=anual.columns.union(_ANUAIS_USADOS))
        fluxos = _todos_os_fluxos(contas).reindex(columns=_FLUXOS_USADOS)
        verificacoes = [
            *_balanco_fecha(bal),
            *_subcontas(selecionadas),
            *_dre(fluxos, anual),
            *_da(anual),
            *_saltos(anual),
        ]
        nao_mapeadas = contas_nao_mapeadas(selecionadas, contas)
    verificacoes += [
        *_fontes_divergentes(selecionadas, plano),
        *_anos_faltantes(anual, historico_anos),
        *_criticas(anual, plano),
        *_escala(selecionadas),
    ]
    ordem = {"erro": 0, "aviso": 1, "info": 2}
    verificacoes.sort(key=lambda v: ordem[v.severidade])
    return ResultadoQA(
        ticker=ticker,
        cd_cvm=int(contas["cd_cvm"].iloc[0]),
        moeda=moeda,
        verificacoes=tuple(verificacoes),
        cobertura={
            str(k): round(float(v), 4) for k, v in cobertura(contas, plano.criticas).items()
        },
        nao_mapeadas=tuple(nao_mapeadas),
    )


def _verificacoes_financeira(
    selecionadas: pd.DataFrame, contas: pd.DataFrame, anual: pd.DataFrame
) -> Iterable[Verificacao]:
    """Balanço (ativo = passivo total), PL positivo, atribuição do lucro e saltos."""
    bal = periodos.saldos(contas).reindex(
        columns=["ativo_total", "passivo_total", "patrimonio_liquido_total"]
    )
    falhas = _falhas(
        _diferenca_relativa(bal["ativo_total"], bal["passivo_total"], bal["ativo_total"])
        > TOL_BALANCO
    )
    if falhas:
        yield Verificacao(
            "balanco_fecha",
            "erro",
            f"Ativo total difere do passivo total (> {TOL_BALANCO:.1%}).",
            falhas,
        )
    falhas = _falhas(bal["patrimonio_liquido_total"] <= 0)
    if falhas:
        yield Verificacao("pl_positivo", "erro", "Patrimônio líquido não positivo.", falhas)
    yield from _subcontas(selecionadas, PAIS_SUBCONTAS_FINANCEIRA)
    fluxos = _todos_os_fluxos(contas).reindex(
        columns=["lucro_liquido", "lucro_liquido_controladora", "lucro_liquido_minoritarios"]
    )
    yield from _lucro_atribuido(fluxos)
    yield from _saltos(anual, CONTAS_SALTO_FINANCEIRA)


def gravar(resultado: ResultadoQA, caminho: Path) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(resultado.para_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return caminho
