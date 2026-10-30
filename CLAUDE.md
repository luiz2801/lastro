# Valuation de Ações da B3 em Python — Guia do Projeto

> Documento-mestre para o agente que vai implementar o projeto. Leia inteiro antes de escrever código.
> Uso **estritamente pessoal**, local, em Linux. Ferramenta de estudo, **não é recomendação de investimento**.

---

## 0. Como usar este documento

**Convenções**

- `[DECIDIDO]` — o usuário definiu. Não mude sem perguntar.
- `[PREMISSA]` — padrão adotado porque o usuário não especificou. Pode ser revisto; registre a mudança em `docs/decisoes/` (ADR curto).
- `[VALIDAR]` — URL, nome de arquivo, código de conta ou série lembrado de memória. **Antes de codificar, confirme inspecionando a fonte real** e registre o resultado em `docs/fontes.md`.
- `[PLACEHOLDER]` — número ilustrativo em exemplos de configuração. **Não é dado de mercado.** O usuário deve revisar todos antes de confiar em qualquer resultado.

**Regras para o agente**

1. Trabalhe **por fase** (seção 17). Cada fase tem critério de pronto. Não avance com testes falhando.
2. **Nunca invente dados financeiros** (preços, múltiplos, ERP, beta, alíquotas). Se faltar um dado, falhe com mensagem clara ou use o parâmetro do `settings.yaml`.
3. Todo dado externo passa por um **adaptador** isolado (seção 6) com cache e logs. Trocar de fonte não deve tocar nos modelos.
4. O motor de cálculo é composto de **funções puras** (sem I/O, sem relógio global). A data-base é parâmetro.
5. Toda execução é **reprodutível**: salve as premissas usadas, versões e metadados junto da saída.
6. Falhe alto, não silenciosamente: validações contábeis (seção 7.5) geram erro ou aviso explícito.
7. Em dúvida de negócio (não de código), **pergunte ao usuário** em vez de decidir sozinho. Liste as dúvidas pendentes na seção 19.
8. Código tipado (`mypy`/`pyright` limpo), formatado com `ruff`, com testes `pytest`. Identificadores de domínio em português (`receita_liquida`, `divida_liquida`), termos genéricos de programação em inglês quando for o idioma natural da biblioteca.
9. Commits pequenos e atômicos, uma mensagem por mudança lógica, no formato `area: o quê` (ver `CONTRIBUTING.md`). **Antes de todo commit, `make lint tipos testes` passa**; se não puder rodar, não faça o commit e avise o usuário. Mantenha `CHANGELOG.md`.
10. **Consulte o `guia.md` antes de modificar** qualquer código (leia a seção do módulo, convenções e armadilhas) e **atualize-o na mesma entrega** de toda alteração de lógica, contrato, parâmetro, arquivo ou comando, subindo a versão no topo conforme a regra de manutenção do próprio guia. O guia é uma foto do estado atual (história vai no `CHANGELOG.md`); se código e guia discordarem, o código vence e o guia deve ser corrigido no mesmo commit.
11. **Consulte o diagrama de atividades em [`docs/diagrama_atividades.md`](docs/diagrama_atividades.md)** para se guiar no fluxo geral do pipeline (da CLI e ingestão ao DCF/DDM, sensibilidade e saídas). **Ele não substitui o `guia.md`, eles se complementam**: o diagrama dá a visão do fluxo dinâmico e das decisões de processo, enquanto o `guia.md` detalha contratos, módulos, parâmetros e convenções. **Mantenha-o atualizado**: sempre que etapas, decisões de fluxo, modelos ou saídas forem adicionados ou alterados com o prosseguimento do projeto, atualize o diagrama e a documentação associada na mesma entrega.
12. **Este documento tem decisões posteriores registradas em ADR.** Antes de seguir uma seção, confira no índice `docs/decisoes/README.md` se algum ADR a alterou: o ADR aceito vence o texto daqui. Se código e este documento divergirem sem ADR, aponte a divergência ao usuário em vez de escolher um lado em silêncio.
13. **Antes de dar uma tarefa por concluída**, siga a lista "Antes de concluir" do `CONTRIBUTING.md` (que documento atualizar para cada tipo de mudança está na tabela de lá) e diga no resumo ao usuário quais documentos foram atualizados, ou por que nenhum precisou.
14. **Consulte as regras modulares em [`docs/regras/`](docs/regras/README.md) conforme a área de atuação**: Para manter o foco, economizar janela de contexto e seguir diretrizes estritas da camada, consulte e aplique:
    - [`docs/regras/REGRAS_DADOS.md`](docs/regras/REGRAS_DADOS.md): ingestão, scrapers, APIs externas, cache, tickers e escala.
    - [`docs/regras/REGRAS_CONTABIL.md`](docs/regras/REGRAS_CONTABIL.md): padronização contábil, DFP/ITR, não-financeiras vs financeiras, IFRS 16 e QA.
    - [`docs/regras/REGRAS_MODELOS.md`](docs/regras/REGRAS_MODELOS.md): projeções, custo de capital (WACC/Ke), modelos (DCF/DDM/Múltiplos) e funções puras.
    - [`docs/regras/REGRAS_TESTES.md`](docs/regras/REGRAS_TESTES.md): suíte de testes, fixtures, dados sintéticos, golden tests e proibição de rede.
15. **Consulte os playbooks de tarefas frequentes em [`docs/recipes_agentes.md`](docs/recipes_agentes.md)**: Passos determinísticos para adicionar nova empresa, nova métrica contábil, parâmetros de configuração, múltiplos, testes golden e diagnóstico de falhas comuns.

---

## 1. Objetivo e escopo

Reproduzir em Python o que um analista faz em Excel para avaliar uma empresa listada na B3:

1. Coletar e padronizar demonstrações financeiras (10 anos).
2. Calcular métricas históricas (EBITDA, FCF, ROIC, dívida líquida etc.).
3. Montar premissas (sugeridas pelo histórico + sobrescrita manual) e projetar.
4. Estimar custo de capital.
5. Avaliar por **DCF** (FCFF) ou **DDM/lucro residual** (financeiras) e por **múltiplos** (comparáveis).
6. Fazer sensibilidade e cenários, ponderados pelo **perfil do investidor**.
7. Exportar **CSV + gráficos**.

**Escopo** `[DECIDIDO]`

- Principais empresas da B3, **incluindo financeiras** (bancos, seguradoras).
- Uma empresa por execução na v1 (a base de dados já é construída para todas).
- Somente fontes **gratuitas**. Sem consenso de analistas.
- 10 anos de histórico. Saída em CSV e gráficos (sem Excel).
- Linux; usuário avançado em Python.

**Fora do escopo na v1**: holdings (ITSA4, BRAP4 etc. — exigem NAV/SOTP), FIIs, REITs, empresas em recuperação judicial, SOTP, Monte Carlo, execução em lote, interface web.

---

## 2. Decisões e premissas

