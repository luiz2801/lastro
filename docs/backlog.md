# Backlog

Itens fora do roadmap das fases (seção 17 do `CLAUDE.md`), registrados para depois.

## Ordem de prioridade (decidida em 2026-10-30)

Em andamento por escolha do usuário: **Fase 10 (financeiras)**. Feito (commits ef24c7a a
8073b23, ADRs 0011–0014): plano de contas, métricas e QA; premissas e projeção do DDM; DDM com
lucro residual, Ke, cenários e sensibilidade; múltiplos e pares (`bancos`, `seguradoras`).
**Falta para fechar a Fase 10:**

1. **Units no market cap** (`data/precos.market_cap`): BPAC11 (1 ON + 2 PN) e BRBI11 viram "par
   ignorado". Sugestão: composição da unit no cadastro manual e preço por ação = preço da unit /
   ações por unit (BPAC3/BPAC5 cotam com preço defasado). Exige ADR (0015) e testes.
2. **YAMLs das financeiras**: `valuation premissas sugerir {T} --escrever` para ITUB4, BBAS3,
   BBDC4, SANB11, BPAC11, BBSE3, CXSE3, PSSA3 e trocar `pares.setor: null` por `bancos` ou
   `seguradoras`; depois `valuation rodar` em cada um e conferir.
3. **Seguradoras**: rodar `comparar`/`rodar` de BBSE3, CXSE3, PSSA3, IRBR3 (BBSE3/CXSE3 são
   holdings de seguros; conferir se o DDM faz sentido) e registrar ressalvas (float, sinistralidade).
4. **Golden das financeiras**: pedir ao usuário a conferência de lucro, PL e ROE de ITUB4 e BBAS3
   com os releases (`tests/golden/referencias.yaml`). CVM traz IFRS consolidado (Itaú 2025: lucro
   da controladora 44.857 mi, PL da controladora 204.501 mi).
5. **Fechamento**: seções 1, 12 e 14 do `guia.md` (contagem de testes: 441, 430 passam), README
   (Estado atual: Fase 10 concluída), ✅ na seção 17 do `CLAUDE.md`, nota do ADR 0014 no README,
   `make cobertura`.

Resultado preliminar (30/10/2026, perfil moderado): ITUB4 R$ 18,86 ponderado × preço R$ 39,15
(Ke 20,1%, ROE_LP 19,4%, Ke implícito 13,0%); BBAS3 R$ 19,51 × R$ 16,59.

Depois, nesta ordem:

1. ✅ **Fase 9 — Saídas** (roadmap; ADR 0016): gráficos (football field com os quartis dos múltiplos, cascata
   da ponte, heatmap, histórico × projeção, composição do valor), `meta.json`,
   `premissas_usadas.yaml`, `qa.json`, `historico.csv`, `valores_reais.csv`, `--sem-graficos`.
2. ✅ **Kd da PETR4** (ADR 0017, Rf + 0,60% = 15,60%): fixar `custo_capital.kd: {metodo: manual, valor: ...}` no YAML dela. O piso
   do Kd na Rf muda o valor em até 18% (Kd histórico cru de 7,8% contra 14,87%): o Kd histórico
   mistura juros em dólar com variação cambial. Precisa de um valor escolhido pelo usuário.
3. ✅ **ERP implícito do Ibovespa em BRL** (ADR 0018, implementado; resultado de 30/10/2026: −4,2%, então o padrão segue `manual`): ver abaixo.
4. Demais itens desta página (outras empresas, preço teto, explicação de métricas, GUI, recomendação).

## ERP implícito do Ibovespa em BRL

✅ Implementado (ADR 0018): `valuation erp`, `custo_capital/erp_implicito.py`, `custo_capital.erp.fonte`.
Resultado de 30/10/2026: **ERP implícito de −4,2%**, que o comando recusa; o padrão segue `manual`
(5,0%). Para o implícito virar utilizável, o que mudaria o resultado (cada um exige ADR novo):

- Fluxo por **lucro** (ou FCFE) em vez de dividendos, para não deprimir o `ke` com o payout: o
  earnings yield (9,4%) ainda deixa o yield spread negativo contra a NTN-F de 15%.
