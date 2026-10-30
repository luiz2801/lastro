# ADR 0001 — Estrutura do repositório e ambiente

- **Data:** 2026-10-30
- **Status:** aceito

## Contexto

O guia (seção 5) mostra a raiz como `valuation/` e o documento-mestre como `PROJETO.md`.
O repositório já existia como `Lastro/` com o guia em `CLAUDE.md`. O sistema tem Python 3.14,
mas parte das dependências científicas (statsmodels, pyarrow, python-bcb) pode não ter wheels
para essa versão.

## Decisão

- A raiz do repositório é `Lastro/`. O pacote e o comando continuam se chamando `valuation`.
- O guia fica só em `CLAUDE.md`, sem cópia em `PROJETO.md`.
- Python fixado em 3.12 via `.python-version` (gerenciado pelo `uv`), com `requires-python >=3.11,<3.14`.
- Layout `src/` e mypy em modo strict.