| # | Tema | Decisão | Status |
|---|---|---|---|
| 1 | Universo | Principais empresas, incl. financeiras. Dois pipelines: `nao_financeira` (FCFF) e `financeira` (DDM/lucro residual). | DECIDIDO |
| 2 | Métodos v1 | Não financeiras: DCF FCFF + múltiplos. Financeiras: DDM + P/VP justificado + múltiplos. | PREMISSA (usuário: "o mais simples") |
| 3 | Execução | Uma empresa por vez via CLI. | DECIDIDO |
| 4 | Moeda/inflação | Resultado principal **nominal**; relatório complementar **real** (deflacionado por IPCA). | DECIDIDO ("ambos") |
| 5 | Perfil do investidor | Questionário no início, resultado em **JSON local**, com validade de 12 meses. Perfil define margem de segurança, pesos dos cenários, horizonte e retorno mínimo exigido. | DECIDIDO (questionário/JSON) + PREMISSA (mapeamento) |
| 6 | Horizonte/valor terminal | Definidos pelo perfil (seção 8.3) + perpetuidade com g limitado; múltiplo de saída como checagem. | PREMISSA |
| 7 | Ajustes contábeis | Consolidado; IFRS 16 tratado como dívida; minoritários descontados; não recorrentes ajustáveis por empresa. Cada ajuste pode ser desligado no YAML. | PREMISSA (explicado ao usuário) |
| 8 | Premissas de projeção | Sugeridas pelo histórico **e** sobrescritas manualmente. | DECIDIDO ("ambas") |
| 9 | Comparáveis | Por setor (padrão) **e** por empresa (sobrescrita). | DECIDIDO |
| 10 | Fontes de dados | Apenas gratuitas: CVM, BCB, yfinance/brapi. | DECIDIDO |
| 11 | Histórico | 10 anos de série. | DECIDIDO |
| 12 | Consenso de analistas | Não. | DECIDIDO |
| 13 | Saída | CSV + gráficos PNG. Sem Excel. | DECIDIDO |
| 14 | Excel com fórmulas | Não. | DECIDIDO |
| 15 | Planilha-gabarito | Não existe. Validar contra releases/divulgações da própria empresa. | DECIDIDO |
| 16 | Ambiente | Linux; usuário avançado; sem tutorial de Python. | DECIDIDO |
| 17 | Natureza | Pessoal. | DECIDIDO |
| 18 | Universo de empresas | Componentes do Ibovespa, em arquivo versionado atualizado manualmente a cada quadrimestre. | PREMISSA |
| 19 | Atualização de dados | Sob demanda, com cache; `valuation atualizar` força download. | PREMISSA |
| 20 | Formato do CSV | `;` como separador, `,` decimal, `utf-8-sig` (abre direto no LibreOffice/Excel pt-BR). Opção para formato internacional. | PREMISSA |
| 21 | Empresas-piloto | PETR4, VALE3, WEGE3 (commodity em BRL, mineradora que reporta em USD, indústria). Piloto financeiro depois: ITUB4 e/ou BBAS3. Na CVM a Vale reporta em BRL (ADR 0002). | PREMISSA |

---

## 3. Princípios de engenharia

- **Separar dados, premissas e cálculo.** O motor roda para qualquer empresa; só o YAML muda.
- **Camadas** (de baixo para cima): `data` (adaptadores) → `contabil` (padronização) → `projecao` → `custo_capital` → `modelos` → `analise` → `saida`. Camada superior nunca é importada por inferior.
- **Dataclasses/pydantic** para todos os objetos trocados entre camadas (`Premissas`, `DadosEmpresa`, `CustoCapital`, `ResultadoDCF`...).
- **Dinheiro e escala**: guarde tudo em **unidades da moeda** (não em milhares) dentro do código; converta a escala (`ESCALA_MOEDA`) na ingestão e só reformate na saída.
- **Datas explícitas**: `data_base` (data da avaliação) é parâmetro; nenhum `date.today()` dentro de funções de cálculo.
- **Logging estruturado** (`logging`), nível INFO por padrão; `--verbose` para DEBUG.
- **Cache**: todo download vai para `data/raw/` com metadados (URL, data, hash). TTL configurável.
- **Sem segredos**: nenhuma chave de API é necessária na v1. Se algum dia houver, usar variável de ambiente + `.env` fora do git.

---

## 4. Stack e setup

- Python ≥ 3.11, gerenciador `uv`.
- Dependências: `pandas`, `numpy`, `pyarrow`, `pydantic>=2`, `pyyaml`, `typer`, `rich`, `requests` (com `requests-cache` ou cache próprio), `yfinance`, `python-bcb`, `statsmodels` (regressão do beta), `scipy`, `matplotlib`.
- Dev: `pytest`, `pytest-cov`, `hypothesis` (opcional), `ruff`, `mypy`.
- Opcional: `duckdb` para consultas ad hoc sobre os parquets.

`pyproject.toml` deve expor o comando `valuation` (entry point do `typer`).

Comandos de apoio (Makefile ou `justfile`): `setup`, `lint`, `tipos`, `testes`, `atualizar`, `rodar TICKER=PETR4`.

---

## 5. Estrutura de pastas

```
valuation/
├── pyproject.toml
├── README.md
├── CLAUDE.md                       # este documento (ADR 0001: não há PROJETO.md)
├── CONTRIBUTING.md                 # commits, documentação a atualizar, testes, convenções
├── guia.md                         # mapa do código no estado atual
├── CHANGELOG.md
├── Makefile
├── config/
│   ├── settings.yaml               # parâmetros globais (seção 6.5 e 10)
│   ├── setores.yaml                # setor -> pares padrão, tipo de modelo, defaults
│   ├── universo_ibovespa.csv       # ticker, cnpj (opcional), setor, tipo_modelo
│   ├── cadastro_manual.csv         # fallback ticker <-> cd_cvm/cnpj
│   ├── mapeamento_contas.yaml      # CVM -> plano padronizado (seção 7.2)
│   └── empresas/
│       ├── PETR4.yaml
│       ├── VALE3.yaml
│       └── WEGE3.yaml
├── data/                           # no .gitignore
│   ├── raw/                        # zips/csvs originais + .meta.json
│   ├── processed/                  # parquets padronizados
│   └── cache/
├── perfil/
│   └── perfil_investidor.json      # no .gitignore
├── saida/                          # no .gitignore: saida/{TICKER}/{YYYY-MM-DD}/
├── docs/
│   ├── fontes.md                   # o que foi validado de cada fonte
│   ├── decisoes/                   # ADRs curtos (índice e modelo em README.md)
│   └── metodologia.md              # fórmulas implementadas (gerar a partir da seção 11)
├── src/valuation/
│   ├── cli.py
│   ├── config.py                   # carrega/valida settings e YAMLs
│   ├── perfil/                     # questionario.py, pontuacao.py, parametros.py
│   ├── data/
│   │   ├── http.py                 # download com cache, retry, hash
│   │   ├── cadastro.py             # ticker <-> cd_cvm <-> cnpj, setor, classes de ação
│   │   ├── cvm.py                  # DFP/ITR/composição de capital
│   │   ├── precos.py               # cotações, FX, Ibovespa
│   │   └── macro.py                # SGS, Focus, Tesouro
│   ├── contabil/
│   │   ├── padronizacao.py         # aplica mapeamento_contas.yaml
│   │   ├── periodos.py             # anual, trimestral, LTM
│   │   ├── moeda.py                # detecção/conversão
│   │   ├── qa.py                   # validações
│   │   ├── nao_financeiras.py      # métricas
│   │   └── financeiras.py
│   ├── projecao/
│   │   ├── premissas.py            # schema pydantic do YAML
│   │   ├── sugestor.py             # premissas a partir do histórico
│   │   └── projetor.py
│   ├── custo_capital/              # beta.py, capm.py, kd.py, wacc.py
│   ├── modelos/                    # dcf.py, ddm.py, multiplos.py, ponte.py
│   ├── analise/                    # sensibilidade.py, cenarios.py
│   └── saida/                      # csv.py, graficos.py, resumo.py
└── tests/
    ├── fixtures/                   # amostras pequenas de CSVs da CVM
    ├── golden/                     # valores conferidos pelo usuário
    └── test_*.py
```

