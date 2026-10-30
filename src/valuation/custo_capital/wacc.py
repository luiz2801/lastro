"""Estrutura de capital e WACC (seção 10.3 do guia); Ke das financeiras (seção 10.4).

WACC = Ke x E/(D+E) + Kd x (1 - t) x D/(D+E): equity a valor de mercado, dívida bruta contábil
(proxy do valor de mercado), na moeda de reporte. Com estrutura-alvo diferente da atual, o beta
da regressão (que reflete a alavancagem atual) é desalavancado e realavancado no alvo (Hamada).

Financeiras só têm Ke (`CustoCapitalFinanceira`): depósitos e captações são operação, não
financiamento, e não entram num WACC nem na alavancagem do beta.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, replace
from typing import Literal

import pandas as pd

from valuation.custo_capital import ErroCustoCapital
from valuation.custo_capital import beta as bt
from valuation.custo_capital.capm import CustoCapitalProprio
from valuation.custo_capital.kd import ResultadoKd

MetodoEstrutura = Literal["mercado_atual", "setor", "manual"]


@dataclass(frozen=True)
class Estrutura:
    metodo: MetodoEstrutura
    divida: float  # dívida bruta contábil (com arrendamento, se IFRS 16 = dívida)
    equity: float  # market cap na moeda de reporte
    peso_divida: float  # D/(D+E) usado no WACC

    @property
    def peso_equity(self) -> float:
        return 1 - self.peso_divida

    @property
    def divida_sobre_equity(self) -> float:
        return self.peso_divida / self.peso_equity

    @property
    def divida_sobre_equity_atual(self) -> float:
        return self.divida / self.equity


def estrutura(
    *,
    metodo: MetodoEstrutura,
    divida: float,
    equity: float,
    divida_sobre_capital_alvo: float | None = None,
) -> Estrutura:
    if equity <= 0:
        raise ErroCustoCapital(f"Market cap não positivo ({equity:,.0f}): sem peso do equity.")
    if divida < 0:
        raise ErroCustoCapital(f"Dívida bruta negativa ({divida:,.0f}).")
    if metodo == "mercado_atual":
        return Estrutura(metodo, divida, equity, divida / (divida + equity))
    if divida_sobre_capital_alvo is None:
        origem = "a mediana dos pares" if metodo == "setor" else "divida_sobre_capital"
        raise ErroCustoCapital(f"Estrutura {metodo} exige {origem}.")
    return Estrutura(metodo, divida, equity, divida_sobre_capital_alvo)


def wacc(ke: float, kd: float, aliquota: float, peso_divida: float) -> float:
    return ke * (1 - peso_divida) + kd * (1 - aliquota) * peso_divida


def beta_na_estrutura(
    resultado: bt.ResultadoBeta, est: Estrutura, aliquota: float
) -> bt.ResultadoBeta:
    """Beta da regressão realavancado na estrutura-alvo; nos demais casos, o próprio beta.

    Comparáveis já saem realavancados no alvo e o beta manual é tomado como dado.
    """
    if resultado.metodo != "regressao" or est.metodo == "mercado_atual":
        return resultado
    desalav = bt.desalavancar(resultado.beta, est.divida_sobre_equity_atual, aliquota)
    return replace(resultado, beta=bt.realavancar(desalav, est.divida_sobre_equity, aliquota))


def validar_g(taxa: float, g: float, nome: str = "WACC") -> None:
    """A perpetuidade exige taxa de desconto > g."""
    if taxa <= g:
        raise ErroCustoCapital(
            f"{nome} de {taxa:.2%} não é maior que o g terminal de {g:.2%}: a perpetuidade não "
            "converge. Revise o custo de capital ou terminal.g_nominal."
        )


@dataclass(frozen=True)
class CustoCapital:
    """Resultado da Fase 6, consumido pelo DCF. Taxas em decimal, valores na moeda de reporte."""

    data_base: dt.date
    beta: bt.ResultadoBeta  # beta usado no Ke (já na estrutura-alvo)
    beta_regressao: float | None  # beta antes da realavancagem, se houve
    ke: CustoCapitalProprio
    kd: ResultadoKd
    aliquota: float
    estrutura: Estrutura
    wacc: float
    data_balanco: dt.date
    avisos: tuple[str, ...]

    @property
    def kd_liquido(self) -> float:
        return self.kd.kd * (1 - self.aliquota)


def montar(
    *,
    data_base: dt.date,
    beta: bt.ResultadoBeta,
    ke: CustoCapitalProprio,
    kd: ResultadoKd,
    aliquota: float,
    estrutura: Estrutura,
    data_balanco: dt.date,
    avisos: tuple[str, ...] = (),
) -> CustoCapital:
    """Junta os componentes. `ke` deve ter sido calculado com `beta_na_estrutura(...)`."""
    taxa = wacc(ke.ke, kd.kd, aliquota, estrutura.peso_divida)
    return CustoCapital(
        data_base=data_base,
        beta=beta,
        beta_regressao=beta.beta_bruto if beta.metodo == "regressao" else None,
        ke=ke,
        kd=kd,
        aliquota=aliquota,
        estrutura=estrutura,
        wacc=taxa,
        data_balanco=data_balanco,
        avisos=(*beta.avisos, *kd.avisos, *avisos),
    )


@dataclass(frozen=True)
class CustoCapitalFinanceira:
    """Custo de capital de uma financeira: só o Ke (seção 10.4 do guia)."""

    data_base: dt.date
    beta: bt.ResultadoBeta
    ke: CustoCapitalProprio
    data_balanco: dt.date
    avisos: tuple[str, ...]


def montar_financeira(
    *,
    data_base: dt.date,
    beta: bt.ResultadoBeta,
    ke: CustoCapitalProprio,
    data_balanco: dt.date,
    avisos: tuple[str, ...] = (),
) -> CustoCapitalFinanceira:
    return CustoCapitalFinanceira(data_base, beta, ke, data_balanco, avisos=(*beta.avisos, *avisos))


Linha = tuple[str, float | None, str]


def _linhas_ke(data_base: dt.date, b: bt.ResultadoBeta, ke: CustoCapitalProprio) -> list[Linha]:
    regressao = b.metodo == "regressao"
    return [
        ("data_base", None, data_base.isoformat()),
        ("moeda", None, f"{ke.moeda} (moeda de reporte; taxas e valores nela)"),
        ("metodo_ke", None, ke.metodo),
        ("beta_metodo", None, b.metodo + (f" ({b.ticker})" if b.ticker else "")),
        ("beta_bruto", b.beta_bruto, "OLS semanal contra o Ibovespa" if regressao else ""),
        ("beta_erro_padrao", b.erro_padrao, ""),
        ("beta_r2", b.r2, ""),
        ("beta_n_obs", None if b.n_obs is None else float(b.n_obs), ""),
        ("beta_janela", None, f"{b.inicio} a {b.fim}" if b.inicio else ""),
    ]


def _linhas_capm(ke: CustoCapitalProprio) -> list[Linha]:
    return [
        ("rf", ke.rf, "BRL (NTN-F longa)" if ke.metodo == "brl_direto" else "USD (manual)"),
        ("erp", ke.erp, ""),
        ("crp", ke.crp if ke.metodo == "usd_crp" else None, ""),
        ("ke_usd", ke.ke_usd, ""),
        ("inflacao_brl", ke.inflacao_brl, "IPCA de longo prazo (Focus)"),
        ("inflacao_usd", ke.inflacao_usd, ""),
        ("ke", ke.ke, ""),
    ]


def _quadro(linhas: list[Linha], avisos: tuple[str, ...]) -> pd.DataFrame:
    linhas = [*linhas, *(("aviso", None, a) for a in avisos)]
    df = pd.DataFrame(linhas, columns=["componente", "valor", "detalhe"])
    df["valor"] = df["valor"].astype("float64")
    return df


def tabela(cc: CustoCapital) -> pd.DataFrame:
    """Componentes do custo de capital para `wacc.csv`: `componente, valor, detalhe`.

    `valor` é sempre numérico (vazio quando não se aplica); textos vão em `detalhe`.
    """
    b, ke, kd, est = cc.beta, cc.ke, cc.kd, cc.estrutura
    linhas: list[Linha] = [
        *_linhas_ke(cc.data_base, b, ke),
        ("beta_regressao", cc.beta_regressao, "Blume aplicado, se configurado"),
        ("beta", b.beta, "usado no Ke (na estrutura-alvo)"),
        *_linhas_capm(ke),
        ("kd_metodo", None, kd.metodo),
        ("kd_bruto", kd.kd_bruto, f"mediana {kd.anos[0]}-{kd.anos[-1]}" if kd.anos else ""),
        ("kd_piso", kd.piso, ""),
        ("kd_teto", kd.teto, ""),
        ("kd", kd.kd, "antes do imposto"),
        ("aliquota", cc.aliquota, "benefício fiscal da dívida"),
        ("kd_liquido", cc.kd_liquido, ""),
        ("divida_bruta", est.divida, f"balanço de {cc.data_balanco}"),
        ("market_cap", est.equity, ""),
        ("estrutura_metodo", None, est.metodo),
        ("peso_divida", est.peso_divida, "D/(D+E)"),
        ("peso_equity", est.peso_equity, "E/(D+E)"),
        ("wacc", cc.wacc, ""),
    ]
    return _quadro(linhas, cc.avisos)


def tabela_financeira(cc: CustoCapitalFinanceira) -> pd.DataFrame:
    """Como `tabela`, só até o Ke (financeiras): `componente, valor, detalhe`."""
    linhas: list[Linha] = [
        *_linhas_ke(cc.data_base, cc.beta, cc.ke),
        ("beta", cc.beta.beta, "usado no Ke"),
        *_linhas_capm(cc.ke),
        ("data_balanco", None, f"{cc.data_balanco} (PL inicial do DDM)"),
    ]
    return _quadro(linhas, cc.avisos)
