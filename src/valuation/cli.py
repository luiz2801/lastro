"""Interface de linha de comando (`valuation`)."""

from __future__ import annotations

import logging
import platform

import typer
from rich.console import Console

from valuation import __version__

app = typer.Typer(
    help="Valuation de ações da B3. Uso pessoal e educacional; não é recomendação de investimento.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


@app.callback()
def principal(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log em nível DEBUG."),
) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@app.command()
def versao() -> None:
    """Mostra a versão do programa e do Python."""
    console.print(f"valuation {__version__} (Python {platform.python_version()})")


if __name__ == "__main__":  # pragma: no cover
    app()
