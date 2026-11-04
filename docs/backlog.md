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
4. ✅ **Golden das financeiras**: ITUB4 e BBAS3 feitos (ver Etapa 1). CVM traz IFRS consolidado
   (Itaú 2025: lucro da controladora 44.857 mi, PL da controladora 204.501 mi).
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

## GUI — requisitos a partir das referências (registrado em 2026-11-03)

Referências: as duas páginas de ativo salvas em `GUI/` (PETR4 no Investidor10 e no portal de
cotação com abas Geral/Contábil/Comunicado). Só **requisitos**: nada implementado. Vale o
princípio da seção acima: a GUI é camada fina sobre o motor, sem cálculo próprio, e lê os mesmos
YAMLs e saídas.

Legenda de **dado**: ✅ já existe na CLI/saídas; 🔶 existe parcial ou precisa de função nova sobre
dados já baixados; ❌ não há fonte gratuita ou está fora do escopo (CLAUDE.md, seção 1). Prioridade:
**P1** núcleo para a página de ativo funcionar, **P2** completa a semelhança, **P3** acabamento.

### Decisões que bloqueiam (perguntar antes de implementar, regra 7 do `CLAUDE.md`)

> **Respondidas em 2026-11-03 (ADR 0022):** 1 Streamlit; 3 Plotly; 5 lê `saida/` e cache, com
> botão de atualizar; 2 essencial = métricas e valuation. Tema (4) segue o do navegador.
> O plano de implementação está em "Sprint GUI 1" abaixo.

1. **Tecnologia** (exige ADR; dependência nova): Streamlit (rápido, aparência limitada, difícil
   copiar o layout das referências), NiceGUI/Dash (mais controle) ou backend local (FastAPI) +
   HTML/JS (fidelidade visual máxima, mais trabalho). Recomendação a discutir: FastAPI + frontend
   leve, porque as referências têm layout denso, abas, cards e gráficos interativos.
2. **Escopo da fidelidade**: copiar só a *página de ativo* ou também navegação global (rankings,
   agenda, notícias)?
3. **Gráficos interativos** (zoom, tooltip, períodos) exigem biblioteca JS ou Plotly, hoje o projeto
   só tem matplotlib/PNG. Aceitar a dependência?
4. **Tema** claro, escuro ou ambos; idioma só PT-BR (assumido).
5. **Execução**: GUI roda o `rodar` sob demanda (lento, rede) ou só lê o último `saida/` e cache,
   com botão "atualizar"?

### Fora do escopo (as referências têm, mas não entram)

Login/cadastro, planos PRO, anúncios, comunidade e comentários, avaliações de usuários, cursos,
IA ("Status Alpha"/Agente IA), Forecast e consenso de analistas (CLAUDE.md, decisão 12), FIIs,
stocks, REITs, BDRs, cripto, tesouro e renda fixa como páginas de ativo, notícias e fatos
relevantes (sem fonte gratuita estável decidida), mercado de opções, volatilidade vs IBOV como
produto próprio, "Preço justo Graham/Bazin" como *rótulo* (ver RF-G12).

### Estrutura da aplicação

- **GUI-01 (P1)** Shell: cabeçalho com busca de ticker (autocomplete pelo universo e cadastro),
  menu de seções e seletor de perfil do investidor; rodapé com aviso "estudo, não é recomendação".
- **GUI-02 (P1)** Rota por ativo (`/ativo/PETR4`) com abas fixas, como a referência (Geral,
  Contábil, Valuation, Comparar; "Comunicado" ❌ fica de fora). Troca de classe de ação
  (PETR3/PETR4) no topo.
- **GUI-03 (P1)** Barra de estado: data-base, idade do cache por fonte (CVM, preços, macro),
  avisos do `qa` e do `meta.json` sempre visíveis; botão "atualizar dados" (chama `atualizar`).
- **GUI-04 (P2)** Páginas globais: início/dashboard, favoritos, carteira, perfil, configurações.

### Aba Geral — cabeçalho e cotação

- **GUI-10 (P1)** Cabeçalho do ativo: nome, ticker, classe, setor/subsetor/segmento (cadastro CVM),
  botão de favorito (liga em `config/favoritos.yaml`, ADR 0021). Dado ✅.
- **GUI-11 (P1)** Cards de resumo: valor atual e variação do dia, mín./máx. 52 semanas, dividend
  yield 12m (e R$ por ação), valorização 12m. Dado 🔶 (preços ✅; dividendos pagos 🔶 conforme
  fonte, ver GUI-32).
- **GUI-12 (P1)** Gráfico de cotação com seletor de período (1 dia, 5 dias, 30 dias, 6 meses, YTD,
  1/5/10 anos, personalizado), cotação padrão × ajustada, moeda R$/US$/EUR. Dado 🔶: intradiário
  (1 dia) ❌ com yfinance diário; moedas usam câmbio do adaptador de macro.
- **GUI-13 (P2)** Comparar rentabilidade contra IBOV, CDI, IPCA e outros ativos (até 5). Dado 🔶.
- **GUI-14 (P2)** Rentabilidade nominal e **real** (descontada IPCA) por janela: 1/3 meses, 1/2/5/10
  anos. Dado 🔶 (IPCA ✅, preços ✅).
- **GUI-15 (P3)** Simulador "se tivesse investido há X": valor hoje com reinvestimento de
  dividendos. Dado 🔶.
- **GUI-16 (P3)** Dados de negociação: tipo da ação, tag along, liquidez média diária, participação
  no IBOV. Dado 🔶 (liquidez calculável de preço×volume; tag along e participação ❌ sem fonte).

### Aba Geral — indicadores fundamentalistas

- **GUI-20 (P1)** Grade de indicadores em cinco grupos (Valuation, Endividamento, Eficiência,
  Rentabilidade, Crescimento) com valor atual por indicador, como a referência. Reaproveita o
  comando `indicadores`/métricas de `contabil` (C3). Dado 🔶: faltam PEG, P/Ativo, P/SR,
  P/Cap. giro, P/Ativo circ. líquido, giro do ativo, liquidez corrente, PL/Ativos, Passivos/Ativos
  (cálculo novo sobre contas já padronizadas; cada definição exige pergunta, regra 7).
- **GUI-21 (P1)** Ajuda por indicador (ícone "?"): definição, fórmula e como interpretar, vinda do
  glossário da CLI (Etapa 7). Dado ✅; falta ampliar o glossário aos indicadores novos de GUI-20.
- **GUI-22 (P1)** Alternar visão **Hoje | Histórico | Média do mercado**. Hoje ✅/🔶; histórico
  (série anual até 10 anos, trimestral) 🔶 a partir de `historico.csv` e ITR; **média do
  mercado/setor** 🔶 a partir dos pares de `setores.yaml` (não é média da B3 inteira, deixar
  explícito no rótulo).
