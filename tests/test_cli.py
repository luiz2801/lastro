from typer.testing import CliRunner

from valuation import __version__
from valuation.cli import app


def test_versao() -> None:
    resultado = CliRunner().invoke(app, ["versao"])
    assert resultado.exit_code == 0
    assert __version__ in resultado.stdout