---

## 6. Fontes de dados

> **Regras modulares**: Antes de alterar adaptadores ou arquivos de configuração de dados, consulte [`docs/regras/REGRAS_DADOS.md`](docs/regras/REGRAS_DADOS.md).

Todas gratuitas. Cada fonte tem um **adaptador** com interface estável, cache e tratamento de erro. `[VALIDAR]` tudo que for URL/nome de arquivo.

### 6.1 CVM — dados abertos (portal `dados.cvm.gov.br`)

| Conjunto | Uso | Caminho esperado `[VALIDAR]` |
|---|---|---|
| Cadastro de cias abertas | CNPJ, `CD_CVM`, setor de atividade, situação | `.../CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv` |
| DFP (anual) | Demonstrações anuais | `.../CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_{ano}.zip` |
| ITR (trimestral) | Demonstrações trimestrais (LTM) | `.../CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_{ano}.zip` |
| FCA | Tickers, classes de ação por empresa | `.../CIA_ABERTA/DOC/FCA/DADOS/fca_cia_aberta_{ano}.zip` (arquivo de valores mobiliários) |

Dentro dos zips de DFP/ITR há CSVs por demonstração, com variantes `_con` (consolidado) e `_ind` (individual): `BPA` (ativo), `BPP` (passivo e PL), `DRE`, `DFC_MD` / `DFC_MI` (fluxo de caixa direto/indireto), `DVA`, `DMPL`, `DRA`, além do arquivo de **composição do capital** (quantidade de ações por classe e em tesouraria). `[VALIDAR]` os nomes.

**Detalhes de parsing que o agente deve tratar**

- Encoding `latin-1` (ISO-8859-1), separador `;`.
- Colunas típicas: `CNPJ_CIA`, `DT_REFER`, `VERSAO`, `DENOM_CIA`, `CD_CVM`, `GRUPO_DFP`, `MOEDA`, `ESCALA_MOEDA`, `ORDEM_EXERC` (`ÚLTIMO`/`PENÚLTIMO`), `DT_INI_EXERC`, `DT_FIM_EXERC`, `CD_CONTA`, `DS_CONTA`, `VL_CONTA`, `ST_CONTA_FIXA`.
- **Escala**: `ESCALA_MOEDA` = `MIL` ou `UNIDADE`. Multiplicar `VL_CONTA` na ingestão.
- **Moeda**: nem toda empresa reporta em BRL (a Vale, por exemplo, reporta em dólar). Detectar via `MOEDA` e tratar (seção 7.4).
- **Reapresentações**: manter, por (empresa, período, demonstração), a **maior `VERSAO`**. Para cada período, preferir o valor da **demonstração mais recente que o reporta** (inclusive como `PENÚLTIMO`), porque reflete reclassificações.
- **Duas versões de baixa qualidade conhecidas**: contas com nomes diferentes entre empresas (`DS_CONTA`), contas ausentes, sinais invertidos (despesas negativas) e mudanças de plano de contas ao longo do tempo. Por isso o mapeamento é por `CD_CONTA` **e** regex de `DS_CONTA` (seção 7.2).
- **10 anos**: baixar DFP de `ano_atual-10` até o último disponível e ITR dos 2 últimos anos. Conferir a consistência dos dados mais antigos (formatos e contas mudaram em torno de 2010 pós-IFRS e novamente com o IFRS 16 em 2019).

### 6.2 Preços — `yfinance` (com fallback brapi)

- Tickers `PETR4.SA`; Ibovespa `^BVSP`; dólar `BRL=X` (fallback: série SGS de câmbio).
- Baixar com `auto_adjust=False` para ter `Close` e `Adj Close`. Para market cap use `Close` **não ajustado por dividendos**; para retornos (beta) use `Adj Close`.
- Para **market cap**, somar `preço_da_classe × ações_da_classe` para todas as classes (ON + PN + units quando houver). Usar quantidade **excluindo ações em tesouraria**.
- **Sanidade**: se houve desdobramento/grupamento depois da data da última demonstração, a quantidade de ações pode estar defasada. Comparar market cap com histórico de preços e alertar se houver salto inexplicável.
- yfinance é não oficial e pode falhar. O adaptador deve ter retry, cache em disco e mensagem clara de erro. Interface (`PrecosProvider`) preparada para uma implementação brapi alternativa.
- brapi: o plano gratuito é limitado (15 mil requisições/mês, 1 ação por requisição, histórico curto, fundamentos básicos); PETR4, VALE3, MGLU3 e ITUB4 têm acesso de teste sem token. Usar só como fallback, nunca como fonte principal de fundamentos.

### 6.3 Macro — Banco Central e Tesouro

- **SGS** (via `python-bcb` ou REST) `[VALIDAR]` códigos: Selic meta (432), Selic diária (11), CDI (12), IPCA mensal (433), IGP-M (189), dólar (1). Registrar os códigos realmente usados em `docs/fontes.md`.
- **Expectativas Focus** (API Olinda do BCB, `ExpectativasMercadoAnuais`) `[VALIDAR]`: IPCA, Selic, câmbio e PIB esperados por ano. Gratuito e útil para a inflação e a Selic projetadas.
- **Taxa livre de risco em BRL**: rendimento do Tesouro Prefixado longo (NTN-F ~10 anos) a partir do **Tesouro Transparente** (CSV de taxas) `[VALIDAR]`. Alternativa: parâmetro manual no `settings.yaml`.
- Para o método em USD (seção 10.2): taxa livre de risco em dólar e inflação americana são **parâmetros manuais** (sem fonte gratuita estável a automatizar).

### 6.4 Cadastro e classificação

`data/cadastro.py` constrói uma tabela `ticker -> cd_cvm, cnpj, razao_social, setor_cvm, tipo_modelo, classes_acao`:

1. Cadastro CVM + FCA para casar ticker e empresa.
2. `config/cadastro_manual.csv` sobrescreve (casos de troca de ticker, units etc.).
3. `tipo_modelo` = `financeira` se o setor CVM for banco/seguradora/intermediação financeira; `nao_financeira` caso contrário; `holding` e `nao_suportada` geram erro explicativo na v1.

### 6.5 Parâmetros globais (`config/settings.yaml`) — exemplo