- **GUI-23 (P2)** Histórico de cada indicador em gráfico (linha ou barra), com seletor de
  indicador, janela (2/5/10/15 anos, máximo), opção "ignorar anomalias", e linhas de valor atual,
  média da própria empresa e média do setor.
- **GUI-24 (P2)** Comparação com os pares do setor: tabela empresa × pares nos mesmos indicadores
  (`multiplos_pares.csv` ✅), com edição de incluir/excluir pares.
- **GUI-25 (P2)** Financeiras: grade própria (ROE, P/VP, payout, DY, PL, carteira) em vez da de não
  financeiras, escolhida por `tipo_modelo` ✅.

### Catálogo de métricas a acrescentar (registrado em 2026-11-03)

Estado de hoje (conferido no código): `indicadores.py` mostra margem líquida, margem EBITDA,
dívida líquida/EBITDA, ROE, ROIC (não financeiras); ROE, payout, ROA e ativo/PL (financeiras); e
P/L, P/VP, dividend yield, EV/EBITDA, EV/EBIT (mercado). `modelos/multiplos.py` já calcula
EV/Receita e EV/FCF, mas o comando `indicadores` ainda não os mostra. `contabil/nao_financeiras.py`
tem as bases (EBITDA, NOPAT, FCFF, capex, CFO, NWC, dívida bruta/líquida, caixa, capital investido,
alíquota efetiva). Tudo abaixo é **o que falta**.

Legenda do dado: ✅ conta já padronizada, só falta a razão; 🔶 precisa de conta nova no
`mapeamento_contas.yaml` ou de dado de preço/volume; ❌ sem fonte gratuita decidida. "Anomalia" é a
classe de tratamento da seção "Decisões fechadas": **M+** múltiplo sempre positivo (Log-IQR),
**M±** pode ser negativo (IQR nos dois lados), **S/C** sem corte. **Todas as fórmulas são
propostas**: cada definição é confirmada com o usuário antes de implementar (regra 7), e cada uma
ganha verbete no glossário (`saida/glossario.py`) e teste calculado à mão.

**Não financeiras**

| Grupo | Métrica | Fórmula proposta | Dado | Anomalia |
|---|---|---|---|---|
| Valuation | P/Receita (P/SR) | market cap ÷ receita líquida LTM | ✅ | M+ |
| Valuation | EV/Receita, EV/FCF | já existem em `multiplos.py`; só expor | ✅ | M+ |
| Valuation | P/Ativo | market cap ÷ ativo total | ✅ | M+ |
| Valuation | P/Capital de giro | market cap ÷ capital de giro (NWC) | ✅ | M± (NWC pode ser ≤ 0) |
| Valuation | P/Ativo circulante líquido | market cap ÷ (ativo circulante − passivo total) | ✅ | M± |
| Valuation | PEG | P/L ÷ crescimento anual do lucro (CAGR 5 anos, em %) | ✅ | M± |
| Valuation | Earnings yield e FCF yield | EBIT ÷ EV; FCFF ÷ EV | ✅ | M± |
| Valuation | LPA, VPA | lucro e PL da controladora ÷ ações (na base de F(t)) | 🔶 | S/C |
| Endividamento | Dívida bruta/PL, dívida líquida/PL | dívida ÷ PL total | ✅ | M± |
| Endividamento | Dívida bruta/EBITDA, dívida líquida/EBIT | dívida ÷ EBITDA ajustado; ÷ EBIT | ✅ | M± |
| Endividamento | Cobertura de juros | EBIT ÷ despesas financeiras | ✅ | M± |
| Endividamento | Passivos/Ativos e PL/Ativos | passivo total ÷ ativo total; PL ÷ ativo | ✅ | S/C |
| Endividamento | Perfil da dívida | dívida CP ÷ dívida bruta | ✅ | S/C |
| Endividamento | Custo médio da dívida | Kd histórico (ADR 0007) como série | ✅ | M± |
| Caixa | Caixa e aplicações, caixa/dívida CP, caixa/ativo | (caixa + aplicações) ÷ denominador | ✅ | S/C |
| Caixa | Conversão de caixa | CFO ÷ EBITDA; FCF ÷ lucro líquido | ✅ | M± |
| Liquidez | Corrente, seca, imediata | AC÷PC; (AC−estoques)÷PC; (caixa+aplicações)÷PC | ✅ | S/C |
| Liquidez | Geral | (AC + realizável a LP) ÷ (PC + PNC) | 🔶 (realizável a LP) | S/C |
| Eficiência | Giro do ativo, do imobilizado | receita ÷ ativo total médio; ÷ imobilizado médio | ✅ | M+ |
| Eficiência | PMR, PME, PMP e ciclo de caixa | receber ÷ receita × 365; estoque ÷ custo × 365; fornecedores ÷ custo × 365 | ✅ | M+ |
| Rentabilidade | Margem bruta, margem EBIT, despesas operacionais/receita | razões sobre receita líquida | ✅ | M± |
| Rentabilidade | ROA, ROCE | lucro ÷ ativo inicial; EBIT ÷ (ativo − passivo circulante) | ✅ | M± |
| Rentabilidade | Margem de FCF, capex/receita, capex/D&A | razões do histórico | ✅ | M± |
| Crescimento | CAGR 3/5/10 anos de receita, EBITDA, lucro, dividendos | (final ÷ inicial)^(1/n) − 1; lucro ≤ 0 vira NaN | ✅ | M± |
| Crescimento | Variação anual de receita e lucro | t ÷ t−1 − 1 | ✅ | M± |
| Mercado | Retorno em janelas (1/3/6 meses, 1/5/10 anos), nominal e real | preço ajustado; real por IPCA | 🔶 | S/C |
| Mercado | Volatilidade, drawdown máximo, mín./máx. 52 semanas | sobre `Close` ajustado | 🔶 | S/C |
| Mercado | Liquidez média diária | média de preço × volume (yfinance) | 🔶 | S/C |
| Mercado | Beta e R² | `custo_capital/beta.py` como série móvel | ✅ | S/C |
| Proventos | Dividendo por ação e DY por ano | proventos por data ÷ preço (JCP/tipo ❌, ver GUI-32) | 🔶 | S/C |
| Mercado | Free float, tag along, participação no IBOV | — | ❌ | — |

**Financeiras (bancos e seguradoras)**

O ADR 0011 mapeou só as contas necessárias ao DDM (receitas, resultado bruto, LAIR, IR, lucro,
dividendos, ativo, passivo, PL, minoritários). Quase tudo abaixo exige inspeção das DFP reais de
ITUB4, BBAS3, BBDC4, SANB11 e BPAC11 antes de mapear (seção 7.2 do `CLAUDE.md`).

