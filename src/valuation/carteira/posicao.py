"""Posição, preço médio e resultado da carteira (ADR 0020, item 5; Etapa C2).

Funções puras, sem I/O nem relógio: a `data_base` e as cotações vêm de quem chama. Tudo em
unidades da moeda (R$), não em milhares.

Regras por tipo de transação (reproduzidas em ordem cronológica, `transacoes.ordenar`):

- `compra`: soma `valor + taxas` ao custo da posição e as ações à quantidade (preço médio =
  custo / quantidade, ponderado, taxas incluídas).
- `venda`: baixa o custo pelo preço médio vigente (o preço médio **não muda**); o resultado
  realizado é `valor - taxas - custo baixado`.
- `desdobramento` e `agrupamento`: mudam a quantidade pelo fator e deixam o custo intacto, então o
  preço médio se ajusta sozinho.
- `bonificacao`: ações a custo zero; o custo da posição não muda e o preço médio cai.
- `provento`: soma `valor - taxas` (retenções) aos proventos recebidos; não mexe na posição.

Resultado total = patrimônio + vendas líquidas + proventos - compras (ADR 0020). Equivale a
realizado + não realizado + proventos, e é conferido nos testes.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from valuation.carteira.transacoes import (
    TOLERANCIA_QUANTIDADE,
    TipoTransacao,
    Transacao,
    aplicar_quantidade,
    ordenar,
)

# Cotação com mais dias que isto antes da data-base é avisada como defasada (feriados e fins de
# semana somam até 4 dias sem pregão).
TOLERANCIA_DIAS_DEFASAGEM = 5


@dataclass(frozen=True)
class Posicao:
    """Estado de um ticker na data-base (acumulado desde a primeira transação)."""

    ticker: str
    quantidade: float
    custo: float  # custo da posição atual (ações em carteira), taxas incluídas
    compras: float  # total pago em compras (valor + taxas) desde sempre
    vendas: float  # total recebido em vendas, líquido de taxas
    proventos: float  # proventos recebidos, líquidos de retenções
    realizado: float  # vendas líquidas - custo das ações vendidas

    @property
    def preco_medio(self) -> float | None:
        return self.custo / self.quantidade if self.quantidade > 0 else None

    @property
    def encerrada(self) -> bool:
        return self.quantidade <= 0


@dataclass(frozen=True)
class Preco:
    """Fechamento usado para avaliar a posição."""

    valor: float
    data: dt.date


@dataclass(frozen=True)
class LinhaCarteira:
    posicao: Posicao
    preco: Preco | None  # None: ticker aberto sem cotação (ou posição encerrada)

    @property
    def patrimonio(self) -> float | None:
        if self.posicao.encerrada:
            return 0.0
        return None if self.preco is None else self.posicao.quantidade * self.preco.valor

    @property
    def nao_realizado(self) -> float | None:
        if self.patrimonio is None:
            return None
        return self.patrimonio - self.posicao.custo

    @property
    def resultado(self) -> float | None:
        """Resultado total do ticker: patrimônio + vendas + proventos - compras."""
        if self.patrimonio is None:
            return None
        p = self.posicao
        return self.patrimonio + p.vendas + p.proventos - p.compras

    @property
    def resultado_pct(self) -> float | None:
        r = self.resultado
        if r is None or self.posicao.compras <= 0:
            return None
        return r / self.posicao.compras


@dataclass(frozen=True)
class ResumoCarteira:
    linhas: tuple[LinhaCarteira, ...]
    data_base: dt.date
    patrimonio: float
    custo: float  # custo das posições abertas
    compras: float
    vendas: float
    proventos: float
    resultado: float
    resultado_pct: float | None
    completo: bool  # False se algum ticker aberto ficou sem cotação (totais parciais)
    avisos: tuple[str, ...]


def calcular_posicoes(transacoes: Sequence[Transacao], data_base: dt.date) -> dict[str, Posicao]:
    """Posição de cada ticker na `data_base` (transações posteriores são ignoradas).

    Presume o histórico já validado (`validar_historico`): uma venda acima da posição ou um evento
    sem posição aqui seria um erro de programação, não de dado.
    """
    qtd: dict[str, float] = {}
    custo: dict[str, float] = {}
    compras: dict[str, float] = {}
    vendas: dict[str, float] = {}
    proventos: dict[str, float] = {}
    realizado: dict[str, float] = {}
    for i in ordenar(transacoes):
        t = transacoes[i]
        if t.data > data_base:
            continue
        k = t.ticker
        q = qtd.get(k, 0.0)
        c = custo.get(k, 0.0)
        if t.tipo is TipoTransacao.COMPRA:
            pago = t.valor + t.taxas
            c += pago
            compras[k] = compras.get(k, 0.0) + pago
        elif t.tipo is TipoTransacao.VENDA:
            if q <= 0 or t.quantidade > q + TOLERANCIA_QUANTIDADE:
                raise ValueError(f"venda de {t.ticker} acima da posição em {t.data}")
            baixa = c * (t.quantidade / q)
            liquido = t.valor - t.taxas
            c -= baixa
            vendas[k] = vendas.get(k, 0.0) + liquido
            realizado[k] = realizado.get(k, 0.0) + liquido - baixa
        elif t.tipo is TipoTransacao.PROVENTO:
            proventos[k] = proventos.get(k, 0.0) + t.valor - t.taxas
        novo = aplicar_quantidade(q, t)
        if abs(novo) <= TOLERANCIA_QUANTIDADE:
            novo, c = 0.0, 0.0  # posição zerada: sem resíduo de arredondamento no custo
        qtd[k], custo[k] = novo, c
        compras.setdefault(k, 0.0)
    return {
        k: Posicao(
            k,
            qtd[k],
            custo[k],
            compras[k],
            vendas.get(k, 0.0),
            proventos.get(k, 0.0),
            realizado.get(k, 0.0),
        )
        for k in sorted(qtd)
    }


def avaliar(
    posicoes: Mapping[str, Posicao],
    precos: Mapping[str, Preco],
    data_base: dt.date,
    avisos: Sequence[str] = (),
) -> ResumoCarteira:
    """Patrimônio e resultado com o fechamento de cada ticker (`precos`) na `data_base`.

    Ticker aberto sem cotação fica sem patrimônio e sem resultado, entra num aviso e os totais
    passam a `completo=False` (somam só o que tem cotação). Cotação mais de
    `TOLERANCIA_DIAS_DEFASAGEM` dias antes da data-base também gera aviso.
    """
    linhas = tuple(
        LinhaCarteira(p, None if p.encerrada else precos.get(p.ticker)) for p in posicoes.values()
    )
    notas = list(avisos)
    sem_preco = [ln.posicao.ticker for ln in linhas if ln.patrimonio is None]
    if sem_preco:
        notas.append(
            f"sem cotação para {', '.join(sem_preco)}: totais parciais, papéis ficaram de fora"
        )
    for ln in linhas:
        if ln.preco is not None and (data_base - ln.preco.data).days > TOLERANCIA_DIAS_DEFASAGEM:
            notas.append(
                f"cotação de {ln.posicao.ticker} defasada: {ln.preco.data.isoformat()} "
                f"({(data_base - ln.preco.data).days} dias antes de {data_base.isoformat()})"
            )
    avaliadas = [ln for ln in linhas if ln.resultado is not None]
    patrimonio = sum(ln.patrimonio or 0.0 for ln in avaliadas)
    compras = sum(ln.posicao.compras for ln in avaliadas)
    resultado = sum(ln.resultado or 0.0 for ln in avaliadas)
    return ResumoCarteira(
        linhas=linhas,
        data_base=data_base,
        patrimonio=patrimonio,
        custo=sum(ln.posicao.custo for ln in avaliadas),
        compras=compras,
        vendas=sum(ln.posicao.vendas for ln in avaliadas),
        proventos=sum(ln.posicao.proventos for ln in avaliadas),
        resultado=resultado,
        resultado_pct=resultado / compras if compras > 0 else None,
        completo=not sem_preco,
        avisos=tuple(notas),
    )