> Todos os números abaixo são **[PLACEHOLDER]**. O usuário revisa antes do primeiro uso real.

```yaml
versao: 1
data_base: hoje                    # ou "2026-10-30"
historico_anos: 10
moeda_saida: BRL

csv:
  separador: ";"
  decimal: ","
  encoding: "utf-8-sig"

cache_ttl_horas: {cvm: 168, precos: 12, macro: 12}

impostos:
  aliquota_nominal: 0.34           # IRPJ+CSLL, regra geral (financeiras têm outra)

custo_capital:
  metodo: brl_direto               # brl_direto | usd_crp
  rf_brl: {fonte: tesouro_prefixado_longo, override: null}
  erp: 0.05                        # PLACEHOLDER
  crp: 0.0                         # só usado em usd_crp
  rf_usd: 0.04                     # PLACEHOLDER, só usd_crp
  inflacao_usd_lp: 0.02            # PLACEHOLDER, só usd_crp
  beta: {metodo: regressao, janela_semanas: 260, ajuste_blume: true, min_r2_aviso: 0.10}
  estrutura_alvo: {metodo: mercado_atual}   # mercado_atual | setor | manual

terminal:
  g_nominal_max: 0.045             # PLACEHOLDER: teto do crescimento perpétuo
  ronic: wacc                      # wacc | roic_historico | valor_numerico
  checagem_multiplo_saida: true

dcf:
  convencao_meio_periodo: true
  alerta_tv_sobre_ev: 0.75

sensibilidade:
  wacc_passo: 0.005
  wacc_faixa: 0.02
  g_passo: 0.0025
  g_faixa: 0.01
```

---

## 7. Camada contábil

> **Regras modulares**: Antes de alterar a padronização contábil ou mapeamento de contas, consulte [`docs/regras/REGRAS_CONTABIL.md`](docs/regras/REGRAS_CONTABIL.md).

### 7.1 Modelo de dados

Tabela longa (parquet) `contas_padronizadas.parquet`:

`cd_cvm, ticker_principal, dt_refer, dt_ini, dt_fim, periodicidade (A|T|YTD), demonstracao, conta_padrao, valor, moeda, escala_aplicada, versao, fonte_arquivo`

Views em formato largo (anual, trimestral, LTM) são **derivadas** por funções, nunca persistidas manualmente.

### 7.2 Plano de contas padronizado (`config/mapeamento_contas.yaml`)

Cada conta padrão tem uma lista de regras avaliadas em ordem; a primeira que casar vence. Formato:

```yaml
nao_financeira:
  receita_liquida:
    - {dem: DRE, cd: "3.01"}
  ebit:
    - {dem: DRE, cd: "3.05"}
  resultado_financeiro:
    - {dem: DRE, cd: "3.06"}
  ir_csll:
    - {dem: DRE, cd: "3.08"}
  lucro_liquido:
    - {dem: DRE, cd: "3.11"}                 # consolidado do período
  lucro_liquido_controladora:
    - {dem: DRE, cd: "3.11.01"}
  da:                                        # depreciação e amortização
    - {dem: DVA, cd: "7.04.01"}
    - {dem: DFC, ds_regex: "(?i)deprecia|amortiza"}
  caixa:
    - {dem: BPA, cd: "1.01.01"}
  aplicacoes_financeiras:
    - {dem: BPA, cd: "1.01.02"}
  divida_cp:
    - {dem: BPP, cd: "2.01.04"}
  divida_lp:
    - {dem: BPP, cd: "2.02.01"}
  # arrendamentos: normalmente subcontas de dívida ou linhas próprias -> regex em DS_CONTA
  arrendamento:
    - {dem: BPP, ds_regex: "(?i)arrendamento"}
  patrimonio_liquido_total:
    - {dem: BPP, cd: "2.03"}
  minoritarios:
    - {dem: BPP, cd: "2.03.09"}
  cfo:
    - {dem: DFC, cd: "6.01"}
  capex_imobilizado_intangivel:
    - {dem: DFC, ds_regex: "(?i)aquisi.*(imobilizado|intang)|adi..es.*imobilizado"}
  # ... complementar durante a Fase 2
```

Os códigos acima (`3.01`, `3.05`, `2.03.09` etc.) seguem o plano de contas padrão da CVM e são o ponto de partida `[VALIDAR]` contra os dados reais. O agente deve:

- Gerar, na Fase 2, um relatório de cobertura (`% de empresas × anos com cada conta mapeada`) e iterar o YAML até cobrir bem as empresas-piloto.
- Suportar **sobrescrita por empresa** (`mapeamento_extra` no YAML da empresa) para casos particulares.
- Registrar contas **não mapeadas relevantes** em `qa_{ticker}.json` em vez de ignorá-las.

**Financeiras** têm plano de contas distinto (DRE começa por "Receitas da Intermediação Financeira", BPA/BPP com carteira de crédito, depósitos etc.). Criar seção `financeira:` separada no YAML, construída na Fase 10 após inspeção real dos dados de ITUB4/BBAS3.

### 7.3 Períodos e LTM — **cuidado, erro clássico**

- Fluxos (DRE, DFC) no ITR vêm **acumulados no ano (YTD)** e, na DRE, também por trimestre. DFC é só YTD.
- **LTM = último exercício anual + YTD atual − YTD do mesmo período do ano anterior.** Implementar em `periodos.py` e testar com dados sintéticos.
- Saldos (balanço) usam a **última data disponível**.
- Garantir que trimestres/anos usados em LTM pertençam à mesma versão/reapresentação.

### 7.4 Moeda e escala

- Detectar moeda de reporte por empresa. Se não for BRL:
  - o **valuation é feito na moeda de reporte** (fluxos e custo de capital na mesma moeda — método `usd_crp` da seção 10.2);
  - o valor por ação é convertido para BRL pela taxa spot da `data_base`;
  - converter apenas na saída final; **nunca** misturar fluxos em USD com taxa de desconto em BRL.
- Registrar em `meta.json` a moeda de reporte e a taxa usada.
- **Vale é o teste dessa lógica** (por isso está entre os pilotos).

> **ADR 0002:** na CVM a Vale reporta em `REAL` (a versão em USD é a do 20-F, fora das fontes da v1). Ela é avaliada em BRL com `brl_direto`; a detecção de moeda e o `usd_crp` ficam implementados e testados só com dados sintéticos.

### 7.5 Controles de qualidade (`qa.py`)

Gerar `qa_{ticker}.json` e **falhar** (ou avisar, conforme severidade):

| Verificação | Severidade |
|---|---|
| Ativo total = Passivo total + PL (tolerância 0,1%) | erro |
| Soma de subcontas ≈ conta-pai nas principais linhas | aviso |
| Receita > 0; EBIT consistente com Receita − Custos − Despesas | erro |
| LL consolidado = LL controladora + não controladores | aviso |
| D&A ausente ou zero para empresa intensiva em capital | aviso |
| Salto de >50% a/a em contas-chave sem explicação | aviso |
| Pontos faltantes em série histórica (anos sem DFP) | aviso |
| Moeda/escala inconsistente entre períodos | erro |

