"""Atualização a pedido: executa os fluxos da CLI em outro processo e devolve o que eles imprimem.

Assim a GUI aciona exatamente o mesmo `atualizar` e `rodar` da linha de comando, com as mesmas
validações, e uma falha não derruba a tela.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

Comando = tuple[str, ...]


def comando(*argumentos: str) -> Comando:
    return (sys.executable, "-m", "valuation", *argumentos)


def baixar_dados(ticker: str) -> list[Comando]:
    """Demonstrações da CVM e séries de mercado: usado quando o ativo não tem nenhum cache."""
    return [comando("atualizar", "--tickers", ticker), comando("series", ticker)]


def baixar_series_grupo(tickers: Sequence[str], sem_demonstracoes: Sequence[str]) -> list[Comando]:
    """Séries de um grupo; quem não tem nem as demonstrações as baixa antes."""
    comandos = []
    if sem_demonstracoes:
        comandos.append(comando("atualizar", "--tickers", ",".join(sem_demonstracoes)))
    return [*comandos, comando("series-varios", *tickers)]


def rodar_valuation(ticker: str) -> list[Comando]:
    return [comando("rodar", ticker)]


def atualizar_ativo(ticker: str) -> list[Comando]:
    return [*baixar_dados(ticker), *rodar_valuation(ticker)]


def atualizar_favoritas(tickers: Sequence[str]) -> list[Comando]:
    return [*(comando("series", t) for t in tickers), comando("favoritos", "atualizar")]


@dataclass(frozen=True)
class Execucao:
    ok: bool
    saida: list[str] = field(default_factory=list)
    falhou_em: str | None = None  # o comando que falhou, em texto


def executar(
    comandos: Sequence[Comando], ao_ler: Callable[[str], None] = lambda _: None
) -> Execucao:
    """Roda em sequência e para no primeiro que falhar. `ao_ler` recebe cada linha ao vivo."""
    ambiente = {**os.environ, "NO_COLOR": "1", "COLUMNS": "120"}
    saida: list[str] = []
    for argumentos in comandos:
        rotulo = "valuation " + " ".join(argumentos[3:])
        try:
            with subprocess.Popen(
                argumentos,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=ambiente,
            ) as processo:
                assert processo.stdout is not None
                for linha in processo.stdout:
                    texto = linha.rstrip("\n")
                    saida.append(texto)
                    ao_ler(texto)
                codigo = processo.wait()
        except OSError as e:
            saida.append(f"Não foi possível iniciar {rotulo}: {e}")
            return Execucao(False, saida, rotulo)
        if codigo != 0:
            return Execucao(False, saida, rotulo)
    return Execucao(True, saida)