| Grupo | Métrica | Fórmula proposta | Dado | Anomalia |
|---|---|---|---|---|
| Capital | **Índice de Basileia**, capital principal e nível 1, RWA | divulgação prudencial do Banco Central | ❌ na CVM; candidato **IF.data (BCB)** | S/C |
| Capital | PL/Ativos, ativo/PL | já existem (`alavancagem`) | ✅ | S/C |
| Valuation | P/VPA tangível | market cap ÷ (PL − intangível) | 🔶 | M+ |
| Valuation | LPA, VPA, P/L, P/VP, DY, payout | P/L, P/VP, DY e payout já existem; LPA/VPA como na tabela acima | ✅/🔶 | M+ / S/C |
| Crédito | Carteira de crédito, carteira/ativo, carteira/depósitos | contas de "operações de crédito" e "depósitos" | 🔶 | S/C |
| Crédito | **Inadimplência (NPL 90 dias)**, cobertura de provisões | do release/IF.data; a DFP só traz o saldo de provisões | ❌ DFP / IF.data | M± |
| Crédito | Custo do crédito | despesa de provisão ÷ carteira média | 🔶 | M± |
| Resultado | Margem financeira (NIM), spread | resultado da intermediação ÷ ativos rentáveis médios | 🔶 | M± |
| Resultado | Índice de eficiência | despesas administrativas e de pessoal ÷ receitas | 🔶 | M± |
| Resultado | Receita de serviços/receitas | tarifas e serviços ÷ receitas totais | 🔶 | S/C |
| Rentabilidade | ROAE, ROAA | lucro ÷ PL médio; ÷ ativo médio (hoje o ROE usa o PL inicial) | ✅ | M± |
| Seguradoras | Sinistralidade, índice combinado, prêmios ganhos | sinistros ÷ prêmios ganhos; (sinistros + despesas) ÷ prêmios | 🔶 | M± |

**Basileia, em particular (entrada nova de fonte)**
- Não está na DFP (`CLAUDE.md`, seções 11.3 e 18). Candidata gratuita: **IF.data do Banco Central**
  (dados abertos: índice de Basileia, capital principal, nível 1, RWA, por instituição e trimestre).
- **[VALIDAR]** antes de qualquer código: URL e formato real, cobertura de ITUB4, BBAS3, BBDC4,
  SANB11 e BPAC11, histórico disponível e o casamento instituição ↔ ticker (o BC publica por
  **conglomerado prudencial**, não por CNPJ de companhia aberta). Registrar em `docs/fontes.md`.
- Exige adaptador em `data/` (cache, `.meta.json`, retry e segunda fonte ou aviso, como as demais),
  ADR próprio (fonte e casamento) e a decisão do usuário sobre o limite mínimo que vira aviso
  (o regulatório é 10,5% com adicional de conservação; o valor que a GUI destaca é escolha dele).
- Fora da sprint GUI 1; **P2 da sprint seguinte**. Enquanto isso, a GUI mostra "—" com o motivo
  "índice regulatório não consta na DFP".

**Prioridade sugerida de entrega** (para decidir com o usuário)
1. Expor o que já existe (EV/Receita, EV/FCF, ROA das não financeiras, dívida/PL, caixa, liquidez
   corrente/seca/imediata, cobertura de juros): só razões sobre contas ✅.
2. Séries históricas e CAGR de crescimento.
3. Eficiência (giros e prazos médios) e demais múltiplos de balanço.
4. Mercado (retornos, volatilidade, liquidez), depende da série de preço da S2.
5. Financeiras: mapear contas de crédito e depósitos, depois Basileia e inadimplência (IF.data).

### Aba Contábil

- **GUI-30 (P1)** Tabelas anual e trimestral de DRE, balanço e fluxo de caixa padronizados (10 anos),
  com variação ano a ano e seletor de linha para virar gráfico. Dado ✅ (`contas_padronizadas`).
- **GUI-31 (P2)** Gráficos "receitas e lucros", "lucro × cotação", "evolução do patrimônio" e
  "fluxo de caixa". Dado 🔶.
- **GUI-32 (P2)** Dividendos: histórico (data com, pagamento, tipo, valor), DY por ano e payout.
  Dado 🔶: payout ✅ via DFP; proventos por data dependem da fonte de preços (yfinance expõe
  dividendos; JCP/tipo ❌, ver pendência de JCP, CLAUDE.md seção 19, item 7).
- **GUI-33 (P2)** Painel de **QA**: resultado de `qa.json` por verificação, severidade e conta
  afetada, com o relatório de cobertura. Dado ✅. Diferencial das referências: aqui a procedência
  do número é visível.
- **GUI-34 (P3)** Posição acionária, regiões e segmentos de receita, produção (barris): ❌ fora das
  fontes da v1.

### Aba Valuation (o que as referências não têm; é o objetivo do projeto)

- **GUI-40 (P1)** Resultado por cenário (pessimista/base/otimista), valor ponderado pelo perfil,
  **preço máximo de compra**, upside, retorno esperado × hurdle. Dado ✅ (`resumo.csv`).
- **GUI-41 (P1)** Football field, ponte EV→equity em cascata, composição VP fluxos × VT, histórico ×
  projeção, heatmap de sensibilidade. Dado ✅ (PNG hoje; versão interativa se a decisão 3 aprovar).
- **GUI-42 (P1)** Checagens do DCF/DDM visíveis: VT/EV, múltiplo implícito, g < WACC, g ≤ teto,
  DDM × lucro residual (financeiras), avisos de baixa confiança. Dado ✅.
- **GUI-43 (P1)** WACC/Ke com cada componente (Rf, beta e R², ERP, Kd, estrutura) e avisos de
  qualidade do beta. Dado ✅ (`wacc.csv`).
- **GUI-44 (P2)** **Edição de premissas** com a sugestão do histórico ao lado (`premissas sugerir`),
  validação pydantic em tempo real, salvar no `config/empresas/{T}.yaml` e **recalcular** sem
  rodar a CLI; botão "restaurar sugerido". É o requisito de maior risco: deve gravar o YAML
  preservando comentários e não duplicar regra do motor.
- **GUI-45 (P2)** Sensibilidade interativa (WACC × g, margem × crescimento, Ke × g) chamando
  `avaliar` (função pura) em vez de CSV estático.
- **GUI-46 (P2)** Múltiplos implícitos (P/L, EV/EBITDA, P/VP pelos quartis dos pares) com valor por
  ação e aviso de poucos pares.
- **GUI-47 (P2)** Valores reais (deflacionados) em alternância nominal/real.
- **GUI-48 (P3)** Comparação entre execuções de datas diferentes (`saida/{T}/{data}/`) para ver
  o que mudou nas premissas e no valor.
- **GUI-49 (P3)** "Meu preço-alvo": campo livre do usuário contra o preço máximo do modelo (a
  referência tem "Definir meu Preço-Alvo").

### Preço justo e preço teto (referências: Graham e Bazin)

