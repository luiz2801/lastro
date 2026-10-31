"""Camada carteira pessoal (ADR 0020): transações, posição e alocação.

Fica no topo da cadeia, acima de `saida`; nenhuma camada inferior a importa.
"""


class ErroCarteira(ValueError):
    """Transação, arquivo de carteira ou histórico inválido."""

    def __init__(self, erros: str | list[str]) -> None:
        self.erros: tuple[str, ...] = (erros,) if isinstance(erros, str) else tuple(erros)
        super().__init__("\n".join(self.erros))
