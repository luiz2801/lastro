"""`python -m valuation`: o mesmo comando `valuation`, para a GUI chamar os fluxos da CLI."""

from valuation.cli import app

if __name__ == "__main__":  # pragma: no cover
    app()