- Incluir **recompras** (conta da DFC sem mapeamento hoje).
- Rf **real** (NTN-B) com fluxos reais, em vez da NTN-F nominal.
- Esperar uma Selic menor: com a NTN-F em 15%, qualquer método por fluxo do índice tende a ficar
  perto de zero.
- O yield spread (earnings yield − NTN-F) segue como termômetro de contexto no `mercado` (hoje:
  −5,5 p.p., em `docs/fontes.md`), nunca como insumo do Ke.

## Rodar o valuation em outras empresas

Hoje o escopo são os pilotos PETR4, VALE3 e WEGE3. Para outras companhias da B3:

- Criar `config/empresas/{TICKER}.yaml` para cada uma (o motor é o mesmo; só o YAML muda).
- Usar o universo de `config/universo_ibovespa.csv`, atualizado a cada quadrimestre.
- Empresas financeiras dependem da Fase 10. Holdings e FIIs ficam fora da v1 (seção 1 do `CLAUDE.md`).
- Modo em lote (`valuation rodar --tickers ...` ou `--tudo`) e screening ficam na Fase 11,
  que só entra se o usuário pedir.

## Interface gráfica (GUI)

Hoje tudo é pela CLI. A seção 1 do `CLAUDE.md` deixa interface web fora da v1, então isto entra
só depois da v1 (ou antes, com uma decisão registrada em ADR).

- Telas candidatas: histórico e QA da empresa, edição das premissas com a sugestão ao lado,
  projeção por cenário, resultado do valuation (football field, sensibilidade) e perfil.
- Deve ser só uma camada por cima do motor: chama as mesmas funções puras e lê os mesmos YAMLs,
  sem lógica de cálculo própria.
- Escolha da tecnologia em aberto (app web local, como Streamlit, ou desktop). Dependência nova
  exige ADR (seção 4 do `CLAUDE.md`).
- Melhor depois da Fase 9, quando as saídas (CSVs e gráficos) estiverem prontas para serem
  reaproveitadas.

## Métrica de preço teto

Definir antes de implementar qual "preço teto" se quer:

- **Preço teto de Bazin**: dividendos por ação médios (ex.: últimos 3 a 5 anos) / dividend yield
  mínimo exigido (Bazin usa 6%). Usa `dividendos_pagos` do histórico e a quantidade de ações; o
  yield mínimo seria parâmetro do `settings.yaml` (talvez por perfil). Faria sentido sobretudo para
  pagadoras de dividendos e financeiras.
- **Preço máximo de compra do perfil** (valor justo ponderado × (1 − margem de segurança)): já está
  previsto na seção 8.4 do `CLAUDE.md` e entra na Fase 7. Se for este, basta exibi-lo com o nome
  "preço teto".
- Em qualquer caso: coluna em `resumo.csv`, linha vertical no football field e comparação com o
  preço de mercado.

## Explicação do significado das métricas exibidas (glossário / legendas)

Ao exibir métricas nos comandos de tela e relatórios (tabelas Rich da CLI, saídas da Fase 9 e
eventual GUI), mostrar também de forma didática o que **todas** as métricas levadas em consideração
significam, sua fórmula/origem e como interpretá-las no contexto de valuation:

### 1. Métricas de Valuation e Modelagem (DCF, DDM, Cenários)
- **WACC** (*Weighted Average Cost of Capital*): custo médio ponderado de capital; taxa de desconto
  mínima exigida pelos fornecedores de capital (credores e acionistas) para remunerar o risco dos ativos operacionais.
- **g** (taxa de crescimento na perpetuidade): taxa estimada de expansão a longo prazo dos fluxos de
  caixa, ancorada nas projeções macroeconômicas de longo prazo (PIB + inflação da moeda de reporte).
- **RONIC** (*Return on New Invested Capital*): retorno sobre o novo capital investido na perpetuidade;
  mede a eficiência marginal com que novos investimentos geram lucros futuros e define a taxa de
  reinvestimento terminal (`g / RONIC`).