- **GUI-50 (P2)** Bloco "preço justo (Graham)" e "preço teto (Bazin)" ao lado do valuation. Depende
  da "Métrica de preço teto" desta página e de **decisão do usuário** sobre incluir ou não
  fórmulas de terceiros (LPA, VPA, DY alvo, média de dividendos). Não substituem o DCF e vêm
  rotulados como heurísticas.

### Favoritos, comparador e carteira

- **GUI-60 (P1)** Aba/lista de favoritos com preço, valor ponderado, upside, data do cálculo e
  idade do cache; ações: adicionar/remover, atualizar um ou todos. Dado ✅ (Etapa 8).
- **GUI-61 (P2)** Comparador de ativos (até 5) lado a lado em indicadores e valuation (`comparar`).
- **GUI-62 (P2)** Carteira: patrimônio, posição, preço médio, indicadores por ativo, alocação real ×
  alvo em rosca (Etapas C2 a C5 do plano da carteira, Etapa C6 é esta tela). Importação de
  XLSX/CSV pela tela.
- **GUI-63 (P3)** Agenda de proventos e de resultados da carteira (Etapa C4). Dado ❌ até a C4.
- **GUI-64 (P3)** Rastreador/ranking simples sobre o universo (filtros por indicador). Fora da v1
  (execução em lote, CLAUDE.md seção 1); só com decisão do usuário.

### Perfil e configurações

- **GUI-70 (P1)** Questionário de perfil na tela, mesma pontuação e vetos do `perfil/`; mostra
  validade (12 meses) e permite override explícito de perfil.
- **GUI-71 (P2)** Edição de `settings.yaml` (ERP, g máximo, margens do perfil) com aviso de que
  todos os [PLACEHOLDER] devem ser revisados, e glossário geral de métricas (Etapa 7).

### Requisitos não funcionais

- **GUI-90 (P1)** Zero lógica financeira na camada de tela; toda conta passa por funções existentes
  e é coberta por teste do motor. Testes da GUI sem rede (fixtures sintéticas).
- **GUI-91 (P1)** Estados vazios e de erro explícitos: dado ausente mostra "—" com motivo
  (ticker sem YAML, sem DFP, fora do escopo como holding), nunca zero silencioso.
- **GUI-92 (P1)** Formatação pt-BR (vírgula decimal, R$, %, escala em mi/bi) centralizada; mesma
  regra de arredondamento dos CSVs.
- **GUI-93 (P2)** Desempenho: página por ativo abre em < 2 s a partir de cache; cálculo longo roda
  em segundo plano com progresso e não trava a tela.
- **GUI-94 (P2)** Responsiva (desktop primeiro, utilizável em ~400 px) e acessível (contraste,
  foco, rótulos).
- **GUI-95 (P2)** Local e single-user: escuta só em `127.0.0.1`, sem login, sem telemetria,
  sem chave de API; `perfil/` e `carteira/` continuam fora do git.
- **GUI-96 (P2)** Reprodutibilidade: tudo mostrado traz a data-base e a versão de premissas;
  botão "exportar" reaproveita os CSVs/PNGs da Fase 9.
- **GUI-97 (P3)** Comando `valuation gui` (entry point) e alvo `make gui`.

### Lacunas de dados a resolver antes (por prioridade)

1. Série histórica de cada indicador (anual/trimestral) e média do setor: cálculo novo sobre dados
   existentes, mais a decisão de definição por indicador.
2. Indicadores faltantes de GUI-20 (cada um com sua definição, regra 7).
3. Dividendos por data e tipo (fonte e JCP).
4. Intradiário e cotação em outras moedas, se GUI-12 exigir.
5. API interna estável (funções que devolvem objetos/DataFrames, não texto de CLI) para a GUI
   consumir; hoje parte da apresentação mora em `cli.py`.

### Ordem sugerida de entrega

1. ADR de tecnologia + esqueleto (GUI-01/02/03/90/91/92/97) com a página PETR4 lendo `saida/`.
2. Aba Geral: GUI-10 a 12, 20 a 22; favoritos (GUI-60).
3. Aba Valuation: GUI-40 a 43, 70.
4. Aba Contábil: GUI-30, 33, 32.
5. Edição de premissas e sensibilidade interativa (GUI-44/45).
6. Comparador, carteira e extras (P2/P3).

## Sprint GUI 1 — plano de implementação (priorizar na próxima sprint)

Decisões já tomadas (ADR 0022, 2026-11-03): **Streamlit + Plotly**, app local, leitura de `saida/` e
cache ao abrir, botão "atualizar dados" para a rede, escopo inicial = **métricas + valuation** de um
ativo. Tudo o que não está aqui segue a "Ordem sugerida de entrega" acima.

**Meta da sprint:** `valuation gui` abre uma página por ativo com (a) cotação e séries históricas de
indicadores (inclui P/L) em gráficos Plotly e (b) o valuation por cenário lido do último `rodar`,
sem nenhuma conta feita na camada de tela.

### Ordem das tarefas (cada uma termina com `make lint tipos testes` verde e commit próprio)

**S1 — Extrair a camada de serviço de `cli.py`** (sem mudar nenhuma saída; ADR 0022, item 4)
- Criar `src/valuation/servicos/` (pacote novo; camada acima de `saida/` e `analise/`, importada só
  por `cli.py` e `gui/`). Regra do pacote: **nenhum** `typer`, `rich` ou `console.print`; avisos
  voltam como `list[str]` no retorno; erros continuam as exceções de domínio (`ErroContabil`,
  `ErroDadosExternos`, `ErroConfiguracao`, `ErroDownload`, `ErroModelo`).
- Mover de `cli.py`, mantendo a assinatura lógica, e fazer a CLI chamar o serviço:
  - `servicos/empresa.py`: `carregar_cadastro` (hoje `_carregar_cadastro`), `padronizar`
    (`_padronizar` e o dataclass `_Padronizada`, hoje com `console.print` de aviso de individual →
    campo `avisos`).
  - `servicos/mercado.py`: `carregar_mercado` (`_mercado`, `_cotacoes`, `_macro`,
    `_Mercado`); o aviso "dólar sem segunda fonte" e "sem preço" vira `avisos`.
  - `servicos/indicadores.py`: `serie_indicadores(p, settings, base, anos) -> TabelaIndicadores`
    (o miolo do comando `indicadores`: anual + LTM, `_anos_encerrados`, escolha financeira ×
    não financeira) e `indicadores_de_mercado(p, mk, settings, base)` (`_fundamentos` + `ind.de_mercado`).
  - `servicos/resultados.py`: `ultimo_resultado(ticker) -> Resultado | None`, lendo `resumo.csv`,
    `projecao_*.csv`, `wacc.csv`, `ponte_ev_equity.csv`, `sensibilidade_*.csv`, `qa.json`,
    `meta.json` da pasta de data mais recente (reaproveita `saida/favoritos.py`, ADR 0021, e o
    leitor que tenta `br` e depois `intl`).
