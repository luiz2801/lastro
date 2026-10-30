"""Premissas sugeridas e projeção do DDM das financeiras (seção 11.3 do CLAUDE.md, ADR 0012).

Entrada: métricas anuais de `contabil.financeiras.metricas` (índice = ano), só com exercícios
encerrados na data-base. Janelas como no sugestor das não financeiras ("5a" e "10a" = os 5 e os 10
últimos exercícios).

- ROE: começa na mediana de 5a e converge linearmente para o ROE de longo prazo, a mediana de
  10a (decisão do usuário).
- Payout: começa na mediana de 5a (limitada a [0, 1]) e converge para 1 - g / ROE de longo prazo,
  o payout que sustenta o crescimento g na perpetuidade.
- Cenários: ±1 desvio-padrão (10a) do ROE, limitado a [1, 5] p.p., somado ao ROE de todos os anos.

Projeção (função pura): a partir do PL da controladora no último balanço até a data-base, para
cada ano t a partir do primeiro exercício aberto:

    lucro_t      = ROE_t x PL_{t-1} x fração_t
    dividendos_t = payout_t x lucro_t
    PL_t         = PL_{t-1} + lucro_t - dividendos_t

`fração` = parte do ano posterior à data-base (como no FCFF). O lucro entre o balanço e a data-base
não entra (aproximação; o mesmo vale para o FCFF).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from valuation.projecao import ErroProjecao
from valuation.projecao import projetor as pj
from valuation.projecao.premissas import (
    SUGERIDO,
    CenariosFinanceira,
    DeltaCenarioFinanceira,
    ProjecaoFinanceira,
)
from valuation.projecao.sugestor import (
    DELTA_MAX,
    DELTA_MIN,
    JANELA_CURTA,
    JANELA_LONGA,
    Sugestao,
    pct,
    pp,
)

PAYOUT_MIN, PAYOUT_MAX = 0.0, 1.0
COLUNAS_PROJECAO = (
    "fracao",
    "roe",
    "payout",
    "pl_inicial",
    "lucro",
    "dividendos",
    "pl_final",
)


@dataclass(frozen=True)
class SugestoesFinanceira:
    ano_base: int  # último exercício do histórico
    roe_inicio: Sugestao
    roe_fim: Sugestao  # ROE de longo prazo
    payout_inicio: Sugestao
    g_terminal: Sugestao
    delta_roe: Sugestao  # magnitude; o sinal depende do cenário
    estatisticas: pd.DataFrame  # linhas ultimo, mediana_5a, mediana_10a x colunas de `razoes`
    avisos: tuple[str, ...]


def _janela(serie: pd.Series, ano_base: int, n: int) -> pd.Series:
    return serie[(serie.index > ano_base - n) & (serie.index <= ano_base)].dropna()


def _faixa(serie: pd.Series) -> str:
    anos = serie.dropna().index
    return f"{min(anos)}-{max(anos)}" if len(anos) else "sem dados"


def razoes(historico: pd.DataFrame) -> pd.DataFrame:
    """ROE e payout por ano (anos faltantes como NaN)."""
    if historico.empty:
        raise ErroProjecao("Histórico vazio: sem exercícios para sugerir premissas.")
    anos = pd.RangeIndex(int(historico.index.min()), int(historico.index.max()) + 1, name="ano")
    h = historico.reindex(anos)
    return pd.DataFrame({"roe": h["roe"], "payout": h["payout"]}, index=anos).astype(float)


def sugerir(historico: pd.DataFrame, *, g_terminal: Sugestao) -> SugestoesFinanceira:
    """Premissas do DDM sugeridas pelo histórico, com a origem de cada uma."""
    r = razoes(historico)
    ano_base = int(r.index.max())
    g = g_terminal.valor
    avisos: list[str] = []
    roe5 = _janela(r["roe"], ano_base, JANELA_CURTA)
    roe10 = _janela(r["roe"], ano_base, JANELA_LONGA)
    if roe5.empty:
        raise ErroProjecao(
            "Sem ROE nos últimos exercícios (são precisos dois balanços seguidos); defina "
            "projecao.roe no YAML."
        )
    if len(roe10) < JANELA_LONGA:
        avisos.append(
            f"ROE de {len(roe10)} exercícios (menos que {JANELA_LONGA}): medianas e desvio com "
            "poucos pontos."
        )
    roe_inicio = Sugestao(float(roe5.median()), f"mediana do ROE {_faixa(roe5)}")
    roe_fim = Sugestao(float(roe10.median()), f"mediana do ROE {_faixa(roe10)}")
    if roe_fim.valor <= g:
        avisos.append(
            f"ROE de longo prazo sugerido ({pct(roe_fim.valor)}) não supera o g terminal "
            f"({pct(g)}): fixe projecao.roe.fim no YAML."
        )

    p5 = _janela(r["payout"], ano_base, JANELA_CURTA)
    if p5.empty:
        longo = payout_final(roe_fim.valor, g) if roe_fim.valor > g else PAYOUT_MAX
        payout_inicio = Sugestao(
            float(np.clip(longo, PAYOUT_MIN, PAYOUT_MAX)),
            "sem dividendos no histórico: o payout de longo prazo",
        )
        avisos.append("Sem dividendos pagos no histórico: payout inicial = o de longo prazo.")
    else:
        mediana = float(p5.median())
        origem = f"mediana do payout {_faixa(p5)}"
        if not PAYOUT_MIN <= mediana <= PAYOUT_MAX:
            origem += f" = {pct(mediana)}, limitada a [0%, 100%]"
        payout_inicio = Sugestao(float(np.clip(mediana, PAYOUT_MIN, PAYOUT_MAX)), origem)

    if len(roe10) >= 2:
        sigma = float(roe10.std(ddof=1))
        valor = float(np.clip(sigma, DELTA_MIN, DELTA_MAX))
        origem = f"1 desvio-padrão do ROE {_faixa(roe10)} = {pp(sigma)}"
        if valor != sigma:
            origem += f", limitado a [{pp(DELTA_MIN)}, {pp(DELTA_MAX)}]"
        delta_roe = Sugestao(valor, origem)
    else:
        delta_roe = Sugestao(DELTA_MIN, f"piso de {pp(DELTA_MIN)} (histórico curto)")
        avisos.append("Histórico curto para o desvio-padrão do ROE: delta dos cenários no piso.")

    resumo = pd.DataFrame(
        {
            "ultimo": r.loc[ano_base],
            "mediana_5a": r.apply(lambda s: _janela(s, ano_base, JANELA_CURTA).median()),
            "mediana_10a": r.apply(lambda s: _janela(s, ano_base, JANELA_LONGA).median()),
        }
    ).T
    return SugestoesFinanceira(
        ano_base=ano_base,
        roe_inicio=roe_inicio,
        roe_fim=roe_fim,
        payout_inicio=payout_inicio,
        g_terminal=g_terminal,
        delta_roe=delta_roe,
        estatisticas=resumo,
        avisos=tuple(avisos),
    )


def payout_final(roe_longo_prazo: float, g: float) -> float:
    """Payout que sustenta g na perpetuidade: 1 - g / ROE (retenção g / ROE)."""
    if roe_longo_prazo <= max(g, 0.0):
        raise ErroProjecao(
            f"ROE de longo prazo ({pct(roe_longo_prazo)}) não supera o g terminal ({pct(g)}): "
            "o payout sustentável seria negativo."
        )
    return 1 - g / roe_longo_prazo


@dataclass(frozen=True)
class PremissasFinanceiras:
    """Premissas numéricas de um cenário do DDM; `roe` com um valor por ano de `anos`."""

    anos: tuple[int, ...]
    roe: tuple[float, ...]
    payout_inicio: float
    g_terminal: float
    cenario: pj.NomeCenario = "base"

    @property
    def roe_longo_prazo(self) -> float:
        return self.roe[-1]

    @property
    def payout(self) -> tuple[float, ...]:
        """De `payout_inicio` a 1 - g / ROE de longo prazo, linear."""
        fim = payout_final(self.roe_longo_prazo, self.g_terminal)
        return pj.linear(self.payout_inicio, fim, len(self.anos))


def anos_projetados(data_base: dt.date, horizonte: int) -> tuple[int, ...]:
    """Do primeiro exercício aberto na data-base até completar `horizonte` anos."""
    if horizonte < 1:
        raise ErroProjecao(f"Horizonte de projeção inválido: {horizonte}.")
    inicio = pj.primeiro_ano_aberto(data_base)
    return tuple(range(inicio, inicio + horizonte))


def resolver(
    config: ProjecaoFinanceira, sugestoes: SugestoesFinanceira, *, anos: tuple[int, ...]
) -> PremissasFinanceiras:
    """Premissas do cenário base: `sugerido` vira a sugestão; número ou lista ficam como estão."""
    s = sugestoes
    roe = pj.trajetoria(config.roe, s.roe_inicio, s.roe_fim, len(anos), "projecao.roe")
    premissas = PremissasFinanceiras(
        anos=anos,
        roe=roe,
        payout_inicio=pj.escolher(config.payout_inicio, s.payout_inicio),
        g_terminal=s.g_terminal.valor,
    )
    payout_final(premissas.roe_longo_prazo, premissas.g_terminal)  # falha cedo se ROE <= g
    return premissas


def resolver_cenarios(
    cenarios: CenariosFinanceira, sugestoes: SugestoesFinanceira
) -> dict[pj.NomeCenario, float]:
    """Delta do ROE de cada cenário; o sugerido é -1 desvio no pessimista e +1 no otimista."""

    def delta(d: DeltaCenarioFinanceira, sinal: int) -> float:
        return sinal * sugestoes.delta_roe.valor if d.roe_pp == SUGERIDO else float(d.roe_pp)

    return {
        "pessimista": delta(cenarios.pessimista, -1),
        "base": 0.0,
        "otimista": delta(cenarios.otimista, 1),
    }


def aplicar_cenario(
    base: PremissasFinanceiras, delta_roe: float, cenario: pj.NomeCenario
) -> PremissasFinanceiras:
    """Soma o delta ao ROE de todos os anos (o de longo prazo e o payout final acompanham)."""
    return replace(base, roe=tuple(x + delta_roe for x in base.roe), cenario=cenario)


def projetar(
    pl_inicial: float, premissas: PremissasFinanceiras, *, data_base: dt.date
) -> pd.DataFrame:
    """Projeção anual (índice `ano`, colunas `COLUNAS_PROJECAO`), em unidades da moeda."""
    if not pl_inicial > 0:
        raise ErroProjecao(f"PL da controladora não positivo ({pl_inicial:,.0f}): sem DDM.")
    p = premissas
    payout = p.payout
    linhas = []
    pl = pl_inicial
    for ano, roe, pay in zip(p.anos, p.roe, payout, strict=True):
        fracao = pj.fracao_restante(ano, data_base)
        lucro = roe * pl * fracao
        dividendos = pay * lucro
        linhas.append(
            {
                "fracao": fracao,
                "roe": roe,
                "payout": pay,
                "pl_inicial": pl,
                "lucro": lucro,
                "dividendos": dividendos,
                "pl_final": pl + lucro - dividendos,
            }
        )
        pl = pl + lucro - dividendos
    return pd.DataFrame(linhas, index=pd.Index(p.anos, name="ano"))[list(COLUNAS_PROJECAO)]
