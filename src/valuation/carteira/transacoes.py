"""Transações da carteira: esquema, validação de cada linha e do histórico (ADR 0020, item 3).

Funções puras, sem I/O. Convenções por tipo (unidades da moeda, não milhares):

- `compra` e `venda`: `quantidade` > 0 e `preco` > 0; `valor` = quantidade x preço, bruto, sem
  `taxas` (se informado, tem de bater com o produto, tolerância de R$ 0,01).
- `provento`: `quantidade` = ações com direito; `valor` bruto > 0 (ou quantidade x preço);
  `taxas` = retenções (IR do JCP), descontadas do valor.
- `desdobramento` e `agrupamento`: `quantidade` é o **fator** (> 1). Desdobramento: cada ação vira
  `fator` ações; agrupamento: `fator` ações viram uma. Sem preço, valor nem taxas.
- `bonificacao`: `quantidade` = ações recebidas (> 0), a custo zero. Sem preço, valor nem taxas.
"""

from __future__ import annotations

import datetime as dt
import math
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from valuation.carteira import ErroCarteira

TOLERANCIA_VALOR = 0.01
TOLERANCIA_QUANTIDADE = 1e-9
PADRAO_TICKER = re.compile(r"^[A-Z]{4}\d{1,2}$")


class TipoTransacao(StrEnum):
    COMPRA = "compra"
    VENDA = "venda"
    PROVENTO = "provento"
    AGRUPAMENTO = "agrupamento"
    DESDOBRAMENTO = "desdobramento"
    BONIFICACAO = "bonificacao"


EVENTOS = (TipoTransacao.AGRUPAMENTO, TipoTransacao.DESDOBRAMENTO, TipoTransacao.BONIFICACAO)


@dataclass(frozen=True)
class Transacao:
    data: dt.date
    ticker: str
    tipo: TipoTransacao
    quantidade: float
    preco: float | None
    valor: float
    taxas: float
    observacao: str


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.strip().lower()


def _tipo(texto: str | TipoTransacao) -> TipoTransacao:
    try:
        return TipoTransacao(_normalizar(str(texto)))
    except ValueError:
        validos = ", ".join(t.value for t in TipoTransacao)
        raise ErroCarteira(f"tipo desconhecido '{texto}' (use: {validos})") from None


def _finito(nome: str, valor: float | None) -> None:
    if valor is not None and not math.isfinite(valor):
        raise ErroCarteira(f"{nome} não é um número finito")


def _exigir_vazio(tipo: TipoTransacao, **campos: float | None) -> None:
    for nome, valor in campos.items():
        if valor not in (None, 0):
            raise ErroCarteira(f"{tipo.value} não leva {nome}")


def nova_transacao(
    data: dt.date,
    ticker: str,
    tipo: str | TipoTransacao,
    quantidade: float,
    preco: float | None = None,
    valor: float | None = None,
    taxas: float | None = None,
    observacao: str = "",
) -> Transacao:
    """Normaliza e valida uma linha; qualquer violação levanta `ErroCarteira`."""
    t = _tipo(tipo)
    papel = ticker.strip().upper()
    if not PADRAO_TICKER.match(papel):
        raise ErroCarteira(f"ticker inválido '{ticker}' (ex.: PETR4, BPAC11; sem sufixo F)")
    for nome, numero in (("quantidade", quantidade), ("preco", preco), ("valor", valor)):
        _finito(nome, numero)
    _finito("taxas", taxas)
    if taxas is not None and taxas < 0:
        raise ErroCarteira("taxas não pode ser negativa")
    taxa = taxas or 0.0
    obs = " ".join(observacao.split())

    if quantidade <= 0:
        raise ErroCarteira("quantidade deve ser maior que zero")
    if preco is not None and preco < 0:
        raise ErroCarteira("preco não pode ser negativo")
    if valor is not None and valor < 0:
        raise ErroCarteira("valor não pode ser negativo")

    if t in (TipoTransacao.COMPRA, TipoTransacao.VENDA):
        if preco is None or preco <= 0:
            raise ErroCarteira(f"{t.value} exige preco maior que zero")
        bruto = round(quantidade * preco, 6)
        if valor is not None and abs(valor - bruto) > TOLERANCIA_VALOR:
            raise ErroCarteira(f"valor {valor} difere de quantidade x preco ({bruto})")
        total = bruto
    elif t is TipoTransacao.PROVENTO:
        if valor is None:
            if preco is None:
                raise ErroCarteira("provento exige valor (ou quantidade e preco)")
            valor = round(quantidade * preco, 6)
        elif preco is not None and abs(valor - quantidade * preco) > TOLERANCIA_VALOR:
            raise ErroCarteira(f"valor {valor} difere de quantidade x preco")
        if valor <= 0:
            raise ErroCarteira("provento exige valor maior que zero")
        total = valor
    else:
        _exigir_vazio(t, preco=preco, valor=valor, taxas=taxas)
        if t is not TipoTransacao.BONIFICACAO and quantidade <= 1:
            raise ErroCarteira(f"{t.value}: o fator (quantidade) deve ser maior que 1")
        total = 0.0
    return Transacao(data, papel, t, quantidade, preco, total, taxa, obs)


def ordenar(transacoes: Sequence[Transacao]) -> list[int]:
    """Índices em ordem de reprodução: por data; no mesmo dia, a ordem do arquivo."""
    return sorted(range(len(transacoes)), key=lambda i: transacoes[i].data)


def aplicar_quantidade(posicao: float, t: Transacao) -> float:
    """Quantidade em carteira depois de `t` (proventos não a alteram)."""
    if t.tipo in (TipoTransacao.COMPRA, TipoTransacao.BONIFICACAO):
        return posicao + t.quantidade
    if t.tipo is TipoTransacao.VENDA:
        return posicao - t.quantidade
    if t.tipo is TipoTransacao.DESDOBRAMENTO:
        return posicao * t.quantidade
    if t.tipo is TipoTransacao.AGRUPAMENTO:
        return posicao / t.quantidade
    return posicao


def validar_historico(
    transacoes: Sequence[Transacao],
    rotulos: Sequence[str] | None = None,
    hoje: dt.date | None = None,
) -> None:
    """Reproduz a carteira em ordem cronológica e recusa o que não fecha.

    Erros: data futura (se `hoje`), venda acima da posição e evento corporativo sem posição.
    `rotulos[i]` identifica a transação `i` nas mensagens (ex.: "linha 7"). Reúne todos os erros.
    """
    nomes = rotulos or [f"transação {i + 1}" for i in range(len(transacoes))]
    erros: list[str] = []
    posicao: dict[str, float] = {}
    for i in ordenar(transacoes):
        t = transacoes[i]
        if hoje is not None and t.data > hoje:
            erros.append(f"{nomes[i]}: data {t.data.isoformat()} no futuro")
        atual = posicao.get(t.ticker, 0.0)
        if t.tipo is TipoTransacao.VENDA and t.quantidade > atual + TOLERANCIA_QUANTIDADE:
            erros.append(
                f"{nomes[i]}: venda de {t.quantidade:g} {t.ticker} em {t.data.isoformat()} acima "
                f"da posição ({atual:g}); no mesmo dia vale a ordem do arquivo"
            )
            continue
        if t.tipo in EVENTOS and atual <= 0:
            erros.append(f"{nomes[i]}: {t.tipo.value} de {t.ticker} sem posição em {t.data}")
            continue
        novo = aplicar_quantidade(atual, t)
        posicao[t.ticker] = 0.0 if abs(novo) <= TOLERANCIA_QUANTIDADE else novo
    if erros:
        raise ErroCarteira(erros)
