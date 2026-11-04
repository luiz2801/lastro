# Changelog

## [Não lançado]

### Sprint GUI 1, S1: camada de serviço, fatia "empresa" (ADR 0022)
- `src/valuation/servicos/empresa.py`: `carregar_cadastro`, `padronizar` e `Padronizada` saem de
  `cli.py`, sem terminal; o aviso de demonstrações individuais volta em `avisos`. Nenhuma saída muda:
  `cli._carregar_cadastro` e `cli._padronizar` ficam como invólucros e os testes da CLI seguem sem
  edição.

### GUI: decisão de tecnologia e plano da sprint (ADR 0022)
- `docs/decisoes/0022-gui-streamlit-plotly.md`: Streamlit + Plotly (grupo opcional `gui`), camada
  `servicos/` compartilhada com a CLI, leitura de `saida/` e cache com botão de atualizar.
- `docs/backlog.md`: seção "Sprint GUI 1" (tarefas S1 a S6, perguntas abertas sobre a série
  histórica de múltiplos, critério de pronto e riscos). Nada implementado ainda.
- `docs/backlog.md`: "Catálogo de métricas a acrescentar" (não financeiras e financeiras, com
  fórmula proposta, estado do dado e classe de tratamento de anomalias; Basileia via IF.data a
  validar).

### Política: perguntar antes de decidir o que muda a saída
- `CLAUDE.md` (regra 7 da seção 0) e `CONTRIBUTING.md` (seção "Dúvidas"): toda decisão que possa
  mudar a saída (valor, arquivo gravado, o que a CLI mostra, aviso, padrão de opção, definição de
  métrica, fonte) é perguntada ao usuário antes de implementar, com as opções e a recomendação.
  Pedido do usuário em 2026-11-03.

### Carteira pessoal, Etapa C3: indicadores por ativo (ADR 0020, RF-004)
- `src/valuation/analise/indicadores.py` (puro): `historicos` (margem líquida, margem EBITDA,
  dívida líquida/EBITDA, ROE sobre o PL inicial e ROIC), `historicos_financeira` (ROE, payout, ROA,
  ativo/PL) e `de_mercado` (P/L, P/VP, dividend yield, EV/EBITDA, EV/EBIT por `mt.multiplo`, a
  mesma conta do `comparar`). Denominador ≤ 0 vira NaN. Os valores já existentes são só reexpostos.
- `contabil/nao_financeiras.py`: nova coluna `pl_controladora_inicio` (PL total − minoritários da
  linha anterior; no LTM, o balanço de 12 meses antes), base do ROE. Nada mais muda nas métricas.
- `valuation indicadores TICKER [--anos N] [--data-base] [--forcar] [--explicar]`: tabela por
  exercício encerrado + LTM e tabela "De mercado". Sem mercado (preço ou composição indisponível),
  mostra o histórico e avisa. Financeiras: só os indicadores e múltiplos de equity.
- Glossário: grupo novo "Indicadores" (margem líquida, margem EBITDA, dívida líquida/EBITDA, ROIC,
  ROA, ativo/PL) e `legenda_indicadores`. Correção: a definição do ROE dizia "PL médio", mas o
  código usa o PL do início do período.
- Testes: `tests/test_indicadores.py` (à mão), `pl_controladora_inicio` em `test_nao_financeiras.py`
  e quatro casos do comando em `test_cli.py` (657 testes, 646 passam). `guia.md` 1.35.
- Pendente: golden dos indicadores novos (depende da conferência do usuário com o release).

### Backlog: validação cruzada dos fundamentos (yfinance × CVM)
- `docs/backlog.md`: desenho, etapas V1 a V5, testes, limites e perguntas abertas da checagem de
  lucro, PL, ativo e receita contra o Yahoo, com alerta pedindo o release só quando divergir. Inclui a
  sondagem de 2026-11-03 (BBAS3 bate; PETR4 vem em USD). Só documentação; nada implementado.