- **FCFF** (*Free Cash Flow to Firm*): fluxo de caixa livre da firma; caixa gerado pelas operações
  disponível a todos os provedores de capital após investimentos operacionais e impostos.
- **FCFE / Projeção de Dividendos**: fluxo de caixa disponível para os acionistas (usado no DDM das
  instituições financeiras).
- **Valor Terminal (VT)** e **VT / EV**: valor presente dos fluxos perpétuos além do horizonte explícito
  e sua proporção frente ao valor total da firma (termômetro de sensibilidade e incerteza).
- **EV** (*Enterprise Value* / Valor da Firma): valor presente operacional total do negócio (soma do
  VP dos fluxos explícitos + VP do VT).
- **Equity Value** (Valor do Patrimônio Líquido): valor atribuível aos acionistas após ajuste da ponte
  (EV ajustado por caixa, dívida e passivos).
- **Valor Justo por Ação** e **Valor Ponderado**: valor por ação resultante do modelo e sua média
  ponderada pelos pesos dos cenários definidos no perfil do investidor.
- **WACC Implícito** e **Ke Implícito**: taxas de desconto que igualam o valor justo ao preço atual de
  mercado (mostram qual taxa de retorno o mercado está precificando).
- **Lucro Residual**: geração de valor além do custo de oportunidade do capital próprio no DDM
  (`Lucro Líquido − Ke × PL`).
- **Margem de Segurança** e **Preço Máximo de Compra**: desconto exigido pelo perfil de risco sobre o
  valor justo ponderado (`Valor Justo × (1 − margem)`).

### 2. Custo de Capital (CAPM, Dívida e Estrutura)
- **Rf** (taxa livre de risco): remuneração de ativo soberano de longo prazo sem risco de calote
  (ex.: títulos do Tesouro / NTN-F).
- **ERP** (*Equity Risk Premium*): prêmio de risco adicional exigido por investir em ações em vez de
  renda fixa soberana.
- **Beta ($\beta$)**: sensibilidade sistemática do retorno da ação frente ao mercado (desalavancado pelos
  pares e realavancado pela estrutura da empresa).
- **CRP** (*Country Risk Premium*): prêmio de risco país somado quando se utiliza taxa base internacional.
- **Ke** (custo do capital próprio): retorno mínimo anual exigido pelos acionistas, estimado pelo CAPM.
- **Kd** (custo da dívida bruto e líquido): taxa média de juros paga sobre empréstimos e seu custo
  efetivo após benefício fiscal (`Kd × (1 − t)`).
- **Pesos da Estrutura de Capital** ($D/(D+E)$ e $E/(D+E)$): proporção da dívida bruta e do equity a
  valor de mercado no balanço da empresa.
- **Alíquota Marginal/Operacional ($t$)**: alíquota nominal ou efetiva de IR/CSLL para o cálculo do
  benefício fiscal dos juros.

### 3. Métricas Contábeis e Operacionais (Não Financeiras)
- **Receita Líquida**: receita operacional após deduções de vendas, devoluções e impostos indiretos.
- **EBIT Contábil e EBIT Ajustado**: resultado operacional antes de juros e tributos; o ajustado expurga
  não recorrentes e equivalência patrimonial (quando coligadas entram na ponte).
- **D&A**: despesas de depreciação e amortização do período.
- **EBITDA e EBITDA Ajustado**: lucro antes de juros, tributos, depreciação e amortização; aproximação
  da geração bruta de caixa das operações.
- **Margem EBITDA** e **Margem EBIT**: eficiência operacional bruta sobre a receita líquida.
- **NOPAT** (*Net Operating Profit After Tax*): lucro operacional desprovido de alavancagem financeira,
  tributado pela alíquota operacional.
- **Capex**: investimentos em bens de capital (imobilizado e intangível) para manutenção e expansão.
- **NWC** (*Net Working Capital*) e **ΔNWC**: capital de giro operacional líquido (ativos operacionais −
  passivos operacionais) e a sua variação de caixa consumida/liberada no exercício.
