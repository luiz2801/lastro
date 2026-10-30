"""Cenários, ponderação pelo perfil e retorno implícito (seções 8.4 e 12 do CLAUDE.md, ADR 0008).

Cada cenário (pessimista/base/otimista) é avaliado com o mesmo custo de capital; o perfil do
investidor só pondera os valores, define a margem de segurança e o hurdle:

    valor_ponderado      = soma de peso_c x valor_por_acao_c
    preco_maximo_compra  = valor_ponderado x (1 - margem_seguranca)

Retorno esperado ao comprar a preço de mercado, em duas leituras (o valor é linear nos fluxos,
então ponderar os valores equivale a descontar os fluxos ponderados):

- **Ke implícito**: retorno do acionista que, posto no lugar do Ke dentro do WACC (Kd e pesos
  fixos), iguala o valor ponderado ao preço. É o que se compara com o hurdle (Selic + spread).
- **WACC implícito**: taxa de desconto do FCFF que iguala o valor ponderado ao preço.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from scipy.optimize import brentq

from valuation.custo_capital import wacc as wc
from valuation.modelos import ErroModelo, dcf
from valuation.perfil.parametros import ParametrosPerfil
from valuation.projecao import projetor as pj

# Folga acima do g terminal no limite inferior da busca (a perpetuidade explode em WACC = g).
FOLGA_G = 1e-4
TAXA_MAXIMA = 1.0  # 100% a.a.: acima disso a taxa implícita é dada como "sem solução"


def avaliar_cenarios(
    base: pj.PremissasResolvidas,
    deltas: Mapping[pj.NomeCenario, pj.DeltaResolvido],
    dados: dcf.DadosAvaliacao,
    *,
    wacc: float,
    ronic: dcf.Ronic,
    cenarios: tuple[pj.NomeCenario, ...] = pj.CENARIOS,
) -> dict[pj.NomeCenario, dcf.Avaliacao]:
    return {
        c: dcf.avaliar(pj.aplicar_cenario(base, deltas[c], c), dados, wacc=wacc, ronic=ronic)
        for c in cenarios
    }


def pesos(
    parametros: ParametrosPerfil, cenarios: tuple[pj.NomeCenario, ...]
) -> dict[pj.NomeCenario, float]:
    """Pesos do perfil com os três cenários; um cenário só tem peso 1."""
    if len(cenarios) == 1:
        return {cenarios[0]: 1.0}
    if set(cenarios) != set(pj.CENARIOS):
        raise ErroModelo(f"Ponderação exige os três cenários ou um só, não {cenarios}.")
    return {
        "pessimista": parametros.peso_pessimista,
        "base": parametros.peso_base,
        "otimista": parametros.peso_otimista,
    }


def ponderar(valores: Mapping[pj.NomeCenario, float], p: Mapping[pj.NomeCenario, float]) -> float:
    return sum(p[c] * valores[c] for c in p)


def taxa_implicita(
    valor_em: Callable[[float], float], alvo: float, *, minimo: float, maximo: float = TAXA_MAXIMA
) -> float | None:
    """Taxa em [minimo, maximo] com `valor_em(taxa) = alvo`; `None` se não houver troca de sinal."""
    lo, hi = valor_em(minimo) - alvo, valor_em(maximo) - alvo
    if lo == 0:
        return minimo
    if lo * hi > 0:
        return None
    return float(brentq(lambda x: valor_em(x) - alvo, minimo, maximo, xtol=1e-7))


@dataclass(frozen=True)
class ResultadoCenarios:
    avaliacoes: dict[pj.NomeCenario, dcf.Avaliacao]
    pesos: dict[pj.NomeCenario, float]
    perfil: ParametrosPerfil
    preco: float  # preço de mercado (BRL) da classe avaliada
    hurdle: float
    valor_ponderado: float  # BRL por ação
    ke_implicito: float | None
    wacc_implicito: float | None

    @property
    def preco_maximo_compra(self) -> float:
        return self.valor_ponderado * (1 - self.perfil.margem_seguranca)

    @property
    def upside(self) -> float:
        """Valor ponderado / preço - 1."""
        return self.valor_ponderado / self.preco - 1

    @property
    def avisos(self) -> tuple[str, ...]:
        vistos: dict[str, None] = {}
        for c, av in self.avaliacoes.items():
            for a in av.avisos:
                vistos[f"{c}: {a}"] = None
        if self.ke_implicito is None:
            vistos["Ke implícito sem solução entre o g terminal e 100% a.a."] = None
        return tuple(vistos)


def analisar(
    base: pj.PremissasResolvidas,
    deltas: Mapping[pj.NomeCenario, pj.DeltaResolvido],
    dados: dcf.DadosAvaliacao,
    *,
    custo_capital: wc.CustoCapital,
    ronic: dcf.Ronic,
    perfil: ParametrosPerfil,
    preco: float,
    selic: float,
    cenarios: tuple[pj.NomeCenario, ...] = pj.CENARIOS,
) -> ResultadoCenarios:
    """Avalia os cenários, pondera pelo perfil e acha o Ke e o WACC implícitos no preço."""
    if preco <= 0:
        raise ErroModelo(f"Preço de mercado inválido: {preco}.")
    cc = custo_capital
    avaliacoes = avaliar_cenarios(base, deltas, dados, wacc=cc.wacc, ronic=ronic, cenarios=cenarios)
    p = pesos(perfil, cenarios)
    valor = ponderar({c: av.valor_por_acao for c, av in avaliacoes.items()}, p)

    def ponderado_com_wacc(taxa: float) -> float:
        por_cenario = avaliar_cenarios(
            base, deltas, dados, wacc=taxa, ronic=ronic, cenarios=cenarios
        )
        return ponderar({c: av.valor_por_acao for c, av in por_cenario.items()}, p)

    def wacc_do_ke(ke: float) -> float:
        return wc.wacc(ke, cc.kd.kd, cc.aliquota, cc.estrutura.peso_divida)

    g = base.g_terminal
    peso_e = cc.estrutura.peso_equity
    ke_minimo = (g - cc.kd_liquido * cc.estrutura.peso_divida) / peso_e + FOLGA_G / peso_e
    return ResultadoCenarios(
        avaliacoes=avaliacoes,
        pesos=p,
        perfil=perfil,
        preco=preco,
        hurdle=perfil.hurdle(selic),
        valor_ponderado=valor,
        ke_implicito=taxa_implicita(
            lambda ke: ponderado_com_wacc(wacc_do_ke(ke)), preco, minimo=ke_minimo
        ),
        wacc_implicito=taxa_implicita(ponderado_com_wacc, preco, minimo=g + FOLGA_G),
    )


def mensagem(r: ResultadoCenarios, ticker: str) -> str:
    """Comparação neutra com o preço máximo do perfil (sem recomendação de compra ou venda)."""
    posicao = "abaixo" if r.preco <= r.preco_maximo_compra else "acima"

    def reais(x: float) -> str:
        return f"R$ {x:,.2f}".translate(str.maketrans(",.", ".,"))

    return (
        f"Preço de mercado de {ticker}: {reais(r.preco)}; {posicao} do preço máximo de compra "
        f"para o perfil {r.perfil.perfil} ({reais(r.preco_maximo_compra)})."
    )