### README: APIs e testes que as validam
- `README.md`, seção "APIs e fontes de dados": CVM, yfinance, brapi, BCB (SGS e Focus) e Tesouro
  Transparente, com endpoint, adaptador e a fonte usada na validação cruzada; e a tabela dos
  testes que validam os adaptadores (`test_http`, `test_cvm`, `test_cadastro`, `test_precos`,
  `test_macro`, `test_validacao`, `test_golden`). Só documentação.

### Golden do BBAS3 (seção 19, item 9 do `CLAUDE.md`)
- `tests/golden/referencias.yaml`: lucro (controladora e total) de 1T25 a 4T25, 1S25, 9M25, 2025,
  1T26, 2T26 e 1S26 e PL (controladora e total) e ativo total de seis datas (31/03/2025 a
  30/06/2026), do IFRS consolidado do BB (`relatorios/BBAS3/`). 38 valores, todos batem com o
  pipeline. O 4T25 é 2025 − 9M25 (o PDF só traz acumulados).
- ROE e "Lucro Líquido Ajustado" ficam de fora: são da base gerencial/BRGAAP do BB (lucro
  ajustado de R$ 20,7 bi em 2025 contra R$ 13,7 bi de lucro IFRS da controladora).
- `tests/test_golden.py`: BBAS3 em `CD_CVM`, `FINANCEIRAS` e `TOLERANCIA`.
- `relatorios/` reorganizado em `ITUB4/` e `BBAS3/` (fora do git); caminhos do ITUB4 no golden
  atualizados. `guia.md` 1.34.

### Carteira pessoal, Etapa C2: posição e preço médio (ADR 0020)
- `src/valuation/carteira/posicao.py` (puro): `calcular_posicoes` reproduz as transações até a
  data-base (preço médio ponderado com taxas; venda não muda o preço médio; desdobramento e
  agrupamento pelo fator; bonificação a custo zero; proventos líquidos de retenção) e `avaliar`
  aplica o fechamento de cada ticker: patrimônio, resultado não realizado, realizado e total
  (patrimônio + vendas + proventos − compras), com avisos de cotação ausente (totais parciais) ou
  defasada (> 5 dias).
- `valuation carteira posicao [--data-base] [--forcar]`: tabela Rich com totais e avisos; cotação
  pelo `preco_validado` (yfinance conferido na brapi), só dos papéis abertos.
- `tests/test_posicao.py` (13 testes): caso calculado à mão, identidade do resultado, avisos e o
  comando. Valuation (DCF, DDM, múltiplos) não mudou.

### Diagramas UML do projeto
- Conjunto completo de diagramas, um por assunto das aulas de UML (`diagramas/`), em Mermaid dentro
  de `docs/`: `diagrama_casos_de_uso.md` (atores, `«include»`, `«extend»`, especialização e a
  especificação dos casos principais), `diagrama_classes.md` (6 diagramas por camada e a hierarquia
  de exceções), `diagrama_objetos.md` (cenário do `rodar` com os valores reais dos testes
  sintéticos, perfil, cadastro e carteira), `diagrama_interacao.md` (sequência de `atualizar`,
  `perfil`, `carteira importar` e lotes; comunicação de `rodar` e `carteira lancar`),
  `diagrama_estados.md` (perfil, cache de download, validação cruzada, execução do `rodar`,
  importação da carteira e favoritos) e `diagrama_arquitetura.md` (pacotes, componentes e
  implantação). Os de atividades e de sequência do `rodar` já existiam.
- `docs/diagramas.md`: índice, rastreabilidade caso de uso → diagramas, notação e quando atualizar
  cada um. O grafo de pacotes foi extraído dos `import` reais; o `guia.md` (seção 19) dizia que
  `custo_capital` importa `config`, e ele não importa nenhum outro pacote (corrigido, guia 1.32).
- Só documentação: nenhum código nem teste mudou.

