UV ?= uv
TICKER ?= PETR4

.PHONY: setup lint formatar tipos testes cobertura atualizar rodar

setup:
	$(UV) sync

lint:
	$(UV) run ruff check src tests
	$(UV) run ruff format --check src tests

formatar:
	$(UV) run ruff check --fix src tests
	$(UV) run ruff format src tests

tipos:
	$(UV) run mypy

testes:
	$(UV) run pytest

cobertura:
	$(UV) run pytest --cov=valuation --cov-report=term-missing

atualizar:
	$(UV) run valuation atualizar --tudo

rodar:
	$(UV) run valuation rodar $(TICKER)
