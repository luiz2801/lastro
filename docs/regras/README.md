# Regras Modulares por Camada

Orientações e princípios inegociáveis para agentes de IA e desenvolvedores que atuam no repositório com contexto delimitado por subsistema.

Cada camada do pipeline possui restrições estritas para garantir que cálculos sejam puros, dados externos sejam fidedignos e auditáveis, demonstrações financeiras reflitam os padrões contábeis adequados e a suíte de testes permaneça isolada e determinística.

## Índice

| Documento | Escopo e Subsistemas | Principais Diretrizes |
|---|---|---|
| [`REGRAS_DADOS.md`](REGRAS_DADOS.md) | `src/data/*.py`, `config/settings.yaml`, `config/cadastro_manual.csv`, `config/universo_ibovespa.csv`, `docs/fontes.md` | Adaptadores isolados, zero dados inventados, fontes gratuitas (CVM/BCB/Yahoo/brapi), cache com metadados/TTL, normalização de escala e sufixos |
| [`REGRAS_CONTABIL.md`](REGRAS_CONTABIL.md) | `src/contabil/*.py`, `config/mapeamento_contas.yaml`, `config/setores.yaml`, `config/empresas/*.yaml` | Separação estrita não financeiras vs financeiras, plano de contas declarativo, IFRS 16, demonstrações consolidadas, QA contábil e LTM |
| [`REGRAS_MODELOS.md`](REGRAS_MODELOS.md) | `src/projecao/*.py`, `src/custo_capital/*.py`, `src/modelos/*.py`, `src/analise/*.py`, `src/perfil/*.py` | Funções estritamente puras (sem I/O e sem `datetime.now()`), separação dados ➔ premissas ➔ cálculo, modelos por setor (FCFF/WACC vs DDM/Ke), teto de $g$ e sanidade |
| [`REGRAS_TESTES.md`](REGRAS_TESTES.md) | `tests/*.py`, `tests/fixtures/`, `tests/golden/`, `pyproject.toml`, `Makefile` | Zero acesso à rede em testes, dados sintéticos (`tests/sintetico.py`), governança rígida de golden tests, `make lint tipos testes` obrigatório |

## Quando Consultar

- **Antes de modificar código em uma camada específica**: consulte o documento de regras daquela camada, além do [`guia.md`](../../guia.md) e do [`docs/diagrama_atividades.md`](../diagrama_atividades.md).
- **Para novos agentes ou subagentes de IA**: injete ou referencie o arquivo de regras correspondente à tarefa em vez de carregar a especificação inteira.