- **CFO** (Fluxo de Caixa Operacional) e **FCF Caixa**: geração de caixa das atividades operacionais
  declarada na DFC e saldo livre após capex contábil.
- **Dívida Bruta, Caixa & Aplicações e Dívida Líquida**: saldo de financiamentos e arrendamento (IFRS 16),
  deduzido de disponibilidades e equivalentes.
- **Alavancagem (Dívida Líquida / EBITDA)**: múltiplos de capacidade de solvência e cobertura de dívida.
- **ROIC** (*Return on Invested Capital*): retorno percentual sobre o capital investido operacional médio
  (`NOPAT / Capital Investido`), medindo o poder de geração de valor da atividade.
- **Alíquota Efetiva vs. Alíquota Operacional**: relação real do IR/CSLL sobre o LAIR versus a alíquota
  aplicada sobre o EBIT operacional (limitada à nominal).

### 4. Métricas Contábeis de Financeiras (Bancos e Seguradoras)
- **Lucro Líquido da Controladora**: resultado líquido final atribuível aos detentores do capital da holding.
- **Patrimônio Líquido da Controladora**: capital próprio dos acionistas (excluídos minoritários).
- **ROE** (*Return on Equity*): rentabilidade do capital dos acionistas (`Lucro Líquido / PL inicial`).
- **ROA** (*Return on Assets*): rentabilidade sobre os ativos totais administrados pela instituição.
- **Alavancagem de Balanço (Ativo / PL)**: multiplicador do capital próprio na intermediação financeira.
- **Dividendos Pagos e Payout**: volume de proventos distribuídos e porcentagem do lucro repassada aos acionistas.
- **ROE de Longo Prazo (ROE_LP)** e **Payout de Longo Prazo**: rentabilidade e taxa de distribuição
  sustentáveis na perpetuidade.

### 5. Itens da Ponte de Valor (EV → Equity)
- **Caixa e Aplicações Financeiras** (incluindo caixa extra identificado nas notas).
- **Dívida Bruta** (empréstimos e financiamentos CP/LP + arrendamento mercantil IFRS 16).
- **Participação de Não Controladores (Minoritários)**: parcela do PL de subsidiárias não detida pela controladora.
- **Investimentos em Coligadas/Associadas**: valor contábil de participações somado na ponte quando
  descontado do resultado operacional.
- **Passivos Extras (Dívida Extra)**: provisões para litígios/contingências e obrigações atuariais de
  planos de pensão deduzidos do valor do acionista.

### 6. Múltiplos de Mercado e Comparáveis
- **P/L** (*Price to Earnings* / Preço sobre Lucro): relação entre a cotação e o lucro líquido por ação.
- **P/VP** (*Price to Book* / Preço sobre Valor Patrimonial): relação entre o valor de mercado e o patrimônio líquido.
- **EV/EBITDA** e **EV/EBIT**: valor da firma sobre o resultado operacional (independente da estrutura de capital).
- **EV/Receita** e **EV/FCF**: valor da firma sobre faturamento e sobre fluxo de caixa livre.
- **Dividend Yield**: rendimento de dividendos dos últimos 12 meses sobre a cotação atual da ação.
- **Percentis de Comparáveis (P25, Mediana, P75)**: métricas estatísticas dos pares setoriais para
  estimar a faixa de valor implícito.
- **Regressão P/VP × ROE**: calibração estatística do múltiplo patrimonial justo em função da rentabilidade do banco.

### Requisitos de Implementação e Apresentação
- **CLI**:
  - Parâmetro global ou de comando `--explicar` / `--glossario` (ou comando dedicado `valuation glossario [METRICA]`).
  - Notas de rodapé / legendas (`caption` ou painel explicativo do Rich) nas tabelas que usam siglas e termos técnicos.
  - Modo padrão sucinto mantido para agilidade, com explicações contextuais ativáveis pelo usuário.
- **Fase 9 (Saídas & Relatórios)**:
  - Documentação embutida em `meta.json` e arquivo de dicionário de dados gerado junto aos relatórios.
  - Tooltips e legendas descritivas nos gráficos (ex.: football field, sensibilidade, cascata da ponte).
