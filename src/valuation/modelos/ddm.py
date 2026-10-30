"""DDM em dois estágios e checagem por lucro residual (seção 11.3 do CLAUDE.md e ADR 0013).

Fluxos: dividendos projetados (`projecao.financeira.projetar`), descontados ao Ke no **fim** de
cada ano, como na fórmula do guia (Div_t / (1 + Ke)^t): tau_t = (31/12 do ano - data-base) / 365;
no ano corrente só entra a parte por vir (fração do ano).

Valor terminal pelo P/VP justificado: (ROE_LP - g) / (Ke - g) x PL_T, descontado pelo tau do
último ano. O valor é do acionista da controladora (lucro e PL da controladora): não há ponte.

Lucro residual: V = PL_0 + soma (lucro_t - c_t x PL_{t-1}) x d_t + d_T x PL_T x (ROE_LP - Ke) /
(Ke - g), com d_t o fator de desconto e c_t = d_{t-1} / d_t - 1 o custo do capital no trecho
((1 + Ke)^fração - 1 no ano corrente). Com lucro, dividendos e PL fechando (PL_t = PL_{t-1} +
lucro_t - dividendos_t), os dois valores coincidem; divergência acima de `TOLERANCIA_LUCRO_RESIDUAL`
vira aviso (premissa ou implementação inconsistente).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from valuation.modelos import ErroModelo
from valuation.projecao import ErroProjecao
from valuation.projecao import financeira as pf
from valuation.projecao.sugestor import pct

TOLERANCIA_LUCRO_RESIDUAL = 0.001


def prazos(anos: pd.Index, data_base: dt.date) -> np.ndarray:
    """tau de cada ano: anos entre a data-base e 31/12 do ano."""
    return np.array([(dt.date(int(a), 12, 31) - data_base).days / 365 for a in anos])


@dataclass(frozen=True)
class ResultadoDDM:
    fluxos: pd.DataFrame  # por ano: dividendos, tau, fator, vp, lucro_residual, vp_lucro_residual
    ke: float
    g: float
    roe_longo_prazo: float
    pvp_justificado: float  # (ROE_LP - g) / (Ke - g)
    pl_inicial: float
    pl_final: float  # PL_T
    valor_terminal: float  # P/VP justificado x PL_T, no fim do último ano
    vp_dividendos: float
    vp_terminal: float
    vp_lucro_residual: float  # explícito
    vp_lucro_residual_terminal: float
    avisos: tuple[str, ...]

    @property
    def valor(self) -> float:
        """Valor do PL da controladora pelo DDM."""
        return self.vp_dividendos + self.vp_terminal

    @property
    def valor_lucro_residual(self) -> float:
        return self.pl_inicial + self.vp_lucro_residual + self.vp_lucro_residual_terminal

    @property
    def divergencia(self) -> float:
        """Lucro residual / DDM - 1 (NaN se o valor do DDM não for positivo)."""
        return self.valor_lucro_residual / self.valor - 1 if self.valor > 0 else float("nan")

    @property
    def vt_sobre_valor(self) -> float:
        return self.vp_terminal / self.valor if self.valor > 0 else float("nan")

    @property
    def pvp_implicito(self) -> float:
        """Valor / PL inicial."""
        return self.valor / self.pl_inicial


def descontar(
    projecao: pd.DataFrame,
    *,
    ke: float,
    g: float,
    pl_inicial: float,
    data_base: dt.date,
    alerta_vt_sobre_valor: float,
) -> ResultadoDDM:
    """Valor do PL da controladora a partir da projeção (`COLUNAS_PROJECAO` do DDM)."""
    if ke <= g:
        raise ErroModelo(
            f"Ke de {pct(ke, 2)} não é maior que o g terminal de {pct(g, 2)}: a perpetuidade "
            "não converge."
        )
    por_vir = projecao[projecao["fracao"] > 0]
    if por_vir.empty:
        raise ErroModelo("A projeção não tem nenhum ano com fluxo por vir.")
    ultimo = projecao.iloc[-1]
    roe_lp = float(ultimo["roe"])
    pl_final = float(ultimo["pl_final"])

    fluxos = pd.DataFrame(index=por_vir.index)
    fluxos["dividendos"] = por_vir["dividendos"]
    fluxos["tau"] = prazos(por_vir.index, data_base)
    fluxos["fator"] = (1 + ke) ** -fluxos["tau"]
    fluxos["vp"] = fluxos["dividendos"] * fluxos["fator"]
    fator_anterior = np.concatenate(([1.0], fluxos["fator"].to_numpy()[:-1]))
    custo = fator_anterior / fluxos["fator"].to_numpy() - 1
    fluxos["lucro_residual"] = por_vir["lucro"] - custo * por_vir["pl_inicial"]
    fluxos["vp_lucro_residual"] = fluxos["lucro_residual"] * fluxos["fator"]

    fator_t = float(fluxos["fator"].iloc[-1])
    pvp = (roe_lp - g) / (ke - g)
    vt = pvp * pl_final
    resultado = ResultadoDDM(
        fluxos=fluxos,
        ke=ke,
        g=g,
        roe_longo_prazo=roe_lp,
        pvp_justificado=pvp,
        pl_inicial=pl_inicial,
        pl_final=pl_final,
        valor_terminal=vt,
        vp_dividendos=float(fluxos["vp"].sum()),
        vp_terminal=vt * fator_t,
        vp_lucro_residual=float(fluxos["vp_lucro_residual"].sum()),
        vp_lucro_residual_terminal=fator_t * pl_final * (roe_lp - ke) / (ke - g),
        avisos=(),
    )
    avisos: list[str] = []
    if resultado.valor <= 0:
        avisos.append(f"Valor pelo DDM não positivo ({resultado.valor:,.0f}).")
    else:
        if resultado.vt_sobre_valor > alerta_vt_sobre_valor:
            avisos.append(
                f"Valor terminal é {pct(resultado.vt_sobre_valor, 0)} do valor (alerta acima de "
                f"{pct(alerta_vt_sobre_valor, 0)}): o resultado depende sobretudo da perpetuidade."
            )
        if abs(resultado.divergencia) > TOLERANCIA_LUCRO_RESIDUAL:
            avisos.append(
                f"Lucro residual diverge {pct(resultado.divergencia, 2)} do DDM: premissas "
                "inconsistentes (lucro, dividendos e PL não fecham)."
            )
    if roe_lp < ke:
        pvp_texto = f"{pvp:.2f}".replace(".", ",")
        avisos.append(
            f"ROE de longo prazo ({pct(roe_lp)}) abaixo do Ke ({pct(ke)}): P/VP justificado "
            f"{pvp_texto} < 1 (crescer destrói valor)."
        )
    return replace(resultado, avisos=tuple(avisos))


@dataclass(frozen=True)
class DadosDDM:
    """O que não muda entre cenários e células da sensibilidade."""

    pl_inicial: float  # PL da controladora no último balanço até a data-base
    acoes: float  # em circulação (ON + PN)
    data_balanco: dt.date
    data_base: dt.date
    alerta_vt_sobre_valor: float


@dataclass(frozen=True)
class AvaliacaoDDM:
    premissas: pf.PremissasFinanceiras
    projecao: pd.DataFrame
    ddm: ResultadoDDM
    acoes: float

    @property
    def valor_por_acao(self) -> float:
        return self.ddm.valor / self.acoes

    @property
    def avisos(self) -> tuple[str, ...]:
        return self.ddm.avisos


def avaliar(premissas: pf.PremissasFinanceiras, dados: DadosDDM, *, ke: float) -> AvaliacaoDDM:
    """Projeção -> DDM -> valor por ação, com o g terminal das premissas. Função pura."""
    if dados.acoes <= 0:
        raise ErroModelo(f"Quantidade de ações inválida: {dados.acoes}.")
    try:
        projecao = pf.projetar(dados.pl_inicial, premissas, data_base=dados.data_base)
    except ErroProjecao as e:
        raise ErroModelo(str(e)) from e
    resultado = descontar(
        projecao,
        ke=ke,
        g=premissas.g_terminal,
        pl_inicial=dados.pl_inicial,
        data_base=dados.data_base,
        alerta_vt_sobre_valor=dados.alerta_vt_sobre_valor,
    )
    return AvaliacaoDDM(premissas, projecao, resultado, dados.acoes)


def tabela(av: AvaliacaoDDM) -> pd.DataFrame:
    """Projeção ano a ano com o desconto e o lucro residual (`ano` como coluna)."""
    colunas = ["tau", "fator", "vp", "lucro_residual", "vp_lucro_residual"]
    return av.projecao.join(av.ddm.fluxos[colunas]).reset_index()
