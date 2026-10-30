# valuation — Valuation de ações da B3

Ferramenta pessoal e educacional para avaliar empresas listadas na B3 (DCF, DDM e múltiplos)
a partir de dados gratuitos (CVM, BCB, Tesouro, yfinance, brapi). **Não constitui recomendação de
investimento.**

## Documentação

| Documento | Para quê |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Especificação completa: escopo, decisões, fórmulas, fontes, roadmap por fase e regras para o agente |
| [`guia.md`](guia.md) | Mapa do código como ele está hoje: módulos, contratos, parâmetros, testes e armadilhas. Leia antes de modificar |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Política de commits, que documento atualizar, testes e convenções |
| [`docs/decisoes/`](docs/decisoes/README.md) | ADRs: decisões que completam ou divergem do `CLAUDE.md`, com índice |
| [`docs/fontes.md`](docs/fontes.md) | O que foi confirmado em cada fonte real (URLs, arquivos, contas, séries SGS) |
| [`CHANGELOG.md`](CHANGELOG.md) | O que foi entregue em cada fase |
| [`referencias/README.md`](referencias/README.md) | Índice dos documentos das companhias usados na conciliação (os arquivos ficam fora do git) |

## Setup e comandos

Requer [`uv`](https://docs.astral.sh/uv/) (o Python 3.12 é baixado automaticamente). Nenhuma chave
de API é necessária.

```bash
make setup                                   # cria .venv e instala dependências
make lint tipos testes                       # ruff, mypy strict e pytest (sem rede)
make cobertura                               # testes com cobertura por linha

uv run valuation versao
uv run valuation cadastro buscar petrobras   # ticker, razão social ou CNPJ
make atualizar                               # = valuation atualizar --tickers PETR4,VALE3,WEGE3
uv run valuation qa PETR4                    # controles de qualidade; sai com 1 se houver erro
uv run valuation historico PETR4             # métricas anuais + LTM (R$ milhões)
uv run valuation historico PETR4 --trimestral
uv run valuation cobertura --tickers PETR4,VALE3,WEGE3
uv run valuation mercado PETR4               # preço, market cap, Ibovespa, dólar, Selic, IPCA, Rf
uv run valuation perfil                      # questionário de perfil (--mostrar, --refazer)
uv run valuation premissas sugerir PETR4     # sugestões × histórico e projeção base
uv run valuation premissas sugerir PETR4 --escrever   # regenera config/empresas/PETR4.yaml
uv run valuation wacc PETR4                 # beta, Ke, Kd e WACC; grava saida/PETR4/{data}/wacc.csv
```

`atualizar` precisa rodar antes de `qa`, `historico`, `cobertura`, `mercado` e `premissas`.
`make rodar` e os comandos `rodar` e `comparar` ainda não existem (Fases 6 a 9). Parâmetros e
efeitos de cada comando: seção 3 do [`guia.md`](guia.md).

Para validar o preço de qualquer ticker na brapi (sem token, só PETR4, VALE3, MGLU3 e ITUB4), crie
um token gratuito em brapi.dev e exporte `BRAPI_TOKEN`.

## Estrutura

- `src/valuation/`: código, em camadas `data` → `contabil` → `projecao` → `custo_capital` →
  `modelos` → `analise` → `saida` (as quatro últimas ainda vazias), mais `perfil`.
- `config/`: `settings.yaml` (parâmetros globais), `mapeamento_contas.yaml` (plano de contas
  padronizado), `cadastro_manual.csv` (holdings e escala de ações), `setores.yaml` e
  `empresas/{TICKER}.yaml` (ajustes e premissas de cada empresa).
- `docs/`: fontes validadas e ADRs.
- `tests/`: testes offline; `tests/golden/referencias.yaml` tem valores conferidos com documentos
  das companhias.
- `referencias/`: PDFs e planilhas das companhias (fora do git; só o índice é versionado).
- `data/`, `saida/`, `perfil/`: gerados localmente, fora do git.

## Estado atual

**Fases 0 a 6 concluídas** (seção 17 do `CLAUDE.md`). Próxima: Fase 7, DCF, ponte, sensibilidade
e cenários.
Pilotos: PETR4, VALE3 e WEGE3.

- **Coleta CVM** (Fase 1): cadastro, DFP de 10 anos, ITR dos dois últimos anos e composição do
  capital, com cache em `data/raw/` (`.meta.json` com URL, datas e sha256), TTL, revalidação e uso
  da cópia vencida se a rede falhar. Ticker ↔ CNPJ ↔ `CD_CVM` pelo cadastro e pelo FCA.
- **Padronização contábil** (Fase 2): plano de contas não financeiro por código, prefixo e regex;
  reapresentações resolvidas pelo documento mais recente; visões anual, acumulada, trimestral e
  LTM; métricas (EBITDA, NOPAT, capex, capital de giro, FCFF, dívida líquida, ROIC) com ajustes de
  IFRS 16, coligadas e não recorrentes. Cobertura de 100% das contas críticas nos 11 exercícios dos
  pilotos.
- **QA** (Fase 2): balanço, subcontas, identidades da DRE, lucro atribuído, D&A, saltos, anos
  faltantes e contas relevantes não mapeadas, em `data/processed/qa/qa_{TICKER}.json`. Os pilotos
  passam sem erro.
- **Conciliação**: 94 valores de Petrobras, Vale e WEG conferidos contra releases e relatórios; 83
  batem com o pipeline e 11 são pulados por definição própria da companhia ou período ainda fora da
  CVM.
- **Preços e macro** (Fase 3): preço por classe, market cap sem tesouraria, Ibovespa, dólar,
  Selic, IPCA 12 meses, Focus e taxa livre de risco, cada um conferido numa segunda fonte.
- **Perfil do investidor** (Fase 4): questionário de 10 perguntas com vetos, classificação em
  conservador/moderado/arrojado, `perfil/perfil_investidor.json` válido por 12 meses e parâmetros
  por perfil (margem de segurança, pesos dos cenários, horizonte, hurdle) em `settings.yaml`.
- **Premissas e projeção** (Fase 5): `config/empresas/{TICKER}.yaml` com ajustes, premissas,
  cenários e pares; sugestões a partir de 10 anos de histórico (com a origem de cada uma e aviso
  para commodity); projeção de receita a FCFF com ano corrente parcial e cenários
  pessimista/otimista; `valuation premissas sugerir TICKER [--escrever]`.
- **Custo de capital** (Fase 6): beta por regressão semanal contra o Ibovespa (Blume, avisos de R²
  e liquidez), manual ou realavancado na estrutura-alvo; Ke por `brl_direto` ou `usd_crp`; Kd
  histórico limitado ou manual; WACC conferido contra o g terminal; `valuation wacc TICKER` grava
  `saida/{TICKER}/{data}/wacc.csv`.
- **Testes**: 368 (357 passam, 11 golden pulados por motivo declarado), mypy strict e ruff limpos.
- **Ainda não**: plano de contas de financeiras, universo do Ibovespa (`atualizar --tudo` falha
  sem ele), beta por comparáveis (precisa dos pares), modelos, sensibilidade e saídas. Lista completa na seção 12 do `guia.md`.

## Decisões que completam ou divergem do `CLAUDE.md`

Detalhe e motivos nos ADRs ([índice](docs/decisoes/README.md)).

- **Repositório e ambiente** ([ADR 0001](docs/decisoes/0001-estrutura-repositorio.md)): a raiz é
  `Lastro/` e a especificação fica só no `CLAUDE.md` (sem `PROJETO.md`); Python 3.12 via `uv`.
- **Vale em BRL** ([ADR 0002](docs/decisoes/0002-moeda-da-vale.md)): na CVM a Vale reporta em
  `REAL`, não em USD como o guia supunha. Ela é avaliada com `brl_direto`; o caminho `usd_crp`
  fica implementado e testado só com dados sintéticos.
- **Escala das ações** ([ADR 0003](docs/decisoes/0003-escala-das-acoes.md)): a composição do
  capital não informa escala. `escala_acoes` no cadastro manual (hoje só VALE3) e correção
  automática de datas em milhares.
- **Mercado por API com validação cruzada** ([ADR 0004](docs/decisoes/0004-validacao-cruzada-de-apis.md)):
  cada dado tem fonte principal e segunda fonte; a principal vence, divergência vira aviso. O aviso
  de Rf (NTN-F × NTN-B + Focus) dispara hoje por construção.
- **Padronização contábil** ([ADR 0005](docs/decisoes/0005-padronizacao-contabil.md)): o documento
  mais recente vence por família e período; dívida financeira e arrendamento separados; D&A pela
  DFC; EBITDA pela definição das companhias; saldos com periodicidade `S`.
- **Premissas e projeção** ([ADR 0006](docs/decisoes/0006-premissas-e-projecao.md)): `sugerido`
  fica no YAML e é recalculado a cada execução (o valor de hoje vai em comentário); margem EBITDA
  ajustada com reversão de metade à mediana de 10a; ΔNWC incremental; deltas dos cenários de ±1
  desvio-padrão; arrendamento projetado como reposição; ano corrente pela fração restante.
- **Custo de capital** ([ADR 0007](docs/decisoes/0007-custo-de-capital.md)): o Kd histórico usa
  as despesas financeiras totais da DRE sobre a dívida bruta média (3 anos) e é limitado a Rf +
  faixa do `settings`; benefício fiscal pela alíquota nominal; IPCA de longo prazo pelo Focus;
  o beta do YAML da empresa vence o do `settings`; comando extra `valuation wacc`.

Os parâmetros de mercado de `config/settings.yaml` (ERP, faixa do Kd, teto do g terminal, Rf e
inflação em USD)
e o mapeamento perfil → parâmetros continuam **placeholders** até o usuário revisá-los (dúvidas em aberto na seção 19 do `CLAUDE.md`).

## Riscos e limitações

- **Qualidade dos dados gratuitos**: inconsistências de contas na CVM e instabilidade do yfinance.
  Por isso há QA e adaptadores isolados.
- **DCF é muito sensível** a WACC, g e margens; o resultado é uma faixa, não um número.
  A saída sempre mostra sensibilidade.
- **Empresas de commodity**: o histórico reflete o ciclo de preços; as premissas exigem revisão manual.
- **Beta** de ações pouco líquidas é ruidoso.
- **Financeiras**: sem dados regulatórios (Basileia) e sem lucro gerencial; o DDM é uma simplificação.
- **Sem consenso de analistas**: as projeções dependem só do histórico e do usuário.
- **IFRS 16**: tratar arrendamento como dívida exige proxy para a reposição dos arrendamentos;
  setores com muitos arrendamentos (varejo, aéreas) precisam de atenção.
- **Valor por ação** ignora diluição e diferenças entre classes de ação.
- **Uso pessoal e educacional**: não constitui recomendação de investimento.