### 7.6 Métricas não financeiras (`nao_financeiras.py`)

```
EBITDA              = EBIT + D&A
EBITDA ajustado     = EBITDA - não recorrentes (config da empresa)
Alíquota efetiva    = IR/CSLL / LAIR   (limitar a [0, alíquota nominal] para projeção)
NOPAT               = EBIT * (1 - t)
Capex               = |capex imobilizado + intangível|  (DFC)
Capital de giro op. = (AC - caixa - aplicações) - (PC - dívida CP - arrendamento CP)
ΔNWC                = NWC_t - NWC_{t-1}
FCFF histórico      = NOPAT + D&A - Capex - ΔNWC
ROIC                = NOPAT / capital investido médio  (PL + dívida líquida [+ arrendamento])
Dívida bruta        = dívida CP + LP (+ arrendamento, se ifrs16 = divida)
Dívida líquida      = dívida bruta - caixa - aplicações financeiras
```

Notas: aplicações financeiras de LP e "ativos financeiros" de alguns balanços podem precisar entrar no caixa via regra por empresa (`caixa_extra` no YAML). Resultado de equivalência patrimonial costuma estar dentro de "despesas/receitas operacionais" — tratar conforme `ajustes.coligadas` (seção 9.1).

---

## 8. Perfil do investidor

### 8.1 Fluxo

1. `valuation perfil` roda o questionário interativo (`typer`/`rich`).
2. Pontua, classifica, grava `perfil/perfil_investidor.json`.
3. Todo `valuation rodar` lê o JSON. Se não existir ou estiver **vencido (12 meses)**, pede para refazer (ou aceita `--perfil conservador|moderado|arrojado` como override explícito, registrado no `meta.json`).

### 8.2 Questionário (estilo *suitability* de banco)

~10 perguntas de múltipla escolha, cada alternativa com pontuação 1–5. Temas (o agente redige o texto final em PT-BR):

1. Objetivo principal dos investimentos (preservar / renda / crescimento / especulação).
2. Horizonte de investimento.
3. Reação a uma queda de 20% na carteira.
4. Percentual do patrimônio que será aplicado em renda variável.
5. Dependência da renda dos investimentos.
6. Experiência com renda variável (anos, produtos).
7. Reserva de emergência (meses de despesas).
8. Conhecimento de análise fundamentalista.
9. Perda máxima aceitável em 12 meses.
10. Estabilidade da renda (fixa / variável).

**Pontuação** (10–50): `10–24` conservador, `25–37` moderado, `38–50` arrojado.
**Vetos**: horizonte < 2 anos ou "não aceito perdas" ⇒ conservador, independentemente da soma.

### 8.3 JSON (esquema)

```json
{
  "versao_questionario": 1,
  "data": "2026-10-30",
  "valido_ate": "2027-10-30",
  "respostas": {"q1": 3, "q2": 4},
  "pontuacao": 31,
  "vetos_aplicados": [],
  "perfil": "moderado"
}
```

### 8.4 Mapeamento perfil → parâmetros (`perfil/parametros.py`) `[PREMISSA]`

Valores iniciais **[PLACEHOLDER]**, ajustáveis em `settings.yaml`:

| Parâmetro | Conservador | Moderado | Arrojado |
|---|---|---|---|
| Margem de segurança exigida | 30% | 20% | 10% |
| Pesos dos cenários (pessimista / base / otimista) | 40 / 50 / 10 | 25 / 50 / 25 | 15 / 50 / 35 |
| Horizonte de projeção explícita (anos) | 5 | 7 | 10 |
| Retorno mínimo exigido (hurdle) | Selic + 3 p.p. | Selic + 5 p.p. | Selic + 7 p.p. |

**Princípio importante**: o perfil **não altera fatos contábeis nem o custo de capital da empresa**. Ele define quanto desconto o investidor exige, como pondera cenários e qual retorno mínimo espera. O valor intrínseco por cenário é o mesmo para todos os perfis.

Saída derivada do perfil:

```
valor_justo_ponderado = Σ peso_cenario × valor_por_acao_cenario
preco_maximo_compra   = valor_justo_ponderado × (1 - margem_seguranca)
retorno_esperado      = TIR ao comprar a preço de mercado (fluxos do cenário ponderado) -> compare com hurdle
```

---

## 9. Premissas e projeção

### 9.1 YAML por empresa (`config/empresas/{TICKER}.yaml`) — esquema

> Valores **[PLACEHOLDER]**. Validar com `pydantic`; campos desconhecidos geram erro.

```yaml
ticker: PETR4
tipo_modelo: nao_financeira        # nao_financeira | financeira
classes_acao: [PETR3, PETR4]
moeda_relatorio: auto              # auto | BRL | USD

ajustes:
  consolidado: true
  ifrs16: divida                   # divida | ignorar
  capex_equivalente_arrendamento: true
  minoritarios: contabil           # contabil | multiplo_pvp
  coligadas: somar_investimento_contabil   # somar_investimento_contabil | manter_no_ebit
  caixa_extra: []                  # contas adicionais a tratar como caixa
  divida_extra: []                 # ex.: passivos de pensão, contingências relevantes
  nao_recorrentes:
    - {ano: 2020, conta: ebit, valor: 0, descricao: "exemplo"}
  mapeamento_extra: {}

projecao:
  horizonte_anos: perfil           # perfil | inteiro
  receita:
    crescimento: {inicio: sugerido, fim: sugerido, curva: linear}   # ou lista explícita
  margens:
    ebitda: {inicio: sugerido, fim: sugerido, curva: linear}
  da_sobre_receita: sugerido
  capex_sobre_receita: sugerido
  nwc_sobre_receita: sugerido
  aliquota_imposto: {valor: sugerido, limite_superior: 0.34}
  terminal:
    g_nominal: null                # null => usa settings.terminal.g_nominal_max
    ronic: wacc

cenarios:                          # deltas sobre o base
  pessimista: {crescimento_pp: -0.02, margem_ebitda_pp: -0.03, capex_pp: +0.01}
  otimista:   {crescimento_pp: +0.02, margem_ebitda_pp: +0.03, capex_pp: -0.005}

pares:
  setor: petroleo_gas              # chave em setores.yaml
  incluir: []
  excluir: []

custo_capital:                     # sobrescritas opcionais
  beta: {metodo: regressao}        # regressao | comparaveis | manual
  kd: {metodo: historico}          # historico | manual
```

`sugerido` = o sugestor calcula a partir do histórico (9.2). O usuário pode substituir por número ou lista (`[0.06, 0.055, 0.05, ...]`).

### 9.2 Sugestor (`sugestor.py`)

Calcula e **grava no YAML** (com comentário da origem) a partir dos 10 anos:

- Crescimento da receita: CAGR 3/5/10 anos e mediana; ponto de partida = mediana de 5 anos, limitado a [-5%, +20%], **convergindo linearmente** para `g_terminal` ao final do horizonte.
- Margem EBITDA/EBIT: mediana de 5 anos com reversão parcial à mediana de 10 anos.
- `D&A/receita`, `capex/receita`, `NWC/receita`: mediana de 5 anos.
- Alíquota efetiva: mediana, limitada ao intervalo [0, alíquota nominal].
- Cenários: deltas proporcionais ao desvio-padrão histórico de crescimento e margem (com piso/teto).
- Sinalizar quando a empresa é de **commodity** (setor em `setores.yaml`): a série histórica reflete o ciclo de preços; avisar que as premissas devem ser revistas manualmente.

