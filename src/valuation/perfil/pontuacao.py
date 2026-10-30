"""Pontuação e classificação das respostas do questionário (seção 8.2 do CLAUDE.md)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from valuation.perfil import ErroPerfil, NomePerfil
from valuation.perfil.questionario import QUESTIONARIO, Pergunta

# Limite superior (inclusivo) de cada faixa de pontuação.
LIMITE_CONSERVADOR = 24
LIMITE_MODERADO = 37


@dataclass(frozen=True)
class Classificacao:
    pontuacao: int
    perfil: NomePerfil
    vetos_aplicados: tuple[str, ...]


def perfil_da_pontuacao(pontuacao: int) -> NomePerfil:
    if pontuacao <= LIMITE_CONSERVADOR:
        return "conservador"
    if pontuacao <= LIMITE_MODERADO:
        return "moderado"
    return "arrojado"


def classificar(
    respostas: Mapping[str, int], questionario: tuple[Pergunta, ...] = QUESTIONARIO
) -> Classificacao:
    """Soma os pontos e aplica os vetos.

    `respostas` mapeia a chave da pergunta ao número da alternativa escolhida (1 = primeira).
    Exige resposta para todas as perguntas, e só para elas.
    """
    chaves = [p.chave for p in questionario]
    faltando = [c for c in chaves if c not in respostas]
    sobrando = sorted(set(respostas) - set(chaves))
    if faltando or sobrando:
        raise ErroPerfil(
            f"Respostas incompletas ou desconhecidas (faltando: {faltando}, sobrando: {sobrando})"
        )
    pontuacao = 0
    vetos: list[str] = []
    for pergunta in questionario:
        escolha, n = respostas[pergunta.chave], len(pergunta.alternativas)
        if not 1 <= escolha <= n:
            raise ErroPerfil(f"{pergunta.chave}: alternativa {escolha} fora de 1 a {n}")
        alternativa = pergunta.alternativas[escolha - 1]
        pontuacao += alternativa.pontos
        if alternativa.veto:
            vetos.append(alternativa.veto)
    perfil = "conservador" if vetos else perfil_da_pontuacao(pontuacao)
    return Classificacao(pontuacao, perfil, tuple(vetos))