- **Interface Gráfica (GUI)**:
  - Tooltips informativos ao passar o mouse sobre cada cabeçalho de coluna, sigla ou gráfico.

## Tickers favoritos e cache local

Criar um mecanismo de watchlist (tickers favoritos) para agilizar o uso cotidiano:

1. **Lista de favoritos** (`config/favoritos.yaml` ou campo em `settings.yaml`): lista de tickers
   marcados pelo usuário. Exige decisão de formato (YAML simples vs. seção em `settings.yaml`);
   registrar em ADR quando implementado.
2. **Aba / view de favoritos na GUI**: quando a interface gráfica for implementada (ver seção
   "Interface gráfica"), exibir os favoritos em destaque — tabela resumida com preço, valor justo
   ponderado, upside e data da última avaliação.
3. **Cache local dos dados dos favoritos** (JSON ou parquet agregado): pré-baixar e serializar os
   dados de mercado (preço, macro, market cap) e os resultados do `rodar` para os tickers
   favoritos, eliminando a rede como gargalo nas consultas rotineiras. Ponto de atenção: definir
   TTL e estratégia de invalidação (flag `--atualizar-favoritos`); o cache de dados brutos CVM
   já existe em `data/raw/` — o que falta é um snapshot dos resultados calculados (ex.:
   `saida/{TICKER}/{data}/resumo.json`).

## Monte Carlo em C++

Quando a Fase 11 for iniciada, avaliar a implementação de simulação Monte Carlo para o DCF em C++:

- **Motivação**: simulações com dezenas de milhares de trajetórias (distribuições de WACC, g,
  margem e crescimento correlacionadas) tornam o gargalo a CPU, não a rede — contexto em que
  C++ se justifica.
- **Integração sugerida**: extensão Python via `pybind11` ou `cffi`, mantendo a CLI e a lógica
  de negócio em Python; só o núcleo de simulação migra para C++.
- **Pré-requisito**: definir a distribuição de cada variável de entrada (normal? triangular?
  bootstrap do histórico?) e o que a saída representa (distribuição do valor por ação, VaR do
  upside). Registrar em ADR antes de implementar.
- **Alternativa de curto prazo**: `numpy`/`scipy` com vetorização (ex.: `np.random` em lote)
  é suficiente para até ~100 k trajetórias sem C++.

## Recomendação (compra / venda)

- Definir os critérios: por exemplo, faixas de upside contra o preço teto/preço máximo, retorno
  esperado contra o hurdle do perfil e confiança (avisos de QA, poucos pares, VT/EV alto).
- Manter o aviso de que é uso pessoal e não constitui recomendação de investimento.

---

## Ordem de implementação incremental (adicionada em 2026-10-30)

Raciocínio: cada etapa entrega algo utilizável de imediato e não bloqueia nada que vem depois.
A sequência respeita as dependências do roadmap (seção 17 do `CLAUDE.md`) e agrupa os itens do
backlog por valor entregue ao usuário.

### Etapa 1 — Fechar a Fase 10 (pendências imediatas)

Pré-requisito para qualquer trabalho posterior em financeiras e para a consistência dos testes.

1. ✅ **Units no market cap** (ADR 0015): `e2196ed` e `0bd81df` (valor por unit).
2. ✅ **YAMLs das financeiras**: `730a9a2`, nove arquivos em `config/empresas/` com o setor.
3. ✅ **Rodar e conferir seguradoras**: rodadas sem erro; ressalva do setor em `guia.md` (armadilha 38).
4. **Golden das financeiras**: solicitar ao usuário os números de ITUB4 e BBAS3; codificar em
   `tests/golden/referencias.yaml`.
5. ✅ **Fechamento formal**: `16524f8` (`CLAUDE.md`, `README.md`, `guia.md`, CHANGELOG); cobertura de 96%.

*Entrega:* Fase 10 fechada; pipeline de financeiras completo e testado. Falta só o item 4 (com o usuário).

### Etapa 2 — Fase 9: Saídas completas ✅ (ADR 0016)

