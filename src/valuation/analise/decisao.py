"""Preço teto de Bazin e recomendação (Etapa 5 do backlog, ADR 0025).

Preço teto de Bazin, informativo ao lado do preço máximo de compra do perfil:

    dividendo por ação = média dos dividendos pagos (DFC: dividendos e JCP aos acionistas da
                         controladora) dos últimos `anos` exercícios x câmbio / ações atuais
    preço teto Bazin   = dividendo por ação / yield mínimo

Recomendação, sobre a leitura pelo perfil (seção 8.4 do CLAUDE.md):

- compra: preço <= preço máximo de compra **e** Ke implícito >= hurdle;
- venda: preço > valor justo ponderado;
- manter: o resto, inclusive Ke implícito sem solução.

Confiança baixa (erro de QA, VT/EV acima do alerta, menos pares que o mínimo, R2 do beta abaixo do
mínimo) rebaixa a compra para manter; venda e manter não mudam. Funções puras, sem I/O.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, cast

import pandas as pd

from valuation.modelos import ErroModelo

Sinal = Literal["compra", "manter", "venda"]
Confianca = Literal["alta", "baixa"]


@dataclass(frozen=True)
class TetoBazin:
    """`valor` e `dividendo_por_acao` em BRL por ação; `None` sem dividendo médio positivo."""

    valor: float | None
    dividendo_por_acao: float | None
    exercicios: tuple[int, ...]  # exercícios com dado que entraram na média
    yield_minimo: float
    avisos: tuple[str, ...]


def _ano(indice: object) -> int:
    """Ano do índice: inteiro ou data de fim do exercício."""
    return int(cast(int, getattr(indice, "year", indice)))


def teto_bazin(
    dividendos: pd.Series,
    *,
    anos: int,
    acoes: float,
    cambio: float,
    yield_minimo: float,
) -> TetoBazin:
    """Teto de Bazin pela média dos dividendos pagos nos últimos `anos` exercícios.

    `dividendos`: um valor por exercício encerrado (índice = ano ou data de fim), positivo = saída
    de caixa, na moeda de reporte. A janela termina no exercício mais recente da série; ano da
    janela sem dado (sem DFP ou NaN) fica fora da média, com aviso.
    """
    if anos < 1:
        raise ErroModelo(f"Janela do teto de Bazin inválida: {anos} exercícios.")
    if yield_minimo <= 0:
        raise ErroModelo(f"Yield mínimo do teto de Bazin inválido: {yield_minimo}.")
    if acoes <= 0:
        raise ErroModelo(f"Quantidade de ações em circulação inválida: {acoes}.")
    por_ano = pd.Series(dividendos.to_numpy(dtype=float), index=[_ano(i) for i in dividendos.index])
    por_ano = por_ano[~por_ano.index.duplicated(keep="last")].sort_index()
    if por_ano.empty:
        return TetoBazin(None, None, (), yield_minimo, ("Teto de Bazin sem histórico anual.",))
    ultimo = int(por_ano.index.max())
    janela = list(range(ultimo - anos + 1, ultimo + 1))
    validos = por_ano.reindex(janela).dropna()
    avisos: list[str] = []
    if len(validos) < anos:
        faltam = [a for a in janela if a not in validos.index]
        avisos.append(
            f"Teto de Bazin com {len(validos)} de {anos} exercícios ({janela[0]} a {ultimo}); "
            f"sem dado em {', '.join(map(str, faltam))}."
        )
    exercicios = tuple(int(a) for a in validos.index)
    media = float(validos.mean()) if len(validos) else math.nan
    if not media > 0:
        avisos.append(f"Teto de Bazin indefinido: sem dividendos pagos de {janela[0]} a {ultimo}.")
        return TetoBazin(None, None, exercicios, yield_minimo, tuple(avisos))
    por_acao = media * cambio / acoes
    return TetoBazin(por_acao / yield_minimo, por_acao, exercicios, yield_minimo, tuple(avisos))


def motivos_baixa_confianca(
    *,
    erros_qa: int,
    vt_sobre_valor: float,
    alerta_vt: float,
    n_pares: int | None,
    min_pares: int,
    r2_beta: float | None,
    min_r2: float,
) -> tuple[str, ...]:
    """Motivos que tornam a confiança baixa; vazio = confiança alta.

    `vt_sobre_valor`: VT/EV (DCF) ou VT/valor (DDM) do cenário de referência; NaN = valor <= 0.
    `n_pares`: pares medidos (`None` = nenhum). `r2_beta`: só o da regressão (`None` nos demais).
    """
    motivos: list[str] = []
    if erros_qa > 0:
        motivos.append(f"QA com {erros_qa} erro(s)")
    if math.isnan(vt_sobre_valor):
        motivos.append("VT sobre o valor indefinido (valor <= 0)")
    elif vt_sobre_valor > alerta_vt:
        motivos.append(f"VT de {vt_sobre_valor:.0%} do valor, acima do alerta de {alerta_vt:.0%}")
    if not n_pares:
        motivos.append("sem pares medidos")
    elif n_pares < min_pares:
        motivos.append(f"{n_pares} par(es) válido(s), abaixo do mínimo de {min_pares}")
    if r2_beta is not None and r2_beta < min_r2:
        r2, minimo = (f"{x:.2f}".replace(".", ",") for x in (r2_beta, min_r2))
        motivos.append(f"R² do beta de {r2}, abaixo de {minimo}")
    return tuple(motivos)


@dataclass(frozen=True)
class Recomendacao:
    sinal: Sinal  # o que vale, já com o rebaixamento
    sinal_modelo: Sinal  # pela regra de preço e hurdle, antes da confiança
    confianca: Confianca
    motivos_confianca: tuple[str, ...]
    ke_atende_hurdle: bool | None  # None = Ke implícito sem solução

    @property
    def rebaixada(self) -> bool:
        return self.sinal != self.sinal_modelo


def recomendar(
    *,
    preco: float,
    valor_ponderado: float,
    preco_maximo_compra: float,
    ke_implicito: float | None,
    hurdle: float,
    motivos_confianca: Sequence[str] = (),
) -> Recomendacao:
    """Compra, manter ou venda pela regra do módulo; confiança baixa rebaixa a compra."""
    if not preco > 0:
        raise ErroModelo(f"Preço de mercado inválido: {preco}.")
    atende = None if ke_implicito is None else ke_implicito >= hurdle
    sinal: Sinal
    if preco > valor_ponderado:
        sinal = "venda"
    elif preco <= preco_maximo_compra and atende:
        sinal = "compra"
    else:
        sinal = "manter"
    motivos = tuple(motivos_confianca)
    confianca: Confianca = "baixa" if motivos else "alta"
    final: Sinal = "manter" if sinal == "compra" and motivos else sinal
    return Recomendacao(final, sinal, confianca, motivos, atende)
