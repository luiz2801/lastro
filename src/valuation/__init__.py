"""Valuation de ações da B3. Uso pessoal e educacional; não é recomendação de investimento."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("valuation")
except PackageNotFoundError:  # pragma: no cover - execução sem instalação
    __version__ = "0.0.0"
