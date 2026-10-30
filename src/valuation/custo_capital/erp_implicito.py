"""ERP implícito do Ibovespa em BRL (ADR 0018).

O índice vale o valor presente dos dividendos agregados de seus componentes:

    P0 = soma_{t=1..N} FC_t / (1 + ke)^t  +  [FC_N x (1 + g) / (ke - g)] / (1 + ke)^N

com `FC_t = FC_0 x produto(1 + g_s)`. Nos N anos explícitos o crescimento é o nominal do Focus
`(1 + PIB real) x (1 + IPCA) - 1`; onde o Focus não chega, e na perpetuidade, vale `g` (a média
histórica do fluxo, escolhida por quem chama). `ERP = ke - Rf`, com a Rf em BRL do próprio Ke das
empresas (sem somar risco-país). Função pura: sem rede, sem I/O, sem relógio.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from scipy.optimize import brentq

from valuation.custo_capital import ErroCustoCapital

FOLGA_G = 1e-6  # o limite inferior da busca fica logo acima de g (a perpetuidade explode em ke = g)
KE_MAXIMO = 2.0  # 200% a.a.: acima disso não há solução plausível
ERP_AVISO = (0.02, 0.10)  # fora desta faixa o resultado é plausível mas suspeito (aviso)
ERP_ERRO = (0.0, 0.15)  # fora desta faixa não se usa (erro; use erp.fonte = manual)
COBERTURA_MINIMA = 0.80  # fração do universo medida abaixo da qual há aviso
FAIXA_LARGA = 0.02  # amplitude da faixa de ERP acima da qual há aviso


@dataclass(frozen=True)
class ErpImplicito:
    """Resultado para um `g` perpétuo: taxa de retorno do acionista e prêmio sobre a Rf."""

    ke: float
    erp: float
    rf: float
    g_perpetuo: float
    crescimentos: tuple[float, ...]


@dataclass(frozen=True)
class FaixaErp:
    central: ErpImplicito
    inferior: ErpImplicito  # g perpétuo menor
    superior: ErpImplicito  # g perpétuo maior
    avisos: tuple[str, ...]
    erro: str | None = None  # central fora de ERP_ERRO: mostrar os números, mas não usar


def ultimo_ano_comum(series: Sequence[Mapping[int, float]], minimo: float = 0.5) -> int:
    """Último ano com fluxo positivo em pelo menos `minimo` das séries (exercício já divulgado)."""
    contagem: dict[int, int] = {}
    for serie in series:
        for ano, valor in serie.items():
            if valor > 0:
                contagem[ano] = contagem.get(ano, 0) + 1
    elegiveis = [a for a, n in contagem.items() if n >= minimo * len(series)]
    if not elegiveis:
        raise ErroCustoCapital("Dividendos históricos insuficientes para o ERP implícito.")
    return max(elegiveis)


def cagr_agregado(
    series: Sequence[Mapping[int, float]], ano_final: int, anos: int
) -> tuple[float, int]:
    """CAGR da soma dos fluxos entre `ano_final - anos` e `ano_final`, devolvido com o nº de séries.

    Só entram as séries com fluxo positivo nas duas pontas (a soma compara o mesmo conjunto).
    """
    ano_inicial = ano_final - anos
    pares = [
        (s[ano_inicial], s[ano_final])
        for s in series
        if s.get(ano_inicial, 0.0) > 0 and s.get(ano_final, 0.0) > 0
    ]
    if not pares:
        raise ErroCustoCapital(
            f"Nenhuma série com dividendos positivos em {ano_inicial} e {ano_final}."
        )
    inicio = sum(a for a, _ in pares)
    fim = sum(b for _, b in pares)
    return (fim / inicio) ** (1 / anos) - 1, len(pares)


def crescimento_nominal(pib_real: float, ipca: float) -> float:
    """Crescimento nominal a partir do PIB real e da inflação (Fisher)."""
    return (1 + pib_real) * (1 + ipca) - 1


def trajetoria(
    ano_inicial: int,
    anos: int,
    pib_real: Mapping[int, float],
    ipca: Mapping[int, float],
    g_perpetuo: float,
) -> tuple[float, ...]:
    """Crescimento de cada ano explícito: Focus nominal onde há PIB e IPCA; senão `g_perpetuo`.

    O ano 1 é o `ano_inicial` (o da data-base); sem convergência: o degrau vai direto de uma
    fonte à outra (ADR 0018).
    """
    return tuple(
        crescimento_nominal(pib_real[a], ipca[a]) if a in pib_real and a in ipca else g_perpetuo
        for a in range(ano_inicial, ano_inicial + anos)
    )


def valor_presente(
    ke: float, fluxo_base: float, crescimentos: Sequence[float], g_perpetuo: float
) -> float:
    """Valor presente dos fluxos explícitos e da perpetuidade (fluxos no fim de cada ano)."""
    if ke <= g_perpetuo:
        raise ErroCustoCapital(f"ke de {ke:.2%} não é maior que o g perpétuo de {g_perpetuo:.2%}.")
    fluxo = fluxo_base
    total = 0.0
    for t, g in enumerate(crescimentos, start=1):
        fluxo *= 1 + g
        total += fluxo / (1 + ke) ** t
    n = len(crescimentos)
    terminal = fluxo * (1 + g_perpetuo) / (ke - g_perpetuo)
    return total + terminal / (1 + ke) ** n


def resolver(
    valor_indice: float,
    fluxo_base: float,
    crescimentos: Sequence[float],
    g_perpetuo: float,
    rf: float,
) -> ErpImplicito:
    """`ke` que iguala o valor presente ao valor do índice; `ERP = ke - Rf`."""
    if valor_indice <= 0 or fluxo_base <= 0:
        raise ErroCustoCapital(
            "ERP implícito exige valor de mercado e dividendos agregados positivos "
            f"(valor {valor_indice:,.0f}; dividendos {fluxo_base:,.0f})."
        )
    minimo = g_perpetuo + FOLGA_G

    def erro(ke: float) -> float:
        return valor_presente(ke, fluxo_base, crescimentos, g_perpetuo) - valor_indice

    if erro(minimo) < 0 or erro(KE_MAXIMO) > 0:
        raise ErroCustoCapital(
            f"ERP implícito sem solução com ke entre {minimo:.2%} e {KE_MAXIMO:.0%} "
            f"(g perpétuo de {g_perpetuo:.2%}); use custo_capital.erp.fonte = manual."
        )
    ke = float(brentq(erro, minimo, KE_MAXIMO, xtol=1e-10))
    return ErpImplicito(ke, ke - rf, rf, g_perpetuo, tuple(crescimentos))


def faixa(
    valor_indice: float,
    fluxo_base: float,
    *,
    ano_inicial: int,
    anos: int,
    pib_real: Mapping[int, float],
    ipca: Mapping[int, float],
    g_perpetuo: float,
    faixa_g: float,
    rf: float,
    cobertura: float = 1.0,
    recompras_ignoradas: bool = True,
) -> FaixaErp:
    """ERP central e limites com `g_perpetuo` ± `faixa_g` (piso 0), mais os avisos do ADR 0018.

    Central fora de `ERP_ERRO` não levanta: vai em `erro`, para quem chama mostrar os números.
    """

    def com_g(g: float) -> ErpImplicito:
        cresc = trajetoria(ano_inicial, anos, pib_real, ipca, g)
        return resolver(valor_indice, fluxo_base, cresc, g, rf)

    central = com_g(g_perpetuo)
    inferior = com_g(max(0.0, g_perpetuo - faixa_g))
    superior = com_g(g_perpetuo + faixa_g)

    avisos: list[str] = []
    erro = None
    if not (ERP_ERRO[0] <= central.erp <= ERP_ERRO[1]):
        erro = (
            f"ERP implícito de {central.erp:.2%} fora de [{ERP_ERRO[0]:.0%}, {ERP_ERRO[1]:.0%}] "
            f"(ke do mercado de {central.ke:.2%} contra Rf de {central.rf:.2%}); "
            "use custo_capital.erp.fonte = manual."
        )
    elif not (ERP_AVISO[0] <= central.erp <= ERP_AVISO[1]):
        avisos.append(
            f"ERP implícito de {central.erp:.2%} fora de [{ERP_AVISO[0]:.0%}, {ERP_AVISO[1]:.0%}]: "
            "confira os dividendos agregados e a Rf."
        )
    amplitude = superior.erp - inferior.erp
    if amplitude > FAIXA_LARGA:
        avisos.append(
            f"Faixa do ERP implícito larga ({amplitude * 100:.1f} p.p.): o resultado depende "
            "muito do crescimento perpétuo."
        )
    if cobertura < COBERTURA_MINIMA:
        avisos.append(
            f"ERP implícito medido em {cobertura:.0%} do universo (mínimo {COBERTURA_MINIMA:.0%})."
        )
    if recompras_ignoradas:
        avisos.append(
            "ERP implícito ignora recompras (fluxo subestimado): tende a ficar abaixo do real."
        )
    return FaixaErp(central, inferior, superior, tuple(avisos), erro)
