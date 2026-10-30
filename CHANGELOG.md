# Changelog

## [Não lançado]

### Fase 4 — Perfil do investidor
- `perfil/questionario.py`: 10 perguntas de suitability (1 a 5 pontos cada) com vetos de horizonte
  menor que 2 anos e de "não aceito perdas"; `VERSAO_QUESTIONARIO`.
- `perfil/pontuacao.py`: soma de 10 a 50 em faixas conservador / moderado / arrojado; veto força
  conservador.
- `perfil/registro.py`: `perfil/perfil_investidor.json` no esquema da seção 8.3, validade de 12
  meses, leitura que recalcula a classificação e recusa arquivo adulterado ou de outra versão,
  `resolver_perfil` com override explícito (para o futuro `rodar --perfil`).
- `perfil/parametros.py` e `settings.yaml > perfil`: margem de segurança, pesos dos cenários,
  horizonte e hurdle (Selic + spread) por perfil, valores placeholder da seção 8.4; pesos devem
  somar 1.
- CLI: `valuation perfil [--mostrar] [--refazer]`.
- `guia.md` 1.2.

### Documentação
- `CONTRIBUTING.md`: ambiente, política de commits (`make lint tipos testes` antes de cada um,
  atômicos, formato `area: o quê`), tabela de qual documento atualizar em cada mudança, lista
  "Antes de concluir", testes e convenções.
- `docs/decisoes/README.md`: índice dos ADRs com as seções do `CLAUDE.md` que cada um altera,
  modelo e regra de substituição.
- `README.md`: mapa da documentação, comandos reunidos, estado atual por fase e resumo das decisões
  que divergem do `CLAUDE.md`.
- `CLAUDE.md`: regras 9, 11 e 12 (testes antes do commit, ADR vence o texto, lista de conclusão),
  notas do ADR 0002 sobre a moeda da Vale (seções 2, 7.4 e 16), estrutura de pastas com
  `CLAUDE.md`, `CONTRIBUTING.md` e `guia.md`, e ✅ nas Fases 0 a 3.

### Fase 2 — Padronização contábil e QA
- `config/mapeamento_contas.yaml`: plano de contas não financeiro (DRE, DFC/DVA, BPA, BPP) com
  regras por código, prefixo, exclusão e regex sem acento; 18 contas críticas.
- `contabil/padronizacao.py`: um documento por demonstração e período (o mais recente, inclusive
  `PENÚLTIMO`), regras em ordem por período, soma das contas de nível mais alto;
  `contas_padronizadas.parquet` por companhia; relatório de cobertura.
- `contabil/periodos.py`: visões anual, acumulado no ano, trimestral (por diferença de YTD) e LTM.
- `contabil/moeda.py`: detecção da moeda (erro se mudar entre períodos) e conversão final para BRL.
- `contabil/nao_financeiras.py`: EBITDA, EBIT ajustado, NOPAT, capex, capital de giro, FCFF,
  dívida financeira × arrendamento, dívida líquida, ROIC; ajustes IFRS 16, coligadas e não
  recorrentes.
- `contabil/qa.py`: balanço, subcontas, identidades da DRE, LL atribuído, D&A ausente, fontes
  alternativas divergentes, saltos, anos faltantes, contas críticas e contas relevantes não mapeadas;
  `qa_{TICKER}.json`.
- CLI: `valuation qa TICKER` (sai com 1 se houver erro), `valuation historico TICKER [--anos N]
  [--trimestral]`, `valuation cobertura --tickers|--tudo`.
- `tests/test_golden.py`: os 94 valores de `tests/golden/referencias.yaml` contra o pipeline (83
  conferem; 11 pulados por definição própria da companhia ou período ainda fora da CVM).
- Pilotos: cobertura de 100% das contas críticas em 11 exercícios e QA sem erros.
- `docs/fontes.md` com o plano de contas validado; ADR 0005; `guia.md` 1.1.

### Fase 3 — Preços e macro via API, com validação cruzada
- `data/validacao.py`: compara duas fontes (`ok` / `divergente` / `sem_validacao` / `manual`); a
  principal vence, divergência vira aviso, nenhuma fonte é erro. Tolerâncias em
  `settings.yaml > validacao_cruzada`.
- `data/macro.py`: Selic (SGS 432 × 11), IPCA 12m (SGS 13522 × 433), dólar (SGS 1 × `BRL=X`),
  Rf em BRL (NTN-F × NTN-B + Focus), Focus de IPCA. Cache em `data/raw/macro/`.
- `data/precos.py`: `PrecosProvider` com `YFinanceProvider` (cache em parquet, retry, cópia vencida
  se falhar) e `BrapiProvider` (token opcional em `BRAPI_TOKEN`); preço validado; market cap por
  espécie sem tesouraria.
- CLI: `valuation mercado TICKER [--data-base] [--forcar]`.
- `docs/fontes.md` com as APIs validadas; ADR 0004.

### Conciliação com documentos das companhias
- `tests/golden/referencias.yaml`: valores de Petrobras, Vale e WEG conferidos contra releases,
  relatório da administração e composição acionária, todos batendo com a CVM.
- `referencias/`: documentos das companhias organizados por ticker (fora do git, com índice).
- `docs/fontes.md`: códigos de conta que mudam entre trimestres, arrendamentos fora de empréstimos
  (WEG) e significado variável da quantidade de ações na composição do capital (Vale).

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