### Carteira pessoal, Etapa C1: transações e importação (ADR 0020)
- `src/valuation/carteira/`: `transacoes.py` (esquema, validação por tipo e do histórico: venda
  acima da posição, evento sem posição, data futura) e `arquivo.py` (leitura de CSV e XLSX, gravação
  só-acréscimo em `carteira/transacoes.csv`, tudo ou nada, com o número de cada linha inválida).
- `valuation carteira lancar` e `valuation carteira importar ARQUIVO` (`--formato-csv`,
  `--permitir-duplicadas`; reimportação do mesmo arquivo é recusada).
- Nova dependência `openpyxl` (autorizada no ADR 0020) e `types-openpyxl` (dev); `carteira/` no
  `.gitignore`; `CAMINHO_TRANSACOES` em `config.py`.
- 45 testes em `tests/test_carteira.py`, sem rede. Valuation (DCF, DDM, múltiplos) não mudou.

### Planejamento da carteira pessoal (ADR 0020)
- Escopo: RF-004, 007, 008, 009, 010, 011 e 012 do plano de requisitos, de forma plena. Nenhum
  código novo ainda.
- `docs/decisoes/0020-modulo-carteira-pessoal.md`: camada `carteira/`, transações em CSV local,
  preço médio, proventos com fonte a validar, alocação-alvo e `openpyxl` (nova dependência).
- `docs/backlog.md`, seção "Carteira pessoal": perguntas abertas (fonte de proventos, tecnologia
  da tela) e Etapas C1 a C6, com entregas.
- `CLAUDE.md` (seção 1): nota apontando o ADR 0020; o corpo da especificação não muda.
### Tickers favoritos e cache de resultados (ADR 0021, Etapa 8 do backlog)
### Golden do ITUB4 (seção 19, item 9 do `CLAUDE.md`, em parte)
- `tests/golden/referencias.yaml`: lucro (controladora e total) de 1T25, 1T26, 2T25, 2T26, 1S25 e
  1S26 e PL (controladora e total) e ativo total de 31/12/2025, 31/03/2026 e 30/06/2026, do IFRS
  consolidado do Itaú (`relatorios/`). Todos batem com o pipeline.
- `tests/test_golden.py` passou a conciliar financeiras (`financeiras.metricas`, plano `financeira`).
- BBAS3 ficou de fora neste momento: os PDFs do BB em `relatorios/` eram Cosif (BRGAAP); entrou depois (seção abaixo).

### Tickers favoritos e cache de resultados (ADR 0020, Etapa 8 do backlog)
- `config/favoritos.yaml` (lista de tickers) e `saida/favoritos.py`: carga/gravação e leitura do
  último `resumo.csv` de `saida/{TICKER}/` (o cache de resultados; nada novo é persistido).
- `valuation favoritos`: tabela com data-base, idade, perfil, preço, valor ponderado, preço máximo
  de compra, upside e avisos, sem rede. `favoritos adicionar|remover` e `favoritos atualizar
  [--max-idade-dias] [--forcar] [--sem-graficos]` (roda `rodar` só nos desatualizados).
- Testes em `tests/test_favoritos.py`.

### Setores como enum e execução por setor (ADR 0019)
- `src/valuation/universo.py`: enum `SetorCVM` (33 setores do `setor_cvm` de
  `config/universo_ibovespa.csv`), `carregar_universo`, `buscar_setor` (nome do membro ou texto
  da CVM, sem caixa/acento) e `empresas_do_setor`. Setor do CSV fora do enum ⇒ erro.
- `valuation setores [SETOR]`: lista os setores com o nº de empresas, ou as empresas de um setor.
- `valuation rodar-setor SETOR`: roda `rodar` em cada empresa do setor, em sequência; holdings
  são puladas; uma falha não interrompe as demais; tabela final e saída 1 se houver falha.
- Testes em `tests/test_universo.py` (enum × CSV, busca, comandos com `rodar` substituído).
- `uv run valuation` sem comando abre um menu interativo: setores numerados → empresas do setor →
  `rodar` da empresa escolhida (padrões do `rodar`); 0 volta ou sai.

