# Changelog

## [Não lançado]

### Fase 1 — Cadastro e coleta CVM
- `data/http.py`: download com cache em `data/raw/`, `.meta.json` (URL, datas, sha256,
  `Last-Modified`), TTL, revalidação com `If-Modified-Since`, retry e uso de cópia vencida se a
  rede falhar.
- `data/cvm.py`: leitura de DFP/ITR (todas as demonstrações, consolidadas e individuais) e da
  composição do capital; escala `MIL` aplicada na ingestão; maior `VERSAO` por documento; um
  parquet por companhia em `data/processed/cvm/{cd_cvm}/`.
- `data/cadastro.py`: ticker ↔ CNPJ ↔ `CD_CVM` via cadastro CVM + FCA, classificação
  financeira/não financeira pelo setor, `config/cadastro_manual.csv` para holdings e escala.
- Correção da escala da quantidade de ações (ADR 0003).
- CLI: `valuation cadastro buscar TEXTO`, `valuation atualizar --tickers|--tudo [--forcar]`.
- `make atualizar` usa `TICKERS` (padrão: os três pilotos).
- `docs/fontes.md` com o formato real das fontes; ADR 0002 (Vale em BRL) e 0003.

### Fase 0 — Fundação
- Estrutura do repositório, `pyproject.toml` (uv, Python 3.12), ruff, mypy (strict), pytest.
- `Makefile` com `setup`, `lint`, `formatar`, `tipos`, `testes`, `cobertura`, `atualizar`, `rodar`.
- `config/settings.yaml` com valores placeholder e validação pydantic (`valuation.config`).
- CLI `valuation versao`.
- `docs/fontes.md` e ADRs iniciais.