Sempre imprimir um resumo "premissas sugeridas × histórico" para o usuário revisar antes de rodar.

> **ADR 0006:** o campo continua `sugerido` no YAML (recalculado a cada execução) e o valor sugerido vai em comentário; a margem é a EBITDA ajustada, com reversão de metade; ΔNWC incremental; deltas dos cenários de ±1 desvio-padrão; campo novo `arrendamento_sobre_receita`.

### 9.3 Projetor (`projetor.py`)

Função pura `projetar(historico, premissas, horizonte) -> DataFrame` com colunas por ano: receita, EBITDA, D&A, EBIT, imposto, NOPAT, capex, ΔNWC, FCFF. Anos a partir do primeiro exercício **não encerrado** na `data_base`.

**Ano corrente parcial (*stub*)**: se a `data_base` cai no meio do exercício, só entra o **fluxo restante** do ano: `fracao = dias_restantes / 365`. O balanço (dívida líquida) é o da última demonstração disponível.

---

## 10. Custo de capital

### 10.1 Beta (`beta.py`)

- Retornos **semanais** (reduz ruído de pregões), 260 semanas, ação vs `^BVSP`, regressão OLS com `statsmodels`.
- Reportar `beta`, `r2`, `n_obs`, erro-padrão. Avisar se `r2 < min_r2_aviso` ou ação de baixa liquidez (beta pouco confiável).
- Opções: ajuste de Blume (`0,67·β + 0,33`), beta de comparáveis (desalavancar com Hamada `βu = βL / (1 + (1−t)·D/E)` e realavancar na estrutura-alvo), ou valor manual.
- Usar a classe de ação **mais líquida** da empresa como proxy.

### 10.2 Custo do capital próprio (`capm.py`)

Dois métodos (selecionados em `settings.yaml` ou por empresa):

**A) `brl_direto` (padrão para empresas que reportam em BRL)**

```
Ke_BRL = Rf_BRL + β × ERP
```

`Rf_BRL` = rendimento nominal longo do Tesouro Prefixado, **que já embute o risco soberano do Brasil**. **Não somar risco-país por cima** (dupla contagem). `ERP` é parâmetro manual (documentar a fonte usada pelo usuário).

**B) `usd_crp` (obrigatório para quem reporta em USD, ex.: Vale)**

```
Ke_USD = Rf_USD + β × ERP_maduro + CRP
Ke_BRL = (1 + Ke_USD) × (1 + π_BR) / (1 + π_US) − 1      # se o resultado precisar ser em BRL
```

Fluxos e taxa **sempre na mesma moeda**.

### 10.3 Custo da dívida e WACC

```
Kd (pré-imposto) = despesas financeiras com dívida / dívida bruta média   (limitado por faixas razoáveis; ou manual)
Kd (pós-imposto) = Kd × (1 - t)
WACC = Ke × E/(D+E) + Kd × (1-t) × D/(D+E)
```

- Pesos a valor de mercado do equity; dívida a valor contábil (proxy). Estrutura-alvo conforme `settings`.
- Se `ifrs16 = divida`, incluir arrendamento em D e nas despesas financeiras usadas para Kd.
- Nuance reconhecida e **não modelada na v1**: benefício fiscal de JCP.
- Validar: `WACC > g` sempre; erro explícito caso contrário.

> **ADR 0007:** a DRE da CVM só traz as despesas financeiras totais; o Kd histórico usa-as sobre a
> dívida bruta média (3 anos) e é limitado a Rf + faixa (`custo_capital.kd`). Benefício fiscal pela
> alíquota nominal.

### 10.4 Financeiras

Só **Ke** (não há WACC). Mesma lógica de beta/CAPM.

---

## 11. Modelos de avaliação

> **Regras modulares**: Antes de alterar modelos de avaliação, projeções ou custo de capital, consulte [`docs/regras/REGRAS_MODELOS.md`](docs/regras/REGRAS_MODELOS.md).

### 11.1 DCF — FCFF (não financeiras) (`dcf.py`)

```
FCFF_t   = EBIT_t × (1 - t) + D&A_t - Capex_t - ΔNWC_t   [- capex_equivalente_arrendamento se ifrs16=divida]
VP(FCFF) = Σ FCFF_t / (1 + WACC)^{τ_t}
```

- `τ_t` = anos entre `data_base` e o fim (ou meio, com `convencao_meio_periodo`) do período `t`; para o ano parcial, usar o ponto médio do trecho restante.
- **Valor terminal** (padrão, *value driver*):

```
NOPAT_{T+1} = NOPAT_T × (1 + g)
Reinvestimento = g / RONIC
FCFF_{T+1} = NOPAT_{T+1} × (1 - g/RONIC)
VT = FCFF_{T+1} / (WACC - g)      ;  VP(VT) = VT / (1 + WACC)^{τ_T}
```

  `RONIC = WACC` por padrão (sem criação de valor adicional na perpetuidade; conservador). Alternativa: ROIC histórico.
- **Checagens obrigatórias** (imprimir e gravar): VT/EV (aviso se > `alerta_tv_sobre_ev`), múltiplo EV/EBITDA implícito no terminal, g implícito de um múltiplo de saída (se configurado), `g < WACC`, `g ≤ g_nominal_max`.

### 11.2 Ponte EV → Equity (`ponte.py`)

```
EV
 − dívida bruta (inclui arrendamento se ifrs16 = divida)
 + caixa e aplicações financeiras
 − participação de não controladores (contábil, ou P/VP do setor se configurado)
 + investimentos em coligadas/controladas não consolidadas (contábil), se excluídas do EBIT
 − itens extra configurados em divida_extra (pensão, contingências)
 = Equity
Valor por ação = Equity / total de ações (excluída tesouraria)
```

- Saldos da **última demonstração disponível**; avisar a defasagem em dias.
- Diluição (opções, bônus) ignorada na v1 — registrar como limitação.
- Várias classes de ação: valor por ação igual para todas as classes (aproximação, pois PN pode ter direitos diferentes). Documentar.
- Mostrar a ponte como tabela e gráfico em cascata.

### 11.3 Financeiras (`ddm.py`)

Modelo principal: **DDM em dois estágios** com ROE e payout.

```
LL_t        = ROE_t × PL_{t-1}
Dividendos  = payout_t × LL_t
PL_t        = PL_{t-1} + LL_t − Dividendos
g sustentável = ROE × (1 − payout)
Valor terminal: P/VP justificado = (ROE_LP − g) / (Ke − g)  ->  VT = P/VP_just × PL_T
Valor = Σ Div_t/(1+Ke)^t + VT/(1+Ke)^T
```