- A formatação de texto (`_formatar`, `_brl`) **não** vai para o serviço: a CLI e a GUI formatam,
  ambas por um módulo único `saida/formato.py` (GUI-92; pt-BR, vírgula decimal, mi/bi).
- Fazer por fatias (uma por commit): empresa → mercado → indicadores → resultados. Os testes
  existentes (`test_cli.py` etc.) devem passar **sem edição**; se algum precisar mudar, parar e
  avisar (indica mudança de saída, regra 7).
- Testes novos: um por função de serviço, com fixtures sintéticas e sem rede (`REGRAS_TESTES.md`).

**S2 — Série histórica de cotação e de múltiplos** (cálculo novo; **depende das respostas abaixo**)
- `analise/serie_multiplos.py` (puro): `serie_multiplo(nome, precos, fundamentos_por_data) ->
  pd.Series` indexada por data, reutilizando `mt.multiplo` (mesma conta do `comparar`; GUI-90).
- `servicos/historico_mercado.py`: monta, para cada data de cálculo, os fundamentos LTM vigentes
  (usa `periodos.ltm` com dados até aquela data, sem olhar o futuro) e o preço da data.
- Cobrir P/L, P/VP, dividend yield, EV/EBITDA, EV/EBIT e, para financeiras, P/L, P/VP, dividend
  yield (conforme `ind.de_mercado`). Denominador ≤ 0 vira NaN (como em `indicadores.py`).
- Cotação histórica: `precos.YFinanceProvider.historico` já existe; expor via serviço com os
  períodos de GUI-12 (1 mês, 6 meses, YTD, 1 ano, 5 anos, máximo). Intradiário fica fora.
- Testes à mão: série sintética com preço e LTM conhecidos; ponto sem LTM disponível = NaN, não zero.

**S3 — Esqueleto Streamlit** (GUI-01, 02, 03, 90, 91, 92, 97)
- `pyproject.toml`: grupo opcional `gui` (`streamlit==1.66.0`, `plotly==7.1.0`);
  `[project.scripts]` ganha o comando via `valuation gui` (subcomando em `cli.py` que chama
  `streamlit run src/valuation/gui/app.py --server.address 127.0.0.1` com
  `browser.gatherUsageStats=false`) e `make gui`. Se `streamlit` não estiver instalado, mensagem
  clara "instale com `uv sync --group gui`" e saída 1.
- `src/valuation/gui/`: `app.py` (roteador por `st.navigation`/`query_params`: `?ticker=PETR4`),
  `estado.py` (barra de estado: data-base, idade do cache por fonte, avisos), `componentes/`
  (cards, tabela de indicadores com "?" do glossário, gráfico Plotly).
- Cache: toda leitura passa por `st.cache_data` sobre funções de `servicos/` (chave = ticker +
  data-base + mtime dos arquivos); nunca recálculo na tela. Botão **"Atualizar dados"** chama o
  mesmo fluxo de `atualizar` + `rodar` num `st.status`, e invalida o cache ao fim.
- Estados vazios e de erro explícitos (GUI-91): ticker fora do universo, sem DFP, sem `saida/`
  ("rode o valuation"), holding/FII fora da v1 — sempre "—" com o motivo, nunca zero.
- Busca de ticker com lista do universo (`config/universo_ibovespa.csv`) e favoritos
  (`saida/favoritos.py`); rodapé "estudo pessoal, não é recomendação".

**S4 — Aba Geral** (GUI-10 a 12, 20 a 22; só o necessário)
- Cabeçalho do ativo (nome, ticker, classe, setor do cadastro), cards de preço, mín./máx. 52
  semanas, market cap e dividend yield.
- Gráfico de cotação (Plotly, seletor de período) e gráfico de cada múltiplo da S2 com linhas
  de "valor atual" e "média da própria empresa" (mediana, a definir), seletor de indicador.
- Grade de indicadores: os que já existem em `indicadores.py` (margens, ROE, ROIC, dívida
  líquida/EBITDA, P/L, P/VP, EV/EBITDA, DY) na visão **Hoje | Histórico**. "Média do mercado" e os
  indicadores novos de GUI-20 ficam para a sprint seguinte.

**S5 — Aba Valuation** (GUI-40 a 43, só leitura de `saida/`)
- Cenários pessimista/base/otimista, valor ponderado, preço máximo de compra, upside e retorno
  esperado × hurdle; WACC/Ke com componentes e avisos; checagens (VT/EV, g < WACC, DDM × lucro
  residual); ponte EV→equity e football field refeitos em Plotly **a partir dos CSVs** (não
  reabrir os PNGs). Sem `saida/`, a aba mostra o botão "Rodar valuation".
- Perfil: mostrar o perfil lido de `perfil/perfil_investidor.json` (validade 12 meses); o
  questionário na tela (GUI-70) fica fora desta sprint.

**S6 — Testes, documentação e fechamento**
- Testes: serviços (S1/S2) sem rede; GUI com `streamlit.testing.v1.AppTest` sobre fixtures
  sintéticas em `tests/fixtures/` (página abre, estado vazio, ticker inválido, dados presentes).
  Cobertura mínima de 80% em `servicos/` e `analise/`; `gui/` fora do piso, mas com o teste de fumaça.
- Documentos (CONTRIBUTING, "Antes de concluir"): `guia.md` (seção nova `servicos/` e `gui/`, subir
  versão), `CHANGELOG.md`, `README.md` (como abrir a GUI), `docs/diagrama_arquitetura.md`,
  `diagrama_atividades.md` e `diagrama_casos_de_uso.md` (fluxo GUI), `docs/decisoes/README.md`,
  nota no `CLAUDE.md` seção 1 (interface web entrou por ADR 0022) e `docs/contexto_rapido.md`.

### Perguntas a responder **antes** da S2 (regra 7; mudam números exibidos)

1. **Definição do P/L histórico** (e dos demais múltiplos). Opções: (a) *preço no fechamento do
   exercício ÷ LPA do exercício* (um ponto por ano, simples, sem ITR); (b) *preço de cada data ÷
   LPA LTM vigente* (série suave, um ponto por mês ou por semana; usa ITR e a regra de LTM do
   `periodos.py`); (c) *(b) só nas datas de divulgação* (um ponto por trimestre). Recomendação: **(b),
   com ponto mensal**, para o gráfico acompanhar a cotação.
2. **Defasagem de publicação**: usar o LTM só a partir da data em que o ITR/DFP foi divulgado
   (evita olhar o futuro) ou do fim do período? Recomendação: a partir da divulgação, se a data
   existir na CVM (`DT_RECEB`/ `dt_receb`, **[VALIDAR]** no arquivo real); senão, fim do período + 45 dias
   (ITR) ou + 90 dias (DFP), registrado no `docs/fontes.md`.