Depende das fases 7 e 8 (já concluídas) e é pré-requisito natural para GUI e cache de resultados.

1. **Gráficos**: football field (com quartis dos múltiplos e linhas de preço atual / preço teto),
   cascata da ponte EV → Equity, heatmap de sensibilidade, histórico × projeção, composição do
   valor (VP dos fluxos × VP do valor terminal).
2. **Arquivos de saída**: `meta.json`, `premissas_usadas.yaml`, `qa.json`, `historico.csv`,
   `valores_reais.csv` (deflacionados por IPCA projetado — seção 11.5 do `CLAUDE.md`).
3. **Flag `--sem-graficos`** na CLI (`valuation rodar`).
4. Validar que `valuation rodar PETR4 --cenario todos` gera a pasta de saída completa e
   reprodutível (critério de pronto da Fase 9).

*Entrega:* relatório completo e reprodutível para qualquer empresa já mapeada; base pronta para GUI.

### Etapa 3 — Ajuste pontual do Kd da PETR4 ✅ (ADR 0017)

Pequena, mas elimina erro metodológico que distorce o valor em até 18%.

1. Decidir com o usuário o valor do Kd a usar (manual vs. algum proxy defensável).
2. Fixar `custo_capital.kd: {metodo: manual, valor: X}` no `config/empresas/PETR4.yaml`.
3. Rerodar `valuation rodar PETR4` e conferir o impacto; atualizar golden se necessário.

*Entrega:* valor da PETR4 metodologicamente correto; sem nova funcionalidade, baixo risco.

### Etapa 4 — Expandir o universo de empresas (não financeiras)

Baixo custo marginal: só adicionar YAMLs; o motor já está pronto.

1. Priorizar empresas do Ibovespa que o usuário queira acompanhar (lista a confirmar).
2. Para cada nova empresa: criar `config/empresas/{TICKER}.yaml`, rodar `valuation premissas
   sugerir {T} --escrever`, conferir o resultado, adicionar ao `universo_ibovespa.csv` se ausente.
3. Atenção a setores com particularidades ainda não validadas (varejo/arrendamentos IFRS 16,
   commodities com ciclo de preços — avisar o usuário nas premissas).

*Entrega:* cobertura prática do universo prioritário do usuário.

### Etapa 5 — Preço teto e recomendação básica

Agrupa dois itens relacionados; exige decisão de negócio antes de codar.

1. **Definir com o usuário** qual "preço teto" implementar (Bazin vs. `valor_justo_ponderado ×
   (1 − margem_segurança)` — o segundo já está previsto na seção 8.4 do `CLAUDE.md`).
2. Implementar e exibir: coluna em `resumo.csv`, linha vertical no football field (Fase 9 já
   entrega o gráfico).
3. **Recomendação** (compra / manter / venda): critérios baseados em upside relativo ao preço teto
   e retorno esperado vs. hurdle do perfil; aviso de confiança (QA, nº de pares, VT/EV); aviso de
   uso pessoal em destaque.

*Entrega:* sinal de decisão acionável sem requerer nenhuma nova fonte de dados.

### Etapa 6 — ✅ ERP implícito do Ibovespa em BRL (feito: ADR 0018, módulo, `valuation erp`, campo `erp.fonte`; o ERP deu −4,2%, ver fontes.md)

Melhora a robustez da premissa de ERP sem depender de fontes pagas; mais elaborado que os itens
anteriores, por isso fica aqui.

1. ADR 0018 (aceito): Focus no curto prazo, CAGR histórico na perpetuidade, sem convergência.
2. Módulo puro `custo_capital/erp_implicito.py` (ver detalhes na seção "ERP implícito" deste
   backlog).
3. Campo `custo_capital.erp.fonte: manual | implicito_ibovespa` em `config.py` e `settings.yaml`.
4. Testes à mão, `guia.md` e `CHANGELOG.md`.

*Entrega:* calibração do ERP baseada em dados locais, saindo com faixa e aviso (não número único).

### Etapa 7 — ✅ Glossário / explicação de métricas na CLI (feito: comando, `--explicar` e `meta.json`; faltam legendas nos PNG e a GUI)