### Glossário das métricas (Etapa 7 do backlog)
- `valuation glossario [TERMO]`: 37 termos (WACC, Ke, g, RONIC, VT/EV, múltiplos, hurdle…) com o
  que é, como se calcula e como ler; busca sem distinguir caixa, acento ou símbolos.
- `--explicar` em `wacc`, `comparar` e `rodar` (DCF e DDM) imprime a legenda dos termos mostrados;
  o modo padrão continua sucinto.
- `meta.json` ganha a chave `glossario` (dicionário de dados). Código em `saida/glossario.py`.
- Fica de fora: legendas nos PNG e GUI.

### ERP implícito do Ibovespa (ADR 0018, Etapa 6 do backlog)
- `valuation erp`: dividendos e market cap agregados do universo, crescimento nominal do Focus
  (PIB real + IPCA) nos 5 primeiros anos e CAGR histórico (teto 5%) na perpetuidade, sem
  convergência; resolve o `ke` do mercado e `ERP = ke − Rf`, com faixa de ±1 p.p. no g perpétuo.
  Grava `data/processed/erp_implicito.json`; recusa (sai com 1, sem gravar) ERP fora de [0%, 15%].
- `custo_capital.erp` virou `{fonte: manual | implicito_ibovespa, valor, anos_explicitos, faixa_g,
  validade_dias}` (número solto continua valendo como `manual`); `_erp_efetivo` lê o JSON no `Ke`.
- `Macro.pib_esperado` (Focus `PIB Total`, validado na API real); `_macro` extraído de `_mercado`.
- **Resultado em 30/10/2026: ERP implícito de −4,2%** (ke do mercado 10,8% contra NTN-F de 15,0%),
  então o `settings.yaml` segue `manual` (5,0%). Detalhes no ADR 0018 e em `docs/fontes.md`.

### Kd manual da PETR4
- `config/empresas/PETR4.yaml`: `custo_capital.kd` manual de 15,60% (Rf 15,00% + spread de 0,60%
  do guia `kd_petrobras.md`). Valor ponderado do perfil moderado: R$ 43,36 → R$ 42,79 (−1,3%).
- ADR 0017; `docs/fontes.md` (premissa do usuário); `guia.md` 1.25; backlog (Etapa 3 feita).

### Fase 9 concluída (saídas completas)
- `valuation rodar` (DCF e DDM) grava também `meta.json` (versão e commit do código, comando,
  perfil, moeda, fontes com URL/data/sha256 da CVM, hash das contas padronizadas, avisos),
  `premissas_usadas.yaml`, `qa.json`, `historico.csv` (exercícios e LTM) e `valores_reais.csv`
  (fluxos e valor terminal deflacionados pelo IPCA do Focus; taxas nominal e real).
- Gráficos PNG em PT-BR (`saida/graficos.py`, `Figure` sem `pyplot`): `football_field.png`
  (modelo, faixa da sensibilidade, múltiplos P25–P75, 52 semanas, preço atual e preço máximo),
  `ponte_ev_equity.png` (só DCF), `sensibilidade_heatmap.png` e o da segunda matriz,
  `historico_vs_projecao.png` e `composicao_valor.png`. Flag `--sem-graficos`.
- ADR 0016; `guia.md` 1.24; diagrama de atividades, README, backlog e ✅ da Fase 9 no `CLAUDE.md`.
- Testes: `test_real.py`, `test_saida_arquivos.py`, `test_graficos.py` e novas asserções em
  `test_cli.py` (454 testes; `saida/` com 100% de cobertura).

### Documentação para Agentes de IA
- Criação do `docs/contexto_rapido.md` (cheatsheet que indica o que ler por tipo de tarefa) e
  mensagens de g >= WACC / g >= Ke em `dcf.py` e `ddm.py` com a ação sugerida (`economizar.md`).
