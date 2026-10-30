"""Múltiplos e comparáveis (seção 11.4 do CLAUDE.md e ADR 0009).

Alvo e pares passam pelo mesmo pipeline contábil: métricas LTM na data do último balanço até a
data-base (`nao_financeiras.metricas_ltm`) e market cap na data-base, tudo em BRL.

- EV = market cap + dívida bruta - caixa e aplicações + não controladores - investimentos em
  coligadas + `divida_extra`: o inverso exato da ponte EV -> equity do DCF, de modo que o valor
  implícito por um múltiplo de EV volta pela mesma ponte.
- EBITDA e EBIT são os ajustados (sem equivalência patrimonial quando as coligadas entram pelo
  investimento contábil, e sem não recorrentes), coerentes com esse EV.
- P/L e P/VP usam o lucro e o PL da controladora; EV/FCF usa o FCFF; dividend yield = dividendos
  pagos no LTM / market cap.

Múltiplo com numerador ou denominador não positivo é descartado (indefinido). Os válidos são
limitados aos percentis de winsorização dos pares antes das estatísticas. O valor implícito usa
P25, mediana e P75 dos pares; no dividend yield a relação é inversa (yield maior, valor menor).

Financeiras (ADR 0014): só P/L, P/VP e dividend yield (`MULTIPLOS_FINANCEIRA`), sem EV; os
fundamentos vêm de `contabil.financeiras.metricas_ltm` e trazem o ROE. A regressão P/VP x ROE
dos pares (`regressao_pvp_roe`) dá o P/VP esperado para o ROE do alvo.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Literal, cast

import numpy as np
import pandas as pd

from valuation.modelos import ErroModelo
from valuation.modelos import ponte as pt

NomeMultiplo = Literal[
    "p_l", "ev_ebitda", "ev_ebit", "ev_receita", "p_vp", "ev_fcf", "dividend_yield"
]
NomeMetrica = Literal[
    "lucro_liquido",
    "ebitda",
    "ebit",
    "receita_liquida",
    "patrimonio_liquido",
    "fcff",
    "dividendos",
]
Base = Literal["equity", "ev", "yield"]

# múltiplo -> (base do numerador, métrica do denominador); "yield" = métrica / market cap.
DEFINICOES: dict[NomeMultiplo, tuple[Base, NomeMetrica]] = {
    "p_l": ("equity", "lucro_liquido"),
    "ev_ebitda": ("ev", "ebitda"),
    "ev_ebit": ("ev", "ebit"),
    "ev_receita": ("ev", "receita_liquida"),
    "p_vp": ("equity", "patrimonio_liquido"),
    "ev_fcf": ("ev", "fcff"),
    "dividend_yield": ("yield", "dividendos"),
}
MULTIPLOS: tuple[NomeMultiplo, ...] = tuple(DEFINICOES)
MULTIPLOS_FINANCEIRA: tuple[NomeMultiplo, ...] = ("p_l", "p_vp", "dividend_yield")
ROTULOS: dict[NomeMultiplo, str] = {
    "p_l": "P/L",
    "ev_ebitda": "EV/EBITDA",
    "ev_ebit": "EV/EBIT",
    "ev_receita": "EV/Receita",
    "p_vp": "P/VP",
    "ev_fcf": "EV/FCF",
    "dividend_yield": "Dividend yield",
}
ESTATISTICAS = ("p25", "mediana", "p75")
# P/VP abaixo disto quase sempre é quantidade de ações em milhares tratada como unidades
# (ADR 0003): o par sai das estatísticas, com aviso.
PVP_MINIMO_PLAUSIVEL = 0.05


@dataclass(frozen=True)
class Fundamentos:
    """Market cap, itens da ponte e métricas LTM de uma companhia, em BRL (unidades)."""

    ticker: str
    market_cap: float
    itens: pt.ItensPonte
    lucro_liquido: float  # controladora
    ebitda: float  # ajustado
    ebit: float  # ajustado
    receita_liquida: float
    patrimonio_liquido: float  # controladora
    fcff: float
    dividendos: float
    roe: float = float("nan")  # financeiras: LTM sobre o PL da controladora de 12 meses antes

    @property
    def ev(self) -> float:
        i = self.itens
        return (
            self.market_cap
            + i.divida_bruta
            - i.caixa_e_aplicacoes
            + i.minoritarios
            - i.investimentos
            + i.divida_extra
        )

    @property
    def data_balanco(self) -> dt.date:
        return self.itens.data_balanco

    def metrica(self, nome: NomeMetrica) -> float:
        return float(getattr(self, nome))


def fundamentos(
    ticker: str,
    ltm: pd.Series,
    *,
    itens: pt.ItensPonte,
    market_cap: float,
    cambio: float = 1.0,
) -> Fundamentos:
    """`ltm` = `metricas_ltm` na data de `itens`, na moeda de reporte; `cambio` leva a BRL."""

    def valor(nome: str) -> float:
        x = float(ltm.get(nome, np.nan))
        return 0.0 if nome == "minoritarios" and pd.isna(x) else x * cambio

    em_brl = replace(
        itens,
        divida_bruta=itens.divida_bruta * cambio,
        caixa_e_aplicacoes=itens.caixa_e_aplicacoes * cambio,
        minoritarios=itens.minoritarios * cambio,
        investimentos=itens.investimentos * cambio,
        divida_extra=itens.divida_extra * cambio,
    )
    return Fundamentos(
        ticker=ticker,
        market_cap=market_cap,
        itens=em_brl,
        lucro_liquido=valor("lucro_liquido_controladora"),
        ebitda=valor("ebitda_ajustado"),
        ebit=valor("ebit_ajustado"),
        receita_liquida=valor("receita_liquida"),
        patrimonio_liquido=valor("patrimonio_liquido_total") - valor("minoritarios"),
        fcff=valor("fcff"),
        dividendos=valor("dividendos_pagos"),
    )


def fundamentos_financeira(
    ticker: str,
    ltm: pd.Series,
    *,
    acoes: int,
    data_balanco: dt.date,
    market_cap: float,
) -> Fundamentos:
    """Fundamentos de uma financeira (`financeiras.metricas_ltm`): sem dívida, caixa nem EV."""
    itens = pt.ItensPonte(0.0, 0.0, 0.0, 0.0, 0.0, acoes, data_balanco)
    nan = float("nan")

    def valor(nome: str) -> float:
        return float(ltm.get(nome, nan))

    return Fundamentos(
        ticker=ticker,
        market_cap=market_cap,
        itens=itens,
        lucro_liquido=valor("lucro_liquido_controladora"),
        ebitda=nan,
        ebit=nan,
        receita_liquida=nan,
        patrimonio_liquido=valor("patrimonio_liquido"),
        fcff=nan,
        dividendos=valor("dividendos_pagos"),
        roe=valor("roe"),
    )


def multiplo(f: Fundamentos, nome: NomeMultiplo) -> float:
    """Valor do múltiplo; NaN se numerador ou denominador não for positivo (ou for NaN)."""
    base, metrica = DEFINICOES[nome]
    m = f.metrica(metrica)
    numerador = f.ev if base == "ev" else f.market_cap
    if not (np.isfinite(m) and np.isfinite(numerador) and m > 0 and numerador > 0):
        return float("nan")
    return m / numerador if base == "yield" else numerador / m


def tabela_pares(
    pares: Sequence[Fundamentos], nomes: tuple[NomeMultiplo, ...] = MULTIPLOS
) -> pd.DataFrame:
    """Uma linha por companhia: data do balanço, market cap, EV, métricas e múltiplos (BRL).

    Só com múltiplos de equity (financeiras) não há EV; entra o ROE.
    """
    com_ev = any(DEFINICOES[n][0] == "ev" for n in nomes)
    metricas = list(dict.fromkeys(DEFINICOES[n][1] for n in nomes))
    extras = ["ev"] if com_ev else []
    linhas = []
    for f in pares:
        linha: dict[str, object] = {
            "ticker": f.ticker,
            "data_balanco": f.data_balanco.isoformat(),
            "market_cap": f.market_cap,
        }
        if com_ev:
            linha["ev"] = f.ev
        linha |= {m: f.metrica(m) for m in metricas}
        if not com_ev:
            linha["roe"] = f.roe
        linha |= {n: multiplo(f, n) for n in nomes}
        linhas.append(linha)
    colunas = [
        "ticker",
        "data_balanco",
        "market_cap",
        *extras,
        *metricas,
        *([] if com_ev else ["roe"]),
        *nomes,
    ]
    return pd.DataFrame(linhas, columns=colunas).set_index("ticker")


def winsorizar(valores: pd.Series, inferior: float, superior: float) -> pd.Series:
    """Limita os valores aos percentis `inferior` e `superior` (interpolação linear)."""
    validos = valores.dropna()
    if validos.empty:
        return validos
    return validos.clip(float(validos.quantile(inferior)), float(validos.quantile(superior)))


def estatisticas(
    tabela: pd.DataFrame,
    *,
    inferior: float,
    superior: float,
    min_pares: int,
    nomes: tuple[NomeMultiplo, ...] = MULTIPLOS,
) -> pd.DataFrame:
    """Por múltiplo: n válidos, mediana, média, P25, P75, mínimo, máximo (após winsorizar) e
    `confianca` (`normal` ou `baixa`, se n < `min_pares`)."""
    linhas = {}
    for nome in nomes:
        v = winsorizar(tabela[nome], inferior, superior)
        linhas[nome] = {
            "n": float(len(v)),
            "mediana": v.median(),
            "media": v.mean(),
            "p25": v.quantile(0.25),
            "p75": v.quantile(0.75),
            "minimo": v.min(),
            "maximo": v.max(),
            "confianca": "normal" if len(v) >= min_pares else "baixa",
        }
    df = pd.DataFrame.from_dict(linhas, orient="index")
    df.index.name = "multiplo"
    return df


def celula(df: pd.DataFrame, linha: str, coluna: str) -> float:
    """Valor numérico de `df.loc[linha, coluna]` (estatísticas e implícitos)."""
    return float(cast(float, df.at[linha, coluna]))


def valor_por_acao(alvo: Fundamentos, nome: NomeMultiplo, valor_multiplo: float) -> float:
    """Valor por ação (BRL) do alvo ao múltiplo dado; NaN se a métrica do alvo não for positiva.

    EV: múltiplo x métrica -> ponte -> equity / ações. P/L, P/VP: múltiplo x métrica / ações.
    Dividend yield: dividendos / yield / ações.
    """
    base, metrica = DEFINICOES[nome]
    m = alvo.metrica(metrica)
    if not (np.isfinite(m) and m > 0 and np.isfinite(valor_multiplo) and valor_multiplo > 0):
        return float("nan")
    if base == "ev":
        return pt.ponte(valor_multiplo * m, alvo.itens).valor_por_acao
    equity = m / valor_multiplo if base == "yield" else valor_multiplo * m
    return equity / alvo.itens.acoes


def valores_implicitos(
    alvo: Fundamentos, estat: pd.DataFrame, nomes: tuple[NomeMultiplo, ...] = MULTIPLOS
) -> pd.DataFrame:
    """Por múltiplo: métrica do alvo, múltiplo do próprio alvo, múltiplos dos pares (P25,
    mediana, P75), valores por ação implícitos em cada um e a confiança."""
    linhas = {}
    for nome in nomes:
        linha: dict[str, object] = {
            "metrica": DEFINICOES[nome][1],
            "valor_metrica": alvo.metrica(DEFINICOES[nome][1]),
            "multiplo_alvo": multiplo(alvo, nome),
        }
        linha |= {f"multiplo_{s}": celula(estat, nome, s) for s in ESTATISTICAS}
        linha |= {
            f"valor_{s}": valor_por_acao(alvo, nome, celula(estat, nome, s)) for s in ESTATISTICAS
        }
        linha |= {"n_pares": celula(estat, nome, "n"), "confianca": estat.at[nome, "confianca"]}
        linhas[nome] = linha
    df = pd.DataFrame.from_dict(linhas, orient="index")
    df.index.name = "multiplo"
    return df


@dataclass(frozen=True)
class RegressaoPVP:
    """P/VP = intercepto + inclinacao x ROE, por mínimos quadrados entre os pares."""

    intercepto: float
    inclinacao: float
    r2: float
    n: int

    def pvp(self, roe: float) -> float:
        return self.intercepto + self.inclinacao * roe


def regressao_pvp_roe(tabela: pd.DataFrame, *, min_pares: int) -> RegressaoPVP | None:
    """Regressão P/VP x ROE dos pares com os dois definidos; None com menos de `min_pares`
    pontos ou ROE sem variação."""
    pontos = tabela[["roe", "p_vp"]].astype(float).dropna()
    if len(pontos) < max(min_pares, 2) or pontos["roe"].nunique() < 2:
        return None
    x, y = pontos["roe"].to_numpy(), pontos["p_vp"].to_numpy()
    inclinacao, intercepto = np.polyfit(x, y, 1)
    previsto = intercepto + inclinacao * x
    total = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - float(((y - previsto) ** 2).sum()) / total if total > 0 else float("nan")
    return RegressaoPVP(float(intercepto), float(inclinacao), r2, len(pontos))


@dataclass(frozen=True)
class ResultadoMultiplos:
    alvo: Fundamentos
    pares: pd.DataFrame  # tabela_pares (sem o alvo)
    estatisticas: pd.DataFrame
    implicitos: pd.DataFrame
    avisos: tuple[str, ...]
    nomes: tuple[NomeMultiplo, ...] = MULTIPLOS
    regressao: RegressaoPVP | None = None  # financeiras

    def mediana(self, nome: NomeMultiplo) -> float:
        """Mediana dos pares; NaN se nenhum par válido."""
        return celula(self.estatisticas, nome, "mediana")

    @property
    def valor_regressao(self) -> float:
        """Valor por ação do alvo ao P/VP da regressão no ROE dele (NaN sem regressão)."""
        if self.regressao is None or not np.isfinite(self.alvo.roe):
            return float("nan")
        return valor_por_acao(self.alvo, "p_vp", self.regressao.pvp(self.alvo.roe))


def avaliar(
    alvo: Fundamentos,
    pares: Sequence[Fundamentos],
    *,
    inferior: float,
    superior: float,
    min_pares: int,
    nomes: tuple[NomeMultiplo, ...] = MULTIPLOS,
) -> ResultadoMultiplos:
    """Múltiplos dos pares (sem o próprio alvo), estatísticas e valores implícitos do alvo.

    Par com P/VP abaixo de `PVP_MINIMO_PLAUSIVEL` é excluído (provável escala das ações); no
    alvo, o mesmo sinal só gera aviso.
    """
    avisos: list[str] = []
    outros = []
    for f in pares:
        if f.ticker == alvo.ticker:
            continue
        if multiplo(f, "p_vp") < PVP_MINIMO_PLAUSIVEL:
            avisos.append(_aviso_escala(f, "excluído dos pares"))
        else:
            outros.append(f)
    if multiplo(alvo, "p_vp") < PVP_MINIMO_PLAUSIVEL:
        avisos.append(_aviso_escala(alvo, "confira antes de usar o resultado"))
    if not outros:
        raise ErroModelo(f"{alvo.ticker} sem pares válidos para os múltiplos.")
    tab = tabela_pares(outros, nomes)
    estat = estatisticas(
        tab, inferior=inferior, superior=superior, min_pares=min_pares, nomes=nomes
    )
    impl = valores_implicitos(alvo, estat, nomes)
    baixa = [n for n in nomes if estat.loc[n, "confianca"] == "baixa"]
    if baixa:
        detalhe = ", ".join(f"{n} ({celula(estat, n, 'n'):.0f})" for n in baixa)
        avisos.append(
            f"Múltiplos com menos de {min_pares} pares válidos (baixa confiança): {detalhe}."
        )
    sem_metrica = [n for n in nomes if not alvo.metrica(DEFINICOES[n][1]) > 0]
    if sem_metrica:
        avisos.append(
            f"{alvo.ticker} sem métrica positiva para {', '.join(sem_metrica)}: sem valor "
            "implícito por esses múltiplos."
        )
    regressao = None
    if "roe" in tab.columns:
        regressao = regressao_pvp_roe(tab, min_pares=min_pares)
        if regressao is None:
            avisos.append(
                f"Regressão P/VP x ROE sem pontos suficientes (mínimo de {min_pares} pares)."
            )
    return ResultadoMultiplos(alvo, tab, estat, impl, tuple(avisos), nomes, regressao)


def _aviso_escala(f: Fundamentos, consequencia: str) -> str:
    return (
        f"{f.ticker}: P/VP de {multiplo(f, 'p_vp'):.3f} (market cap de {f.market_cap:,.0f}) é "
        "implausível; a quantidade de ações deve estar em milhares (escala_acoes no "
        f"cadastro_manual.csv, ADR 0003): {consequencia}."
    )