Melhora a usabilidade sem alterar nenhum modelo.

1. Comando `valuation glossario [METRICA]` (ou flag `--explicar`) usando `rich`.
2. Legendas e notas de rodapé nas tabelas existentes (modo sucinto mantido por padrão).
3. Dicionário de dados embutido em `meta.json` e gerado junto aos relatórios da Fase 9.

*Entrega:* ferramenta mais educativa; útil antes da GUI.

### Etapa 8 — Tickers favoritos e cache de resultados

Agiliza o uso cotidiano depois que o universo estiver razoavelmente coberto (Etapa 4).

1. `config/favoritos.yaml` (ou campo em `settings.yaml`): lista de tickers favoritos.
2. Cache de resultados calculados: snapshot de `resumo.json` em `saida/{TICKER}/{data}/`; TTL e
   flag `--atualizar-favoritos`.
3. Comando `valuation favoritos` mostrando tabela resumida (preço, valor ponderado, upside, data).

*Entrega:* fluxo de revisão rápida sem nova rede; base para aba de favoritos na futura GUI.

### Etapa 9 — Interface gráfica (GUI)

Só depois das Fases 9 e 10 fechadas, e após as etapas 5–8 estabilizarem a CLI.

1. Decidir tecnologia (Streamlit local ou desktop) e registrar em ADR.
2. Implementar como camada fina sobre o motor: chama as mesmas funções puras e lê os mesmos YAMLs.
3. Telas prioritárias: favoritos/dashboard, edição de premissas, resultado (football field,
   sensibilidade) e histórico × projeção.

*Entrega:* interface visual para o workflow completo já validado na CLI.

### Etapa 10 — Monte Carlo (Fase 11, sob demanda)

Só iniciar se o usuário pedir explicitamente; exige decisão sobre distribuições e saída antes de codar.

1. Alternativa de curto prazo: `numpy`/`scipy` vetorizado (~100 k trajetórias), sem C++.
2. Se performance exigir: extensão C++ via `pybind11`, apenas no núcleo de simulação.
3. ADR antes de qualquer implementação (distribuições, saída, integração com CLI).

*Entrega:* distribuição do valor por ação e VaR do upside; Fase 11 do roadmap.

## Carteira pessoal (ADR 0020, planejado em 2026-10-31)

Escopo pedido pelo usuário: RF-004, 007, 008, 009, 010, 011 e 012 do plano de requisitos, de forma
plena. Os RF-005 (gráficos interativos), RF-001 (tempo real) e RF-013 (aportes) não entram aqui.
Regra de ordem: cada etapa só começa quando a anterior está com testes e `make lint tipos testes`
passando, e a validação de fonte (`docs/fontes.md`) vem antes de qualquer código que dependa dela.

### Perguntas abertas (dúvidas da seção 19 do `CLAUDE.md`)

1. **Fonte de proventos anunciados (RF-010/011).** Recomendo inspecionar primeiro o yfinance
   (`dividends`: data ex e valor, sem data de pagamento) e o cadastro de eventos da CVM, e escolher
   por dado real. Sem fonte confiável, RF-010/011 viram aviso e só o histórico de recebidos segue.
2. **Tela visual (RF-008 dashboard e página por ativo do RF-004).** Recomendo Streamlit local, como
   já previsto na Etapa 9, por ADR próprio. Até lá, a entrega é a CLI da Etapa C4.
3. **Carteira ou só valuation?** Já decidido pelo usuário em 2026-10-31 (ADR 0020). A pergunta 2
   decide só a tecnologia da tela.

### Etapa C1 — Transações e importação (RF-006 e RF-007) ✅

Feita em 2026-10-31 (`carteira/transacoes.py`, `carteira/arquivo.py`, `carteira lancar` e `carteira importar`).

Pré-requisito de todo o resto.

1. Schema de `carteira/transacoes.csv` (ADR 0020, item 3) em `src/valuation/carteira/`, com validação
   que recusa o arquivo inteiro e aponta a linha.