- Criação do `tests/README.md` (Guia de Mocks, Fixtures e Testes Rápidos) com orientações sobre comandos cirúrgicos de teste, política estrita de zero acesso à rede e exemplos de dados sintéticos.
- Adição da função helper `criar_empresa_sintetica` em `tests/sintetico.py` para geração de demonstrações sintéticas completas multi-anuais no padrão CVM.
- Criação do diagrama de atividades UML em `docs/diagrama_atividades.md` mapeando o fluxo completo do pipeline (CLI, ingestão, DCF/DDM, sensibilidade e saídas).
- Criação de playbooks operacionais em `docs/recipes_agentes.md` com 7 procedimentos passo a passo determinísticos (nova empresa, métricas contábeis, parâmetros de configuração, múltiplos, testes golden e diagnóstico de erros).
- Criação de regras modulares em `docs/regras/` para orientar agentes com contexto delimitado (e índice `docs/regras/README.md`):
  - `docs/regras/REGRAS_DADOS.md`: adaptadores, scrapers, APIs, cache e escalas.
  - `docs/regras/REGRAS_CONTABIL.md`: padronização contábil, planos de contas, IFRS 16 e QA.
  - `docs/regras/REGRAS_MODELOS.md`: funções puras, DCF/DDM, custo de capital e sanidade econômica.
  - `docs/regras/REGRAS_TESTES.md`: mocks, dados sintéticos, golden tests e proibição de rede.
- `CLAUDE.md`: referenciamento das regras modulares na seção 0 (regras 14 e 15) e nas seções 6, 7, 11 e 15 apontando para `docs/regras/`.
- `CONTRIBUTING.md`, `README.md` e `guia.md`: referências atualizadas para `docs/regras/`; versão do `guia.md` atualizada para 1.19.

### Fase 10 concluída
- Critério de pronto atendido: pipeline completo para ITUB4 e BBAS3 com checagem DDM × lucro
  residual; cobertura de 96% (todas as camadas acima de 80%). Pendentes com o usuário: golden das
  financeiras e a divisão do setor `seguradoras` (seção 19 do `CLAUDE.md`, itens 9 e 10).
- `guia.md` 1.23.

### Fase 10 — YAMLs das financeiras
- `config/empresas/`: ITUB4, BBAS3, BBDC4, SANB11, BPAC11 (setor `bancos`) e BBSE3, CXSE3, PSSA3,
  IRBR3 (setor `seguradoras`), gerados por `premissas sugerir --escrever`; `rodar` conferido nos
  nove (lucro residual igual ao DDM em todos).
- `guia.md` 1.22: ressalva do setor `seguradoras` (holdings × operadoras).

### Fase 10 — Units no market cap
- `fix`: papel avaliado pela unit (SANB11, BPAC11) tem o valor por ação contado em units, comparável
  ao preço da unit (antes saía por ação, 2 a 3 vezes menor).
- `data/cadastro.py`: coluna opcional `acoes_por_unit` no cadastro manual e em `ClasseAcao`.
- `data/precos.py`: unit cotada com composição conhecida precifica ON e PN (preço da unit / ações
  por unit).
- `config/cadastro_manual.csv`: BPAC11 e BRBI11 (3 ações por unit) e SANB11 (2); BPAC11 e BRBI11
  entram nos pares de bancos.
- ADR 0015; `guia.md` 1.20.

### Fase 10 — Financeiras: múltiplos e pares
- `modelos/multiplos.py`: `fundamentos_financeira`, `MULTIPLOS_FINANCEIRA` (P/L, P/VP, DY),
  regressão P/VP × ROE (`regressao_pvp_roe`, `valor_regressao`).
- `config/setores.yaml`: setores `bancos` e `seguradoras`; `cadastro_manual.csv`: escala de ações
  de Santander, Banrisul, Mercantil, BNB e Mercantil Investimentos.
- CLI: `comparar` e `rodar` de financeiras medem os pares (ROE na tabela, regressão no terminal e
  `valor_regressao_pvp_roe` no `resumo.csv`).
