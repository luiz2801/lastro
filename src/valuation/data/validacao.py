"""Validação cruzada de um dado obtido em duas fontes independentes.

A fonte principal sempre vence; a alternativa só confere. Divergência além da tolerância não
interrompe a execução, mas fica registrada (e aparece nos avisos da saída). Se só uma fonte
responder, o valor é usado marcado como `sem_validacao`; se nenhuma responder, é erro.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

Status = Literal["ok", "divergente", "sem_validacao", "manual"]


class ErroDadosExternos(Exception):
    """Nenhuma fonte devolveu o dado, ou o dado recebido é inválido."""


@dataclass(frozen=True)
class Leitura:
    valor: float
    fonte: str
    data: dt.date | None = None


@dataclass(frozen=True)
class Validado:
    nome: str
    valor: float
    fonte: str
    data: dt.date | None
    status: Status
    fonte_alt: str | None = None
    valor_alt: float | None = None
    divergencia: float | None = None
    tolerancia: float | None = None
    relativa: bool = False

    @property
    def aviso(self) -> str | None:
        if self.status == "divergente":
            unidade = "relativa" if self.relativa else "absoluta"
            return (
                f"{self.nome}: {self.fonte}={self.valor:.6g} e {self.fonte_alt}="
                f"{self.valor_alt:.6g} divergem ({unidade} {self.divergencia:.4g} > "
                f"{self.tolerancia:.4g}); usando {self.fonte}"
            )
        if self.status == "sem_validacao":
            return f"{self.nome}: sem segunda fonte para validar ({self.fonte})"
        return None


def manual(nome: str, valor: float) -> Validado:
    return Validado(
        nome=nome, valor=valor, fonte="manual (settings.yaml)", data=None, status="manual"
    )


def cruzar(
    nome: str,
    principal: Leitura | None,
    alternativa: Leitura | None,
    *,
    tolerancia: float,
    relativa: bool = False,
) -> Validado:
    """Compara as duas leituras. `relativa=True` mede |a-b|/|a|; senão, |a-b| (em unidades)."""
    if principal is None and alternativa is None:
        raise ErroDadosExternos(f"{nome}: nenhuma fonte devolveu o dado")
    if principal is None or alternativa is None:
        usada = principal or alternativa
        assert usada is not None
        logger.warning("%s: apenas %s respondeu; sem validação cruzada", nome, usada.fonte)
        return Validado(nome, usada.valor, usada.fonte, usada.data, "sem_validacao")

    diferenca = abs(principal.valor - alternativa.valor)
    divergencia = diferenca / abs(principal.valor) if relativa else diferenca
    status: Status = "ok" if divergencia <= tolerancia else "divergente"
    resultado = Validado(
        nome=nome,
        valor=principal.valor,
        fonte=principal.fonte,
        data=principal.data,
        status=status,
        fonte_alt=alternativa.fonte,
        valor_alt=alternativa.valor,
        divergencia=divergencia,
        tolerancia=tolerancia,
        relativa=relativa,
    )
    if resultado.aviso:
        logger.warning(resultado.aviso)
    return resultado
