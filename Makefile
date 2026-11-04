UV ?= uv
TICKER ?= PETR4
TICKERS ?= PETR4,VALE3,WEGE3

.PHONY: setup lint formatar tipos testes cobertura atualizar rodar gui

setup:
	$(UV) sync --group gui

lint:
	$(UV) run ruff check src tests
	$(UV) run ruff format --check src tests

formatar:
	$(UV) run ruff check --fix src tests
	$(UV) run ruff format src tests

tipos:
	$(UV) run --group gui mypy

testes:
	$(UV) run --group gui pytest

cobertura:
	$(UV) run --group gui pytest --cov=valuation --cov-report=term-missing

atualizar:
	$(UV) run valuation atualizar --tickers $(TICKERS)

rodar:
	$(UV) run valuation rodar $(TICKER)

gui:
	$(UV) run --group gui valuation gui