- ROE converge de forma linear para `ROE_LP` (parâmetro; sugerido pela mediana histórica); payout converge para `1 − g/ROE_LP`.
- **Checagem cruzada**: lucro residual `V0 = PL0 + Σ (ROE_t − Ke) × PL_{t-1} / (1+Ke)^t + VT_residual`. Divergência relevante entre os dois métodos aponta inconsistência nas premissas.
- Limitações a documentar: o programa **não vê** índice de Basileia/capital regulatório (não está na DFP) — avisar que o payout projetado deve respeitar restrição de capital; usa lucro contábil (o "lucro recorrente gerencial" dos releases não está na CVM).
- Seguradoras: mesmo modelo, com ressalvas próprias (float, sinistralidade) documentadas.

### 11.4 Múltiplos (`multiplos.py`)

- Para cada empresa e cada par: calcular **com o mesmo pipeline contábil** (consistência entre empresa-alvo e pares).
- Não financeiras: P/L, EV/EBITDA, EV/EBIT, EV/Receita, P/VP, EV/FCF, dividend yield (usar LTM).
- Financeiras: P/L, P/VP, dividend yield, ROE; regressão opcional **P/VP × ROE** entre pares.
- Estatísticas dos pares: mediana, média, quartis (P25/P75). Descartar múltiplos negativos/indefinidos; winsorizar extremos (parâmetro).
- Exigir ≥ 3 pares válidos; caso contrário, aviso e resultado marcado como "baixa confiança".
- Valor implícito: `múltiplo_par × métrica_da_empresa` (EV → ponte → equity → por ação; P/L e P/VP direto).
- Pares padrão por setor em `setores.yaml`; `incluir`/`excluir` por empresa.

### 11.5 Valores reais (relatório complementar)

Deflacionar fluxos e valor por IPCA projetado (Focus no curto prazo, meta/parâmetro no longo) para exibir o equivalente em reais de hoje. Não substitui o resultado nominal.

---

## 12. Sensibilidade, cenários e football field

- `avaliar(premissas, dados, custo_capital) -> Resultado` deve ser **pura e rápida**, para poder rodar milhares de vezes.
- **Cenários**: pessimista/base/otimista (deltas do YAML) → valor por ação de cada → ponderação pelo perfil.
- **Tabelas de sensibilidade** (CSV + heatmap):
  - WACC × g (valor por ação).
  - Margem EBITDA terminal × crescimento da receita.
  - Para financeiras: Ke × g e ROE_LP × Ke.
- **Football field** com barras de: DCF (pess.–otim.), DCF (faixa WACC/g), P/L, EV/EBITDA, P/VP pelos quartis dos pares, faixa de 52 semanas; linhas verticais: preço atual e preço máximo de compra do perfil.

---

## 13. Saídas

Diretório: `saida/{TICKER}/{YYYY-MM-DD}/`. CSV no formato do `settings.csv`.

| Arquivo | Conteúdo |
|---|---|
| `resumo.csv` | Linha única: ticker, data-base, perfil, preço, valor por cenário, valor ponderado, preço máximo de compra, upside, retorno esperado vs. hurdle, WACC/Ke, g, VT/EV, avisos |
| `historico.csv` | 10 anos de métricas padronizadas |
| `projecao_{cenario}.csv` | Projeção ano a ano |
| `wacc.csv` | Componentes do custo de capital |
| `ponte_ev_equity.csv` | Ponte detalhada |
| `sensibilidade_*.csv` | Matrizes |
| `multiplos_pares.csv` | Múltiplos de cada par |
| `multiplos_implicitos.csv` | Valores implícitos e estatísticas |
| `valores_reais.csv` | Versão deflacionada |
| `premissas_usadas.yaml` | Cópia final das premissas (reprodutibilidade) |
| `qa.json` | Resultado dos controles de qualidade |
| `meta.json` | Versão do código, data/hash das fontes, perfil, moeda, avisos |

Gráficos (`matplotlib`, PNG, legendas em PT-BR): `football_field.png`, `historico_vs_projecao.png`, `sensibilidade_heatmap.png`, `ponte_ev_equity.png` (cascata), `composicao_valor.png` (VP dos fluxos × VP do valor terminal).

---

## 14. CLI (`typer`)

```
valuation perfil [--mostrar] [--refazer]
valuation cadastro buscar TEXTO
valuation atualizar [--tickers PETR4,VALE3] [--tudo] [--forcar]
valuation qa TICKER
valuation premissas sugerir TICKER [--escrever]
valuation rodar TICKER [--cenario base|pessimista|otimista|todos]
                       [--data-base AAAA-MM-DD] [--perfil conservador|moderado|arrojado]
                       [--saida DIR] [--formato-csv br|intl] [--sem-graficos]
valuation comparar TICKER                 # só múltiplos/pares
valuation versao
```

Mensagens em PT-BR, `rich` para tabelas no terminal, códigos de saída não nulos em erro.

---

## 15. Testes e validação

> **Regras modulares**: Antes de criar ou alterar testes e fixtures, consulte [`docs/regras/REGRAS_TESTES.md`](docs/regras/REGRAS_TESTES.md).

**Unitários (`pytest`)**

- `periodos.py`: LTM com dados sintéticos (anual + YTD).
- `moeda.py`/escala: conversão de `MIL`/`UNIDADE` e moeda.
- `padronizacao.py`: mapeamento por `cd` e por regex, precedência de regras.
- `dcf.py`: exemplo **calculado à mão** (projeção curta, WACC e g conhecidos) com valor esperado exato; casos-limite (`g ≥ WACC` deve falhar).
- `wacc.py`/`capm.py`: valores conhecidos; método `usd_crp` ↔ `brl_direto` coerentes quando as taxas de inflação são consistentes.
- `beta.py`: regressão em série sintética com beta conhecido.
- `ddm.py`: consistência DDM × lucro residual em caso sintético.
- `perfil`: pontuação, vetos, validade.
- Propriedades (opcional, `hypothesis`): valor por ação é monotônico decrescente em WACC; crescente em margem.

**Integração**

- Fixtures pequenas de CSVs reais da CVM (uma empresa, dois anos) e pipeline completo offline (preços/macro mockados).

**Golden / conciliação com a realidade**

- `tests/golden/`: valores que o **usuário confere** com divulgações da empresa (receita, EBITDA, lucro líquido, dívida líquida de um ano). O agente deve pedir ao usuário essa conferência para cada piloto no fim da Fase 2 e codificar os valores como testes.

**Qualidade de código**: cobertura mínima de 80% nas camadas `contabil`, `modelos`, `custo_capital`, `perfil`.

---

## 16. Pilotos

| Ticker | Por que | Desafios que exercita |
|---|---|---|
| PETR4 | Commodity, estatal, ON/PN | Várias classes de ação, ciclo de commodity, dívida/arrendamentos relevantes |
| VALE3 | Mineração | **Reporte em USD**, método `usd_crp`, conversão cambial. Na CVM reporta em BRL: avaliada com `brl_direto` (ADR 0002) |
| WEGE3 | Industrial de crescimento | Receitas em várias moedas, crescimento alto com fade longo |
| ITUB4 / BBAS3 (Fase 10) | Bancos | Plano de contas financeiro, DDM, P/VP justificado |

---