3. **Ações no tempo**: a composição de capital da CVM traz a quantidade vigente. Para o LPA ou
   o market cap histórico, usar a quantidade atual com preço **ajustado por desdobramentos**, ou as
   quantidades de cada data? Recomendação: preço ajustado por desdobramentos/grupamentos e ações
   atuais, com aviso. **[VALIDAR]** que o yfinance com `auto_adjust=False` traz `Stock Splits` e
   quais datas (ADR 0003 trata a escala das ações).
4. **"Média" de referência no gráfico**: mediana ou média da própria empresa; janela (5 anos ou
   toda a série); remover anomalias (GUI-23) por qual critério (ex.: P/L < 0 ou > 100)?
5. **Média do setor/mercado** (GUI-22): confirmada como média dos pares de `setores.yaml`, não da
   B3 inteira? Entra na sprint seguinte.
6. **Janela do histórico**: 10 anos (CLAUDE.md) ou o que o yfinance entregar? Preço ≥ 10 anos é
   confiável para todas as empresas do universo? **[VALIDAR]** por amostra.

### Respostas do usuário (2026-11-03)

1. **P/L histórico: (b)**, preço de cada data ÷ LPA do LTM vigente, ponto mensal. ✅
2. **Defasagem: data de divulgação** do ITR/DFP. ✅ (fallback quando a CVM não trouxer a data:
   fim do período + 45 dias no ITR e + 90 dias na DFP; **[VALIDAR]** `DT_RECEB` no arquivo real.)
3. **Ações no tempo: em análise pelo usuário.** Levantamento feito em 2026-11-03 com `Ticker.splits`
   do yfinance, 2016-11 a 2026-11, nos 76 tickers do universo: **84 eventos em 43 tickers**.
   - Desdobramentos grandes: MGLU3 (8:1 em 2017 e 2019, 4:1 em 2020), PRIO3 (10:1 em 2019, 5:1 em
     2021), CPLE3 e IGTI11 (10:1), HAPV3/EQTL3/ASAI3/RADL3 (5:1), WEGE3 (1,3 em 2018 e 2:1 em 2021),
     BBAS3 (2:1 em 2024), VIVT3 e FLRY3 (2:1).
   - Grupamentos (fator < 1): **MGLU3 10:1 em 2024-05-27** e **HAPV3 15:1 em 2025-06-06**.
   - Bonificações (fatores 1,01 a 1,4, que o Yahoo também registra como split): ITUB4, BBDC3/4,
     ITSA4, LREN3, CMIG4, EGIE3, GGBR4, RADL3 e outras. Mudam a quantidade de ações do mesmo jeito.
   - **Achados que afetam o desenho:** (i) o `Close` do yfinance, mesmo com `auto_adjust=False`, vem
     **ajustado por splits** (só os dividendos ficam de fora), então preço histórico e quantidade
     atual de ações estão na mesma base, mas a quantidade da **CVM por data** está na base da época
     (WEGE3 em 2020 tem metade das ações de hoje, ADR 0003); (ii) o yfinance **não é exaustivo** nem
     garantido (conferir contra a composição de capital da CVM: salto de ações sem split
     correspondente ou o inverso é aviso); (iii) a lista completa está na Etapa S2 como fixture
     (`tests/fixtures/splits_universo.csv`, a criar).
   - **Proposta** (aguarda confirmação): market cap(t) = `Close` ajustado(t) × ações da CVM vigentes
     em t × F(t), com F(t) = produto dos fatores de split posteriores a t; assim a quantidade
     histórica real é usada sem supor ações constantes (emissões e recompras entram), e o resultado
     não depende de a quantidade atual representar o passado.
4. **Referência no gráfico: mediana e média, com alternância na tela; janelas 10 anos, 5 anos e
   atual.** ✅ Pendente: critério de anomalias (ver "Perguntas abertas").
5. **Média de referência: pares do setor e B3.** ✅ com a ressalva de "B3" abaixo.
6. **Janela do histórico: 10 anos.** ✅
7. **Dependências: Streamlit e Plotly** (o usuário escreveu "plotpy"; assumido Plotly, a biblioteca
   que o Streamlit renderiza; PlotPy é de Qt/desktop). Versões fixadas na S3: `streamlit==1.66.0`
   (2026-10-14; a 1.66.1 de 2026-10-21 tem menos de 14 dias) e `plotly==7.1.0` (2026-09-15).
   Confirmadas no PyPI em 2026-11-03.

### Respostas da segunda rodada (2026-11-03)

- **Item 3 (market cap histórico com ações da CVM por data): aprovado.** ✅
- **Resposta sobre a API:** o yfinance **lista** desdobramentos, grupamentos e bonificações
  (`Ticker.splits`) e **ajusta preço e dividendos** por eles; conferido em 2026-11-03: `Close` sem
  salto em MGLU3 (grupamento 1:10 em 2024-05-27, 12,57 → 12,52) e em WEGE3 (2:1 em 2021-04-28,
  37,01 → 36,50). **Não normaliza** o que vem da CVM: lucro, PL e dívida são valores em R$ e não
  mudam, mas a quantidade de ações vem na base da época. Qualquer métrica por ação (LPA, VPA,
  dividendo por ação, market cap) é nossa conta, com o fator F(t) acumulado dos splits.
- **Anomalias: base = `guia_de_tratamento_de_anomalias_de_p_l_em_valuation.md`** (raiz do repo).
  Procedimento adotado: (1) remover P/L ≤ 0 e guardar as empresas/datas removidas; (2) se n ≥ 15,
  Log-IQR com corte superior `exp(Q3_y + 1,5·IQR_y)`; (3) se n < 15, corte fixo + mediana.
  - O guia tem um erro de digitação na seção 4, passo 2: escreve `Q1,y + 1,5·IQR_y`; o correto, pela
    seção 3, é `Q3,y + 1,5·IQR_y`. Vale o da seção 3.
  - O guia trata o corte transversal (pares). Na série temporal de uma empresa (120 pontos
    mensais em 10 anos), n ≥ 15 sempre vale; nos pares da maioria dos setores n < 15.
  - A empresa/data removida não some do relatório: a GUI mostra o motivo (P/L ≤ 0 ou acima do
    corte) e sugere o múltiplo alternativo do guia (EV/EBITDA, P/S ou PEG).
- **B3 e pares: aceitos** como propostos (Ibovespa, só empresas carregadas, financeiras separadas;
  valor de hoje na S4, série histórica depois). ✅
- **"Atual" = marcador do valor de hoje** (assumido, ninguém discordou). ✅
- **Escopo de dados por favoritas** (ver "Perguntas abertas"): carga primária só das favoritas
  (`config/favoritos.yaml`, ADR 0021); ativo não favorito é carregado sob demanda quando aberto.