- ADR 0014; `guia.md` 1.15.

### Fase 10 — Financeiras: DDM, Ke, cenários e sensibilidade
- `modelos/ddm.py`: DDM em dois estágios (dividendos descontados no fim de cada ano, ano corrente
  parcial, valor terminal pelo P/VP justificado) e checagem por lucro residual, que coincide com
  o DDM por construção.
- `custo_capital/wacc.py`: Ke das financeiras (`CustoCapitalFinanceira`, `tabela_financeira`),
  sem Kd nem WACC; beta por comparáveis sem Hamada.
- `analise/cenarios.py`: resultado genérico (FCFF ou DDM) e `analisar_ddm` com o Ke implícito no
  preço.
- `analise/sensibilidade.py`: matrizes Ke × g e ROE de longo prazo × Ke.
- `settings.yaml`: `sensibilidade.roe_passo` e `roe_faixa`.
- CLI: `wacc` e `rodar` de financeiras (`resumo.csv` com P/VP justificado e lucro residual,
  `sensibilidade_ke_g.csv`, `sensibilidade_roe_ke.csv`).
- ADR 0013; `guia.md` 1.14.

### Fase 10 — Financeiras: premissas e projeção do DDM
- `projecao/premissas.py`: `projecao` e `cenarios` com esquema conforme o `tipo_modelo`
  (financeira: ROE em trajetória ou lista, `payout_inicio`, `terminal.g_nominal`, `roe_pp`).
- `projecao/financeira.py`: ROE da mediana de 5 anos até o de longo prazo (mediana de 10 anos,
  decisão do usuário), payout até 1 − g/ROE_LP, cenários de ±1 desvio-padrão do ROE e projeção de
  lucro, dividendos e PL a partir do PL da controladora do último balanço.
- `projecao/escrita.py`: YAML comentado das financeiras.
- CLI: `premissas sugerir` de financeiras (sugestões × histórico, projeção, `--escrever`).
- ADR 0012; `guia.md` 1.13.

### Fase 10 — Financeiras: plano de contas e métricas
- `config/mapeamento_contas.yaml`: seção `financeira:` por regex de descrição, conferida em 25
  bancos e seguradoras (planos de bancos, de seguradoras e comercial; demonstrações individuais).
- `contabil/financeiras.py`: lucro e PL da controladora, ROE sobre o PL inicial, ROA, payout,
  dividendos pagos, alavancagem e alíquota efetiva, anuais e LTM.
- `contabil/qa.py`: verificações próprias das financeiras (balanço, PL positivo, atribuição do
  lucro, saltos).
- `contabil/padronizacao.py`: documento que informa um período só com zeros não substitui outro
  (balanço de 2024 zerado nos ITR 2025 de BAZA3, BNBR3, BGIP4, BPAR3 e BMIN4).
- CLI: `qa`, `historico` e `cobertura` aceitam financeiras; companhia sem consolidado usa as
  individuais com aviso; holdings recebem mensagem própria.
- `config/cadastro_manual.csv`: WIZC3 e QUAL3 (corretoras) como `nao_financeira`.
- ADR 0011; `guia.md` 1.12.

### Justificativas e alternativas
- `docs/justificativas_e_alternativas.md`: justificativa de cada decisão (dados, contabilidade,
  premissas, custo de capital, DCF, múltiplos, perfil), alternativas com o custo de implementar e
  roteiro de análises diferentes.

### ERP e backlog
- `custo_capital.erp` mantido em 5,0% como premissa do usuário (sem fonte externa), registrado em
  `docs/fontes.md` com a sensibilidade e a checagem pelo yield spread do Ibovespa (−5,5 p.p.,
  só contexto).
- `docs/backlog.md`: ordem de prioridade (Fase 9, Kd da PETR4, ERP implícito do Ibovespa).
- `guia.md` 1.11.