## 17. Roadmap por fases (com critério de pronto)

> Fases concluídas levam ✅ (atualize ao fechar uma fase; o estado detalhado está no `README.md` e na seção 1 do `guia.md`).

**Fase 0 — Fundação** ✅ concluída
Repo, `pyproject.toml`, `uv`, `ruff`, `mypy`, `pytest`, Makefile, `settings.yaml`, `.gitignore` (dados, perfil, saída), `docs/` com `fontes.md` e ADRs.
*Pronto:* `make lint testes` passa; `valuation versao` roda.

**Fase 1 — Cadastro e coleta CVM** ✅ concluída
`http.py`, `cadastro.py`, `cvm.py`: baixar cadastro, DFP/ITR, composição de capital; cache e `.meta.json`; mapear ticker ↔ empresa para os pilotos.
*Pronto:* `valuation atualizar --tickers PETR4,VALE3,WEGE3` baixa e armazena 10 anos de DFP + ITR recentes; `valuation cadastro buscar` funciona; `docs/fontes.md` com URLs validadas.

**Fase 2 — Padronização contábil e QA** ✅ concluída
`padronizacao.py`, `periodos.py` (LTM), `moeda.py`, `qa.py`, `nao_financeiras.py`, `mapeamento_contas.yaml`.
*Pronto:* tabela padronizada dos 3 pilotos; relatório de cobertura de contas ≥ 95% nas contas críticas; QA sem erros; **conciliação com divulgações da empresa confirmada pelo usuário** (golden tests).

**Fase 3 — Preços e macro** ✅ concluída
`precos.py`, `macro.py` com cache e fallback.
*Pronto:* market cap correto (multi-classe), Ibovespa e câmbio, Selic/IPCA/Focus e taxa livre de risco carregados.

**Fase 4 — Perfil do investidor** ✅ concluída
Questionário, pontuação, JSON, validade, mapeamento de parâmetros.
*Pronto:* `valuation perfil` gera JSON válido; testes de pontuação e vetos.

**Fase 5 — Premissas e projeção** ✅ concluída
Schema pydantic, `sugestor.py`, `projetor.py`, ano parcial.
*Pronto:* `valuation premissas sugerir PETR4 --escrever` produz YAML comentado; projeção reproduz exemplo manual.

**Fase 6 — Custo de capital** ✅ concluída
Beta, CAPM (`brl_direto` e `usd_crp`), Kd, WACC.
*Pronto:* testes unitários; relatório `wacc.csv` com avisos de qualidade do beta.

**Fase 7 — DCF, ponte, sensibilidade e cenários** ✅ concluída
`dcf.py`, `ponte.py`, `sensibilidade.py`, `cenarios.py`, ponderação por perfil.
*Pronto:* valor por ação por cenário e ponderado para os 3 pilotos; checagens de VT/EV e g impressas; sensibilidade CSV.

**Fase 8 — Múltiplos e comparáveis** ✅ concluída
`multiplos.py`, `setores.yaml`, estatísticas dos pares.
*Pronto:* múltiplos e valores implícitos para os pilotos, com tratamento de outliers e aviso de poucos pares.

**Fase 9 — Saídas** ✅ concluída
CSVs completos, `meta.json`, gráficos, football field, relatório real (deflacionado).
*Pronto:* `valuation rodar PETR4` gera a pasta de saída completa e reprodutível.

**Fase 10 — Financeiras** ✅ concluída
Mapeamento de contas de bancos/seguradoras, métricas (ROE, payout, PL), `ddm.py`, lucro residual, P/VP justificado, múltiplos financeiros.
*Pronto:* pipeline completo para ITUB4 e/ou BBAS3 com checagem DDM × lucro residual.

**Fase 11 — Extensões (só se o usuário pedir)**
Modo em lote/screening, SOTP/NAV para holdings, Monte Carlo, deck de commodities, tratamento de JCP, diluição.

---

## 18. Riscos e limitações (documentar no README)

- **Qualidade dos dados gratuitos**: inconsistências de contas na CVM e instabilidade do yfinance. Por isso QA + adaptadores.
- **DCF é muito sensível** a WACC, g e margens; o resultado é uma faixa, não um número. A saída sempre mostra sensibilidade.
- **Empresas de commodity**: histórico reflete ciclo de preços; premissas exigem revisão manual.
- **Beta** de ações pouco líquidas é ruidoso.
- **Financeiras**: sem dados regulatórios (Basileia) e sem lucro gerencial; DDM é simplificação.
- **Sem consenso de analistas**: projeções dependem só do histórico e do usuário.
- **IFRS 16**: tratamento como dívida exige proxy para reposição de arrendamentos (`capex_equivalente_arrendamento`); setores com muitos arrendamentos (varejo, aéreas) precisam de atenção.
- **Valor por ação** ignora diluição e diferenças entre classes de ação.
- **Uso pessoal e educacional**: não constitui recomendação de investimento.

---

## 19. Dúvidas em aberto (o agente pergunta ao usuário quando chegar a hora)

1. ~~ERP e fonte preferida do prêmio de risco (Fase 6).~~ Respondida: 5,0% como premissa do
   usuário, sem fonte externa (`docs/fontes.md`); ERP implícito do Ibovespa no `docs/backlog.md`.
2. Taxa livre de risco: Tesouro Prefixado 10 anos automático ou valor manual (Fase 3/6).
3. ~~Teto do crescimento perpétuo em termos nominais (Fase 7).~~ Respondida: 5,0% (ADR 0008).
4. ~~Lista final de empresas do universo (Ibovespa atual) e pares por setor (Fase 8).~~ Respondida
   (ADR 0009 e 0010).
5. Aceitar os valores iniciais do mapeamento perfil → parâmetros (seção 8.4) ou ajustá-los (Fase 4).
6. Conferência dos números dos pilotos contra os releases das empresas (fim da Fase 2).
7. Tratamento de JCP e de diluição: ignorar na v1 (padrão) ou incluir.
8. Faixa do Kd histórico (`custo_capital.kd`, hoje Rf + 0 a 5 p.p.) e se o piso deve ser a Rf em BRL
   para empresas com dívida em dólar (ADR 0007) (Fase 6).
9. Conferência de lucro, PL e ROE de ITUB4 e BBAS3 contra os releases, para os golden das
   financeiras (Fase 10; a CVM traz IFRS consolidado, não o lucro recorrente gerencial).
10. Setor `seguradoras`: separar holdings de seguros (BBSE3, CXSE3) das operadoras (PSSA3,
    IRBR3)? Juntas, o P/VP dos pares distorce o valor das operadoras (`guia.md`, armadilha 38).

---

## 20. Primeiros passos para o agente

1. Criar o repositório com a estrutura da seção 5 e executar a **Fase 0**.
2. Ao iniciar a **Fase 1**, validar cada URL da seção 6 fazendo requisição real e inspecionando os arquivos; registrar em `docs/fontes.md` o que foi confirmado e o que mudou em relação a este guia.
3. Ao final de cada fase, atualizar `CHANGELOG.md`, rodar `make lint tipos testes` e resumir ao usuário: o que ficou pronto, o que foi decidido, o que depende dele.