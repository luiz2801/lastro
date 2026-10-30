"""Camada perfil."""

from typing import Literal

NomePerfil = Literal["conservador", "moderado", "arrojado"]


class ErroPerfil(Exception):
    """Perfil ausente, vencido, inválido ou com respostas inconsistentes."""
