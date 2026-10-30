"""DCF do FCFF (seção 11.1 do CLAUDE.md e ADR 0008).

VP(FCFF) = soma de FCFF_t x fração_t / (1 + WACC)^tau_t, com tau_t em anos entre a data-base e o
fim do período t (dias / 365) ou, com a convenção de meio período, o ponto médio do trecho por vir
(fim - fração / 2; no ano corrente, o meio do que resta). Exercício já encerrado sem DFP (fração 0)
não entra.

Valor terminal (value driver): NOPAT_{T+1} = NOPAT_T x (1 + g); FCFF_{T+1} = NOPAT_{T+1} x
(1 - g / RONIC); VT = FCFF_{T+1} / (WACC - g), descontado pelo tau do último ano explícito.
RONIC = WACC por padrão (crescimento sem criação de valor).

`avaliar` junta projeção, desconto e ponte numa função pura e rápida, chamada muitas vezes pela
sensibilidade e pelos cenários.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, replace
from typing import Literal

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from valuation.modelos import ErroModelo
from valuation.modelos import ponte as pt
from valuation.projecao import projetor as pj

Ronic = Literal["wacc"] | float


def resolver_ronic(
    escolha: Literal["wacc", "roic_historico"] | float, *, roic_historico: float | None
) -> Ronic:
    """`wacc` fica simbólico (acompanha o WACC de cada cálculo); `roic_historico` vira número."""
    if escolha != "roic_historico":
        return escolha
    if roic_historico is None or not np.isfinite(roic_historico) or roic_historico <= 0:
        raise ErroModelo(
            "terminal.ronic = roic_historico, mas o ROIC histórico não é positivo: "
            "use wacc ou um número."
        )
    return roic_historico


def prazos(
    anos: pd.Index, fracoes: pd.Series, data_base: dt.date, meio_periodo: bool
) -> np.ndarray:
    """tau de cada ano, em anos a partir da data-base (fim ou meio do trecho por vir)."""
    fim = np.array([(dt.date(int(a), 12, 31) - data_base).days / 365 for a in anos])
    return fim - fracoes.to_numpy(dtype=float) / 2 if meio_periodo else fim


@dataclass(frozen=True)
class ResultadoDCF:
    fluxos: pd.DataFrame  # índice ano (só fração > 0): fracao, fcff, fluxo, tau, fator, vp
    wacc: float
    g: float
    ronic: float
    nopat_terminal: float  # NOPAT_{T+1}
    fcff_terminal: float  # FCFF_{T+1}
    valor_terminal: float  # na data do último ano explícito
    vp_fluxos: float
    vp_terminal: float
    ev_ebitda_terminal: float  # VT / EBITDA_T (NaN se EBITDA_T <= 0)
    avisos: tuple[str, ...]

    @property
    def ev(self) -> float:
        return self.vp_fluxos + self.vp_terminal

    @property
    def tv_sobre_ev(self) -> float:
        return self.vp_terminal / self.ev if self.ev > 0 else float("nan")


def descontar(
    projecao: pd.DataFrame,
    *,
    wacc: float,
    g: float,
    ronic: Ronic,
    data_base: dt.date,
    meio_periodo: bool,
    alerta_tv_sobre_ev: float,
) -> ResultadoDCF:
    """Valor da firma a partir da projeção (`projetor.projetar`) na moeda de reporte."""
    if wacc <= g:
        raise ErroModelo(
            f"WACC de {wacc:.2%} não é maior que o g terminal de {g:.2%}: a perpetuidade não "
            "converge."
        )
    r = wacc if ronic == "wacc" else float(ronic)
    if r <= max(g, 0.0):
        raise ErroModelo(
            f"RONIC de {r:.2%} não é maior que o g terminal de {g:.2%}: o reinvestimento "
            "consumiria todo o NOPAT da perpetuidade."
        )
    por_vir = projecao[projecao["fracao"] > 0]
    if por_vir.empty:
        raise ErroModelo("A projeção não tem nenhum ano com fluxo por vir.")

    fluxos = pd.DataFrame(index=por_vir.index)
    fluxos["fracao"] = por_vir["fracao"]
    fluxos["fcff"] = por_vir["fcff"]
    fluxos["fluxo"] = por_vir["fcff"] * por_vir["fracao"]
    fluxos["tau"] = prazos(por_vir.index, por_vir["fracao"], data_base, meio_periodo)
    fluxos["fator"] = (1 + wacc) ** -fluxos["tau"]
    fluxos["vp"] = fluxos["fluxo"] * fluxos["fator"]

    ultimo = projecao.iloc[-1]
    nopat_t1 = float(ultimo["nopat"]) * (1 + g)
    fcff_t1 = nopat_t1 * (1 - g / r)
    vt = fcff_t1 / (wacc - g)
    vp_vt = vt * float(fluxos["fator"].iloc[-1])
    ebitda_t = float(ultimo["ebitda"])

    resultado = ResultadoDCF(
        fluxos=fluxos,
        wacc=wacc,
        g=g,
        ronic=r,
        nopat_terminal=nopat_t1,
        fcff_terminal=fcff_t1,
        valor_terminal=vt,
        vp_fluxos=float(fluxos["vp"].sum()),
        vp_terminal=vp_vt,
        ev_ebitda_terminal=vt / ebitda_t if ebitda_t > 0 else float("nan"),
        avisos=(),
    )
    avisos: list[str] = []
    if nopat_t1 <= 0:
        avisos.append("NOPAT do último ano explícito não é positivo: valor terminal <= 0.")
    if resultado.ev <= 0:
        avisos.append(f"Valor da firma não positivo ({resultado.ev:,.0f}).")
    elif resultado.tv_sobre_ev > alerta_tv_sobre_ev:
        avisos.append(
            f"Valor terminal é {resultado.tv_sobre_ev:.0%} do EV (alerta acima de "
            f"{alerta_tv_sobre_ev:.0%}): o resultado depende sobretudo da perpetuidade."
        )
    return replace(resultado, avisos=tuple(avisos))


def g_implicito(
    multiplo_saida: float, *, ebitda_t: float, nopat_t: float, wacc: float, ronic: Ronic
) -> float | None:
    """g da perpetuidade que faz VT = `multiplo_saida` x EBITDA_T (checagem do terminal).

    Com K = múltiplo x EBITDA_T / NOPAT_T, resolve (1 + g)(1 - g/RONIC) / (WACC - g) = K. Com
    RONIC = WACC a solução é fechada: g = K x WACC - 1. None se não houver g < min(WACC, RONIC)
    (múltiplo, EBITDA ou NOPAT não positivos, ou RONIC < WACC sem raiz única).
    """
    if not (multiplo_saida > 0 and ebitda_t > 0 and nopat_t > 0):
        return None
    k = multiplo_saida * ebitda_t / nopat_t
    r = wacc if ronic == "wacc" else float(ronic)
    if np.isclose(r, wacc):
        g = k * wacc - 1
        return g if g < wacc else None
    if r < wacc:
        return None

    def h(g: float) -> float:
        return (1 + g) * (r - g) - k * r * (wacc - g)

    # h(-1) < 0 e h(WACC) > 0 com RONIC > WACC: uma única raiz no intervalo.
    return float(brentq(h, -1.0, wacc))


@dataclass(frozen=True)
class DadosAvaliacao:
    """O que não muda entre cenários e células da sensibilidade."""

    historico: pd.DataFrame  # métricas anuais até o último exercício encerrado
    ponte: pt.ItensPonte
    data_base: dt.date
    meio_periodo: bool
    alerta_tv_sobre_ev: float
    cambio: float = 1.0  # BRL por unidade da moeda de reporte (1 se BRL)


@dataclass(frozen=True)
class Avaliacao:
    premissas: pj.PremissasResolvidas
    projecao: pd.DataFrame
    dcf: ResultadoDCF
    ponte: pt.ResultadoPonte
    cambio: float

    @property
    def valor_por_acao(self) -> float:
        """Em BRL: o da moeda de reporte convertido pela taxa spot (só na saída)."""
        return self.ponte.valor_por_acao * self.cambio

    @property
    def avisos(self) -> tuple[str, ...]:
        return self.dcf.avisos


def avaliar(
    premissas: pj.PremissasResolvidas, dados: DadosAvaliacao, *, wacc: float, ronic: Ronic
) -> Avaliacao:
    """Projeção -> DCF -> ponte, com o g terminal das premissas. Função pura."""
    projecao = pj.projetar(dados.historico, premissas, data_base=dados.data_base)
    resultado = descontar(
        projecao,
        wacc=wacc,
        g=premissas.g_terminal,
        ronic=ronic,
        data_base=dados.data_base,
        meio_periodo=dados.meio_periodo,
        alerta_tv_sobre_ev=dados.alerta_tv_sobre_ev,
    )
    return Avaliacao(
        premissas, projecao, resultado, pt.ponte(resultado.ev, dados.ponte), dados.cambio
    )


def tabela(av: Avaliacao) -> pd.DataFrame:
    """Projeção ano a ano com o desconto (`ano`, colunas da projeção, `tau`, `fator`, `vp`)."""
    t = av.projecao.join(av.dcf.fluxos[["fluxo", "tau", "fator", "vp"]])
    return t.reset_index()