### Universo do Ibovespa e pares da mineração
- `config/cadastro_manual.csv`: `escala_acoes` 1000 para outras 19 companhias do universo (23
  tickers; ITUB4, ABEV3, AXIA3 etc.), detectadas pela razão entre as ações da CVM e a quantidade
  teórica da B3. Sem isso o market cap saía 1.000 vezes menor.
- `config/universo_ibovespa.csv`: 76 ativos da carteira de 30/10/26 da B3 (`ticker;cnpj;setor_cvm;
  tipo_modelo`); `valuation atualizar --tudo` passa a funcionar.
- `config/cadastro_manual.csv`: BPAC11, CEAB3 e MBRF3, que o FCA não resolvia.
- `config/setores.yaml`: CSNA3 entra nos pares de `mineracao`.
- ADR 0010; `guia.md` 1.9.

### Fase 8 — Múltiplos e comparáveis
- `config/setores.yaml`: pares por setor (decisão do usuário): `petroleo_gas` só E&P (PETR4,
  PRIO3, RECV3, BRAV3), `mineracao` (VALE3, CMIN3, CBAV3) separada do novo setor `siderurgia`
  (GGBR4, GOAU4, USIM5, CSNA3) e `maquinas_equipamentos` (WEGE3 e nove pares).
- `config/cadastro_manual.csv`: CSNA3 e CMIN3 (o FCA traz o código CVM no lugar do ticker) e
  `escala_acoes` 1000 para CBAV3, EMBJ3, RAPT3/4, TUPY3, KEPL3, MYPK3 e FRAS3.
- `modelos/multiplos.py`: P/L, EV/EBITDA, EV/EBIT, EV/Receita, P/VP, EV/FCF e dividend yield
  LTM com o mesmo pipeline contábil para alvo e pares (EV inverso da ponte, EBITDA ajustado);
  descarte de indefinidos, winsorização 10/90, mediana/média/quartis, baixa confiança com menos de
  3 pares, exclusão de par com P/VP implausível (escala das ações) e valor por ação implícito do
  alvo em P25, mediana e P75.
- `modelos/dcf.py`: g implícito num múltiplo de saída (`g_implicito`).
- `modelos/ponte.py`: minoritários pelo P/VP mediano dos pares (`multiplo_pvp`).
- `custo_capital`: estrutura-alvo do setor (mediana de D/(D+E) dos pares); beta por comparáveis
  ligado aos pares medidos.
- `settings.yaml`: seção `multiplos` (`min_pares`, `winsorizar`).
- CLI: `valuation comparar TICKER` (grava `multiplos_pares.csv` e `multiplos_implicitos.csv`);
  `atualizar --com-pares`; `rodar` mede os pares, grava os mesmos CSVs, mostra o valor implícito e
  o g implícito no EV/EBITDA dos pares e acrescenta ao `resumo.csv` o valor pela mediana de cada
  múltiplo, o número de pares, o EV/EBITDA mediano e o g implícito.
- ADR 0009; `guia.md` 1.7 e 1.8.

### Fase 7 — DCF, ponte, sensibilidade e cenários
- `modelos/dcf.py`: DCF do FCFF com ano corrente parcial e convenção de meio período, valor
  terminal por value driver (RONIC = WACC, ROIC histórico ou número), EV/EBITDA implícito no
  terminal, aviso de VT/EV e erros de WACC/RONIC ≤ g; `avaliar` (projeção → DCF → ponte) puro.
- `modelos/ponte.py`: ponte EV → equity → valor por ação (dívida bruta, caixa, minoritários
  contábeis, coligadas, `divida_extra`, ações em circulação) com o balanço dos pesos do WACC.
- `analise/cenarios.py`: cenários pessimista/base/otimista ponderados pelo perfil, preço máximo de
  compra, upside, Ke implícito no preço (contra o hurdle) e WACC implícito; mensagem neutra.