### Decisões fechadas (terceira rodada, 2026-11-03): S2 liberada

1. **Corte fixo (n < 15): 80x**, parâmetro global `multiplos.corte_pl` no `settings.yaml`, com
   sobrescrita por setor em `setores.yaml` depois. Escolha delegada pelo usuário ("80x e 100x já
   parecem anomalias"); o menor dos dois valores do guia é o mais conservador para poucos pares.
2. **Estatística de referência: mediana, média winsorizada e média simples, com seletor na tela.**
   Padrão = mediana (guia, seção 5). Média simples mostra aviso de sensibilidade a extremos. A
   winsorização usa os limites do filtro (corte superior; inferior só em métrica que pode ser
   negativa).
3. **`comparar`/`multiplos.py` não mudam.** O guia entra em `analise/anomalias.py`, usado só pela
   GUI; unificar depende de ADR futuro, comparando os valores implícitos antes e depois.
4. **Tratamento de anomalias para o máximo de métricas** (pedido do usuário):
   - Múltiplos sempre positivos (P/L, P/VP, P/SR, EV/EBITDA, EV/EBIT, EV/Receita, P/Ativo,
     P/Cap. giro): ≤ 0 removido, Log-IQR (n ≥ 15) ou corte fixo (n < 15). Corte fixo de cada um
     é parâmetro (`multiplos.corte_*`) e **não** é 80x para todos; valor a escolher na S2.
   - Métricas que podem ser negativas legitimamente (margens, ROE, ROIC, crescimento, dívida
     líquida/EBITDA): IQR de Tukey **nos dois lados**, na escala linear. *Escolha minha, mudar se
     discordar*: o guia não cobre esse caso.
   - Dividend yield, payout e liquidez: sem corte, só marcação visual de pontos fora de 1,5·IQR.
   - A série nunca é apagada; pontos descartados ficam em cinza e a tela mostra a contagem.
5. **Atualização só no clique.** Abrir a GUI lê o cache dos favoritos, sem rede. Botão "Atualizar
   favoritas" (reaproveita `favoritos atualizar`) e botão "Atualizar" em cada página de ativo.
   Rede automática apenas para ativo sem nenhum cache: o favorito sem cache ou o não favorito
   aberto pela primeira vez, com progresso e erro visível.

### Métricas pedidas além do GUI-20

Pedido do usuário (2026-11-03): "o máximo de métricas possíveis", inclusive Basileia, endividamento
e caixa. O catálogo completo, com fórmula proposta e estado do dado, está em **"Catálogo de métricas
a acrescentar"** (aba Geral, abaixo). Nenhuma entra na sprint GUI 1 sem passar pela regra 7.

### Critério de pronto da sprint

- `uv sync --group gui && valuation gui` abre `http://127.0.0.1:8501` sem rede e sem erro, mostra
  PETR4, VALE3 e WEGE3 a partir do cache e dos últimos `saida/`.
- A aba Geral exibe cotação e pelo menos P/L, P/VP, EV/EBITDA e dividend yield em série, com o
  valor atual marcado; a aba Valuation exibe os três cenários, o ponderado e o preço máximo de compra
  iguais ao `resumo.csv`.
- `grep -R "rich\|typer" src/valuation/servicos src/valuation/gui` vazio; nenhuma conta financeira em
  `gui/`; `make lint tipos testes` verde; testes da CLI inalterados.
- Documentos da S6 atualizados e dito no resumo quais foram.

### Riscos

- `cli.py` (3,4 mil linhas) mistura apresentação e orquestração: extrair em fatias, rodando os testes
  a cada uma, para a mudança de saída não passar despercebida.
- Série de múltiplos depende de LTM em muitas datas: custo de CPU (cachear por ticker) e de
  qualidade (trimestres faltando na CVM viram lacuna visível, não interpolação).
- Streamlit reexecuta o script a cada clique: sem `st.cache_data` a página passa de 2 s (GUI-93).
- yfinance é não oficial: o botão de atualizar precisa mostrar a falha sem derrubar a tela.

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
4. ✅ **Golden das financeiras** (ITUB4 em 2026-11-02, BBAS3 em 2026-11-03): lucro, PL e ativo do
   IFRS em `tests/golden/referencias.yaml`. ROE fica de fora: o do release é gerencial, não IFRS.
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

### Etapa 8 — ✅ Tickers favoritos e cache de resultados (ADR 0021; falta só a aba na GUI)

Agiliza o uso cotidiano depois que o universo estiver razoavelmente coberto (Etapa 4).

1. `config/favoritos.yaml` (ou campo em `settings.yaml`): lista de tickers favoritos.
2. Cache de resultados calculados: snapshot de `resumo.json` em `saida/{TICKER}/{data}/`; TTL e
   flag `--atualizar-favoritos`.
3. Comando `valuation favoritos` mostrando tabela resumida (preço, valor ponderado, upside, data).

*Entrega:* fluxo de revisão rápida sem nova rede; base para aba de favoritos na futura GUI.

### Etapa 9 — Interface gráfica (GUI)

Só depois das Fases 9 e 10 fechadas, e após as etapas 5–8 estabilizarem a CLI.

0. Requisitos detalhados (GUI-01 a GUI-97) na seção "GUI — requisitos a partir das referências".
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

## Validação cruzada dos fundamentos (yfinance × CVM)

Objetivo (pedido do usuário em 2026-11-03): não precisar enviar os relatórios das companhias a cada
conferência. O pipeline compara lucro, PL, ativo (e receita, nas não financeiras) calculados a
partir da CVM com os fundamentos do Yahoo (`yfinance`, já dependência do projeto). Se coincidem, nada
é pedido; se divergem, dispara um alerta pedindo o release daquele período. O golden continua sendo o
registro fixo conferido com o documento da companhia; a checagem externa é só triagem.

**Sondagem feita em 2026-11-03** (leitura, sem gravar nada): `Ticker.quarterly_income_stmt` e
`quarterly_balance_sheet` trazem ~5 trimestres (o mais antigo vem `NaN`). BBAS3 bateu com o IFRS do
golden até a primeira casa decimal em lucro dos controladores (`Net Income Common Stockholders`),
PL dos controladores (`Stockholders Equity`) e ativo total (`Total Assets`). PETR4 veio em **dólar**
(receita do 2T26: 33.607 contra R$ 169.530 mi), então precisa de checagem de moeda. Em banco, o
`Total Revenue` do Yahoo não é a receita da CVM: não comparar.

### Desenho

1. **Adaptador** `src/valuation/data/fundamentos.py` (camada `data`, sem importar camadas acima):
   - `FundamentosProvider` (Protocol, como `PrecosProvider`) e a implementação `yfinance`, devolvendo
     tabela longa `data_ref, metrica, valor, moeda, fonte`, com métricas padronizadas
     (`lucro_controladora`, `patrimonio_liquido_controladora`, `ativo_total`, `receita_liquida`).
   - Mapa de rótulos do Yahoo → métrica em `config/` (não no código); moeda de `financialCurrency`.
   - Cache em `data/raw/fundamentos/` (parquet + `.meta.json`), TTL em `cache_ttl_horas.fundamentos`,
     retry e cópia vencida em falha de rede, como em `precos.py`. Falha ou ausência nunca é erro.
2. **Comparação** em `contabil/qa.py`, que continua pura: `verificar(..., referencia_externa=None)`
   recebe a tabela já baixada (quem baixa é a CLI). Para cada (métrica, data) em comum, monta duas
   `Leitura` (CVM principal, Yahoo alternativa) e chama `validacao.cruzar`; consolida num único
   `Verificacao` de código `fundamentos_divergentes`.
   - Fluxos: trimestres de `periodos.trimestral`; saldos: datas de balanço. Só períodos que existem
     nos dois lados.
   - Financeiras: só lucro dos controladores, PL dos controladores e ativo total. Não financeiras:
     inclui receita líquida. EBITDA e dívida líquida ficam fora (definições diferentes entre fontes).
3. **Resultado por situação**:

   | Situação | Severidade | Efeito |
   |---|---|---|
   | todos os períodos coincidem | `info` | "conferido com yfinance em N períodos"; nenhum pedido |
   | diferença acima da tolerância | `aviso` | lista (métrica, período, valor CVM, valor Yahoo) e a frase "envie o release de {período}" |
   | moeda do Yahoo ≠ moeda da CVM (PETR4) | `info` | "sem validação: Yahoo em USD" |
   | Yahoo sem o período ou sem rede | `info` | "sem validação externa"; nunca bloqueia |

   O aviso aparece no `qa.json`, na saída do `valuation qa TICKER` e `valuation rodar` e no
   `meta.json`. Não interrompe a execução (mesma política da validação cruzada de preços e macro).
4. **Tolerância** (`settings.yaml`, `validacao.fundamentos`, **[PLACEHOLDER]**): relativa de 0,5% **e**
   diferença absoluta acima de R$ 1 milhão, para o arredondamento do Yahoo (0,1 milhão) e valores
   pequenos não dispararem falso alerta.
5. **Fluxo do usuário**: coincidiu → segue sem enviar nada. Alertou → envia o release; o agente
   confere, corrige o mapeamento ou o dado e, se for o caso, acrescenta o período ao
   `tests/golden/referencias.yaml`.
6. **Em lote** (extensão): `valuation validar --tudo` percorre o universo e lista quais empresas têm
   divergência, para o usuário enviar só esses relatórios.

### Etapas

- **V1 — Validar a fonte** (antes de qualquer código): script exploratório de leitura sobre os
  pilotos (PETR4, VALE3, WEGE3, ITUB4, BBAS3): cobertura de períodos, rótulos, moeda e taxa de acerto
  contra a CVM. Registrar em `docs/fontes.md`; fixar a tolerância com o resultado.
- **V2 — ADR e adaptador**: ADR 0022 (uso do yfinance para fundamentos só como segunda fonte, nunca
  principal, sem alterar o `CLAUDE.md`), `fundamentos.py`, mapa de rótulos, cache; `tests/test_fundamentos.py`.
- **V3 — Integração**: parâmetro em `qa.verificar`, chamada na CLI (`qa` e `rodar`), opção
  `--sem-externo`, `settings.yaml`, avisos no `meta.json`; casos novos em `tests/test_qa.py`.
- **V4 — Lote**: `valuation validar --tudo` sobre o universo.
- **V5 — Moeda (opcional)**: comparar emissores em USD (PETR4) convertendo pela PTAX da data com
  tolerância larga (ordem de 5%), ou manter "sem validação". Decisão do usuário.

### Testes (sem rede, como manda `docs/regras/REGRAS_TESTES.md`)

Provider falso e tabelas sintéticas: coincidência, divergência de 1%, diferença abaixo do piso
absoluto, período `NaN` ou ausente, moeda USD, rede fora do ar, financeira sem receita comparada,
cache dentro do TTL e cópia vencida em falha; `qa.json` com o novo código. Nenhum teste chama o
Yahoo.

### Limites a registrar

- Cobre só os últimos ~5 trimestres: serve para erro em dado recente (reapresentação, conta nova),
  não para os 10 anos.
- O Yahoo parte dos mesmos documentos que a CVM: é independente do nosso parser e mapeamento, não
  do que a companhia divulgou. Coincidir diz que as duas leituras concordam, não que conferem com o
  documento.
- Alerta significa "confira": moeda, definição (lucro ajustado × IFRS) ou erro do Yahoo também disparam.
- Yahoo pode atrasar a publicação de um trimestre novo: aparece como "sem validação", não como erro.
- Rótulos validados só para BBAS3 e PETR4; confirmar nos demais pilotos na etapa V1.

### Documentos a atualizar na entrega

`docs/fontes.md`, ADR 0022 (com índice), `guia.md` (módulo `fundamentos`, `qa`, testes), `README.md`
(tabela de APIs e testes), `CHANGELOG.md`, `docs/diagrama_atividades.md` e os UML afetados
(`docs/diagramas.md`: classes, sequência do `rodar`, arquitetura), `docs/regras/REGRAS_DADOS.md` se
surgir regra nova.

### Perguntas abertas para o usuário

1. Tolerância: aceita 0,5% com piso de R$ 1 milhão?
2. O alerta só avisa (recomendado) ou deve bloquear o `rodar`?
3. Vale a pena a etapa V5 (conversão por PTAX) ou emissores em USD ficam "sem validação"?

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

### Etapa C2 — Posição e preço médio (RF-008, parte de dados) ✅

Feita em 2026-11-03 (`carteira/posicao.py`, `valuation carteira posicao`). Sem CSV de saída: só a tabela, como previsto.

1. Função pura de posição: preço médio ponderado pelo custo (taxas incluídas), venda sem mudar o
   preço médio, agrupamento e desdobramento pelo fator, bonificação a custo zero.
2. Patrimônio, lucro/prejuízo nominal e percentual (venda + proventos recebidos − custo) com a
   cotação de fechamento na data-base, pela mesma função `fechamento_ate` de `precos.py`.
3. Teste com valores calculados à mão (um caso de compra, compra, venda parcial, desdobramento).

*Entrega:* `valuation carteira posicao` em tabela Rich, com aviso de cotação defasada.

### Etapa C3 — Indicadores por ativo (RF-004) ✅ (golden pendente)

Feita em 2026-11-03 (`analise/indicadores.py`, `valuation indicadores`, glossário). **Falta o item 3** (golden): os números de PETR4 estão no terminal, mas só entram em `tests/golden/` depois que o usuário os conferir com o release.

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
