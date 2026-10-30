# valuation — Valuation de ações da B3

Ferramenta pessoal e educacional para avaliar empresas listadas na B3 (DCF, DDM e múltiplos)
a partir de dados gratuitos (CVM, BCB, Tesouro, yfinance, brapi). **Não constitui recomendação de
investimento.**

## Documentação

| Documento | Para quê |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Especificação completa: escopo, decisões, fórmulas, fontes, roadmap por fase e regras para o agente |
| [`docs/regras/`](docs/regras/README.md) | Regras modulares por camada em `docs/regras/` ([`DADOS`](docs/regras/REGRAS_DADOS.md), [`CONTABIL`](docs/regras/REGRAS_CONTABIL.md), [`MODELOS`](docs/regras/REGRAS_MODELOS.md), [`TESTES`](docs/regras/REGRAS_TESTES.md)) para agentes de IA |
| [`guia.md`](guia.md) | Mapa do código como ele está hoje: módulos, contratos, parâmetros, testes e armadilhas. Leia antes de modificar |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Política de commits, que documento atualizar, testes e convenções |
| [`docs/decisoes/`](docs/decisoes/README.md) | ADRs: decisões que completam ou divergem do `CLAUDE.md`, com índice |
| [`docs/justificativas_e_alternativas.md`](docs/justificativas_e_alternativas.md) | Por que cada decisão do valuation foi tomada e que alternativas dá para usar (config, código, ADR ou fase) em outras análises |
| [`docs/fontes.md`](docs/fontes.md) | O que foi confirmado em cada fonte real (URLs, arquivos, contas, séries SGS) |
| [`docs/diagrama_atividades.md`](docs/diagrama_atividades.md) | Diagrama de atividades UML do pipeline (complementa o `guia.md` com o fluxo dinâmico de processos e decisões) |
| [`docs/recipes_agentes.md`](docs/recipes_agentes.md) | Playbooks de tarefas frequentes e procedimentos operacionais passo a passo para agentes de IA |
| [`docs/contexto_rapido.md`](docs/contexto_rapido.md) | Cheatsheet de ~80 linhas: o que ler para cada tipo de tarefa, convenções e armadilhas mais repetidas (poupa contexto de agentes) |
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
uv run valuation atualizar --tickers PETR4 --com-pares   # baixa também os pares do setor
uv run valuation comparar PETR4             # múltiplos dos pares e valor implícito
uv run valuation rodar PETR4                # DCF por cenário, valor ponderado pelo perfil, sensibilidade
make rodar TICKER=PETR4                      # o mesmo
```

`atualizar` precisa rodar antes de `qa`, `historico`, `cobertura`, `mercado`, `premissas`, `wacc`,
`comparar` e `rodar` (com `--com-pares` para os múltiplos); `rodar` também exige um perfil válido
(`valuation perfil`) ou `--perfil`. Parâmetros e efeitos de cada comando: seção 3 do
[`guia.md`](guia.md).

Para validar o preço de qualquer ticker na brapi (sem token, só PETR4, VALE3, MGLU3 e ITUB4), crie
um token gratuito em brapi.dev e exporte `BRAPI_TOKEN`.

## Estrutura

- `src/valuation/`: código, em camadas `data` → `contabil` → `projecao` → `custo_capital` →
  `modelos` → `analise` → `saida`, mais `perfil`.
- `config/`: `settings.yaml` (parâmetros globais), `mapeamento_contas.yaml` (plano de contas
  padronizado), `cadastro_manual.csv` (holdings e escala de ações), `setores.yaml` e
  `empresas/{TICKER}.yaml` (ajustes e premissas de cada empresa).
- `docs/`: fontes validadas, ADRs, regras modulares por camada (`docs/regras/`), diagrama de atividades e recipes.
- `tests/`: testes offline; `tests/golden/referencias.yaml` tem valores conferidos com documentos
  das companhias.
- `referencias/`: PDFs e planilhas das companhias (fora do git; só o índice é versionado).
- `data/`, `saida/`, `perfil/`: gerados localmente, fora do git.

## Estado atual

**Fases 0 a 8 e 10 concluídas** (seção 17 do `CLAUDE.md`). Próxima: Fase 9, saídas (gráficos,
`meta.json`, relatório real).
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
- **DCF, ponte, cenários e sensibilidade** (Fase 7): FCFF descontado com ano parcial e meio
  período, valor terminal por value driver, ponte EV → equity → valor por ação, cenários
  ponderados pelo perfil com preço máximo de compra, Ke implícito no preço contra o hurdle e WACC
  implícito, matrizes WACC × g e margem × crescimento; `valuation rodar TICKER` grava resumo,
  projeções, ponte e sensibilidades em `saida/{TICKER}/{data}/`.
- **Múltiplos e comparáveis** (Fase 8): pares por setor em `config/setores.yaml`, medidos com o
  mesmo pipeline do alvo; P/L, EV/EBITDA, EV/EBIT, EV/Receita, P/VP, EV/FCF e dividend yield com
  winsorização, quartis, aviso de poucos pares e de escala implausível; valor implícito do alvo;
  beta por comparáveis, estrutura-alvo do setor, minoritários pelo P/VP e g implícito no múltiplo
  de saída; `valuation comparar TICKER` e múltiplos no `rodar`.
- **Testes**: 446 (435 passam, 11 golden pulados por motivo declarado), mypy strict e ruff limpos.
- **Universo**: `config/universo_ibovespa.csv` com os 76 ativos da carteira de 30/10/26 da B3;
  `valuation atualizar --tudo` baixa os dados de todos (holdings só avisam).
- **Financeiras** (Fase 10): plano de contas de bancos e seguradoras (25 companhias
  conferidas), métricas (ROE, payout, PL da controladora), QA próprio; premissas do DDM (ROE
  até o de longo prazo, payout até 1 − g/ROE) e projeção de lucro, dividendos e PL; DDM com
  checagem por lucro residual, Ke sem WACC, cenários ponderados pelo perfil, Ke implícito no preço
  e matrizes Ke × g e ROE × Ke; múltiplos P/L, P/VP e DY com regressão P/VP × ROE (setores
  `bancos`, 18 pares, e `seguradoras`); units no market cap; YAMLs de 5 bancos e 4 seguradoras;
  todos os comandos aceitam financeiras. Golden das financeiras aguardam a conferência do usuário.
- **Ainda não**: gráficos e demais saídas da Fase 9. Lista
  completa na seção 12 do `guia.md`.

## Decisões que completam ou divergem do `CLAUDE.md`

Detalhe e motivos nos ADRs ([índice](docs/decisoes/README.md)).

- **Repositório e ambiente** ([ADR 0001](docs/decisoes/0001-estrutura-repositorio.md)): a raiz é
  `Lastro/` e a especificação fica só no `CLAUDE.md` (sem `PROJETO.md`); Python 3.12 via `uv`.
- **Vale em BRL** ([ADR 0002](docs/decisoes/0002-moeda-da-vale.md)): na CVM a Vale reporta em
  `REAL`, não em USD como o guia supunha. Ela é avaliada com `brl_direto`; o caminho `usd_crp`
  fica implementado e testado só com dados sintéticos.
- **Escala das ações** ([ADR 0003](docs/decisoes/0003-escala-das-acoes.md)): a composição do
  capital não informa escala. `escala_acoes` no cadastro manual (VALE3 e sete pares) e correção
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
- **DCF e cenários** ([ADR 0008](docs/decisoes/0008-dcf-ponte-e-cenarios.md)): o retorno esperado
  sai em duas leituras (Ke implícito no preço, comparado ao hurdle, e WACC implícito); teto do g
  perpétuo em 5,0%; valor terminal descontado no meio do último ano com a convenção de meio
  período; ponte com o balanço dos pesos do WACC; `rodar` entra já na Fase 7 com saída parcial.
- **Múltiplos e comparáveis** ([ADR 0009](docs/decisoes/0009-multiplos-e-comparaveis.md)): pares
  decididos pelo usuário (petróleo só E&P, mineração separada da siderurgia, lista ampla de
  máquinas); EV como inverso da ponte e EBITDA ajustado; winsorização 10/90 com valor pela
  mediana e faixa P25–P75; par com P/VP implausível é excluído (escala das ações).
- **Universo e Vale** ([ADR 0010](docs/decisoes/0010-universo-ibovespa-e-pares-da-mineracao.md)):
  universo da carteira teórica da B3 e CSNA3 como terceiro par da mineração.
- **Financeiras** ([ADR 0011](docs/decisoes/0011-plano-de-contas-das-financeiras.md)): plano de
  contas por descrição para bancos, seguradoras e o plano comercial; individuais quando não há
  consolidado; ROE sobre o PL inicial; corretoras (WIZC3, QUAL3) avaliadas como não financeiras.
- **Premissas das financeiras** ([ADR 0012](docs/decisoes/0012-premissas-e-projecao-das-financeiras.md)):
  ROE de longo prazo pela mediana de 10 anos, payout até 1 − g/ROE, cenários pelo ROE.
- **DDM das financeiras** ([ADR 0013](docs/decisoes/0013-ddm-ke-e-cenarios-das-financeiras.md)):
  desconto no fim do ano, lucro residual igual ao DDM por construção, Ke sem WACC.
- **Múltiplos das financeiras** ([ADR 0014](docs/decisoes/0014-multiplos-e-pares-das-financeiras.md)):
  P/L, P/VP e DY sem EV, regressão P/VP × ROE, pares de todos os bancos cotados.
- **Units** ([ADR 0015](docs/decisoes/0015-units-no-market-cap.md)): ON e PN pelo preço da unit
  quando a composição está no cadastro manual (BPAC11, BRBI11, SANB11).

O ERP (5,0%) é premissa do usuário, sem fonte externa (`docs/fontes.md`). Os demais parâmetros de
mercado de `config/settings.yaml` (faixa do Kd, Rf e inflação em USD) e o mapeamento perfil →
parâmetros continuam **placeholders** até o usuário revisá-los (dúvidas em aberto na seção 19 do `CLAUDE.md`).

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