- `analise/sensibilidade.py`: matrizes WACC × g e margem EBITDA × crescimento.
- `saida/csv.py`: `gravar_matriz`.
- `settings.yaml`: teto do g terminal em 5,0% (decisão do usuário) e eixos de margem e
  crescimento da sensibilidade.
- CLI: `valuation rodar TICKER [--cenario] [--perfil] [--data-base] [--saida] [--formato-csv]
  [--forcar]`, que grava `resumo.csv`, `wacc.csv`, `projecao_{cenario}.csv`,
  `ponte_ev_equity.csv` e `sensibilidade_*.csv`; `premissas sugerir` e `rodar` compartilham a
  montagem das sugestões.
- `config/empresas/*.yaml` regenerados (comentário do g terminal).
- ADR 0008; `guia.md` 1.6.

### Fase 6 — Custo de capital
- `custo_capital/beta.py`: regressão OLS semanal (260 semanas, `adj_close`) contra o Ibovespa com
  erro-padrão, R² e avisos de R² baixo, janela incompleta e baixa liquidez; Blume; Hamada
  (desalavancar/realavancar); beta por comparáveis (mediana desalavancada) e manual; escolha da
  classe de ação mais líquida.
- `custo_capital/capm.py`: Ke `brl_direto` (sem risco-país sobre a NTN-F) e `usd_crp` com
  conversão por Fisher; empresa que reporta em USD usa `usd_crp`.
- `custo_capital/kd.py`: Kd histórico (despesas financeiras / dívida bruta média, mediana de 3
  exercícios) limitado a Rf + faixa, ou manual.
- `custo_capital/wacc.py`: estrutura de capital (mercado atual ou alvo manual, com beta
  realavancado), WACC, checagem WACC > g e tabela de componentes.
- `saida/csv.py`: CSV no formato do `settings.csv` (pt-BR) ou internacional.
- `settings.yaml`: `custo_capital.kd` (faixa do Kd) e `estrutura_alvo.divida_sobre_capital`.
- CLI: `valuation wacc TICKER [--data-base] [--forcar] [--saida] [--formato-csv]`, que grava
  `saida/{TICKER}/{data}/wacc.csv`; `mercado` passa a usar a mesma coleta (`_mercado`).
- ADR 0007; `guia.md` 1.5.

### Fase 5 — Premissas e projeção
- `contabil/nao_financeiras.py`: ajustes `caixa_extra` (contas somadas ao caixa e à redução da
  dívida líquida) e `divida_extra` (métrica à parte, para a ponte EV → equity).
- `projecao/premissas.py`: esquema pydantic de `config/empresas/{TICKER}.yaml` (seção 9.1), com
  `sugerido`, número ou lista por ano, campo novo `arrendamento_sobre_receita`, conferência com o
  cadastro e conversão dos ajustes para a camada contábil.
- `projecao/sugestor.py`: premissas a partir dos exercícios encerrados (crescimento da mediana de
  5a ao g terminal, margem EBITDA ajustada com reversão de metade à mediana de 10a, razões sobre a
  receita, alíquota, deltas dos cenários de ±1 desvio-padrão) com a origem de cada uma; aviso
  para setor de commodity.
- `projecao/projetor.py`: anos projetados com ano-ponte e fração do ano corrente, resolução das
  premissas, cenários pessimista/otimista e projeção pura de receita a FCFF (ΔNWC incremental,
  arrendamento como reposição se IFRS 16 = dívida).
- `projecao/escrita.py`: YAML da empresa regenerado com o valor sugerido e a origem em comentário.
- `config/setores.yaml` (`commodity`, `tipo_modelo`, pares vazios) e
  `config/empresas/{PETR4,VALE3,WEGE3}.yaml`.
- CLI: `valuation premissas sugerir TICKER [--escrever] [--perfil] [--data-base]`; `qa`,
  `historico` e `premissas` passam a ler o YAML da empresa (mapeamento extra, consolidado, moeda,
  ajustes).
- ADR 0006; `guia.md` 1.3 e 1.4.

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