2. Importação CSV (`;`, decimal `,`) e XLSX (`openpyxl`, nova dependência autorizada no ADR).
3. Comando `valuation carteira lancar` (registro manual de compra, venda, provento, agrupamento,
   desdobramento, bonificação) e `valuation carteira importar ARQUIVO`.
4. Testes: linha inválida, venda acima da posição, XLSX e CSV equivalentes, histórico que não muda.

*Entrega:* carteira em disco, validada, sem cálculo ainda.

### Etapa C2 — Posição e preço médio (RF-008, parte de dados)

1. Função pura de posição: preço médio ponderado pelo custo (taxas incluídas), venda sem mudar o
   preço médio, agrupamento e desdobramento pelo fator, bonificação a custo zero.
2. Patrimônio, lucro/prejuízo nominal e percentual (venda + proventos recebidos − custo) com a
   cotação de fechamento na data-base, pela mesma função `fechamento_ate` de `precos.py`.
3. Teste com valores calculados à mão (um caso de compra, compra, venda parcial, desdobramento).

*Entrega:* `valuation carteira posicao` em tabela Rich, com aviso de cotação defasada.

### Etapa C3 — Indicadores por ativo (RF-004)

1. `analise/indicadores.py`: margem líquida, dívida líquida/EBITDA e ROE das não financeiras
   (esta última usa o PL inicial, como o ROE das financeiras). Os indicadores já existentes
   (P/L, P/VP, DY, EV/EBITDA, ROIC, margem EBITDA) são reexpostos sem mudar valor.
2. Comando `valuation indicadores TICKER` com legenda via `--explicar` (glossário da Etapa 7).
3. Golden de um ano conhecido (margem líquida e dívida líquida/EBITDA de PETR4 ou WEGE3, conferidos
   com o usuário, como o fim da Fase 2).

*Entrega:* a página por ativo em forma de tabela, pronta para a tela da pergunta 2.

### Etapa C4 — Proventos e agenda (RF-010 e RF-011)

Só começa com a pergunta 1 respondida.

1. Inspecionar a fonte escolhida, registrar em `docs/fontes.md` e no `docs/regras/REGRAS_DADOS.md` a
   regra de cache e de validação cruzada.
2. Proventos recebidos por mês (das linhas `provento`), e calendário de proventos anunciados
   cruzado com a posição (data com, data de pagamento, valor a receber).
3. Comando `valuation carteira proventos [--meses N]`: histórico mensal e provisionado.
4. Sem fonte confiável: só o histórico de recebidos, com aviso explícito.

*Entrega:* renda passiva mensal, recebida e provisionada.

### Etapa C5 — Alocação e alvos (RF-009 e RF-012)

1. `carteira/alvos.yaml` (classe e ativo, soma 100%, validado por pydantic).
2. Alocação atual por classe (`acao`) e por setor (`setor_cvm`) em percentual do patrimônio, com o
   desvio em relação ao alvo.
3. Saída CSV e PNG em rosca (`saida/carteira/{data}/alocacao.csv` e `alocacao.png`), no padrão
   dos gráficos da Fase 9, com legendas em PT-BR.
4. Fundos e renda fixa ficam fora (ADR 0020, item 7); FIIs seguem fora da v1 (seção 1 do `CLAUDE.md`).

*Entrega:* alocação real × alvo, o insumo do cálculo de aportes (RF-013, fora deste plano).

### Etapa C6 — Tela (RF-008 dashboard, RF-009 gráficos na tela)

Depende da pergunta 2 e de ADR próprio para a tecnologia. Reaproveita as Etapas C1 a C5 sem lógica
nova (mesmo princípio da Etapa 9).

*Entrega:* dashboard de patrimônio e alocação, e página por ativo.

### Documentação e testes desta frente

- Cada etapa atualiza `guia.md`, `CHANGELOG.md` e `docs/diagrama_atividades.md` (fluxo de importação e
  posição) na mesma entrega, como manda o `CONTRIBUTING.md`.
- Testes com transações sintéticas (`tests/sintetico.py`), sem rede.
- Nova dependência (`openpyxl`) entra em `pyproject.toml` só na Etapa C1.
