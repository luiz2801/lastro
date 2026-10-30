# Backlog

Itens fora do roadmap das fases (seção 17 do `CLAUDE.md`), registrados para depois.

## Ordem de prioridade (decidida em 2026-10-30)

Em andamento por escolha do usuário: **Fase 10 (financeiras)**. Depois, nesta ordem:

1. **Fase 9 — Saídas** (roadmap): gráficos (football field com os quartis dos múltiplos, cascata
   da ponte, heatmap, histórico × projeção, composição do valor), `meta.json`,
   `premissas_usadas.yaml`, `qa.json`, `historico.csv`, `valores_reais.csv`, `--sem-graficos`.
2. **Kd da PETR4**: fixar `custo_capital.kd: {metodo: manual, valor: ...}` no YAML dela. O piso
   do Kd na Rf muda o valor em até 18% (Kd histórico cru de 7,8% contra 14,87%): o Kd histórico
   mistura juros em dólar com variação cambial. Precisa de um valor escolhido pelo usuário.
3. **ERP implícito do Ibovespa em BRL** (opção D da decisão sobre o ERP): ver abaixo.
4. Demais itens desta página (outras empresas, preço teto, GUI, recomendação).

## ERP implícito do Ibovespa em BRL

Opção D da decisão sobre o ERP; hoje o `custo_capital.erp` é a premissa de 5,0% do usuário.

- Módulo puro `custo_capital/erp_implicito.py` (fluxos, valor do índice, Rf e g por parâmetro; sem
  rede nem `date.today()`), no estilo de `cenarios.taxa_implicita` (`brentq`): resolve
  `P0 = Σ FC_t / (1 + ke)^t` e `ERP = ke − Rf`.
- Dados já disponíveis: `config/universo_ibovespa.csv`, `metricas_ltm` (lucro, dividendos) e
  market cap (com a escala de ações corrigida). Fluxo agregado = dividendos (e recompras, se
  houver).
- Ponto frágil: o crescimento esperado do índice, sem consenso de analistas (decisão 12). Usar o
  Focus (PIB + inflação) como teto de longo prazo e o histórico no curto prazo; sair com **faixa e
  aviso**, não número único.
- Exige ADR, campo novo (`custo_capital.erp.fonte: manual | implicito_ibovespa`) em `config.py` e
  `settings.yaml`, testes à mão, `guia.md` e `CHANGELOG.md`.
- Não aplicar ERP por setor, não calibrar no preço da empresa avaliada, não somar `crp` em BRL.
- O yield spread (earnings yield − NTN-F) fica como termômetro de contexto no `mercado` (hoje:
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

## Recomendação (compra / venda)

**Conflita com o `CLAUDE.md`**, que pede mensagem neutra ("preço de mercado X; abaixo/acima do
preço máximo para o perfil Y", seção 8.4), sem recomendação de compra ou venda, e trata o projeto
como ferramenta de estudo, não de recomendação. Para entrar:

- Mudar essa regra no `CLAUDE.md`, com o aval do usuário, e registrar a decisão num ADR.
- Definir os critérios: por exemplo, faixas de upside contra o preço teto/preço máximo, retorno
  esperado contra o hurdle do perfil e confiança (avisos de QA, poucos pares, VT/EV alto).
- Manter o aviso de que é uso pessoal e não constitui recomendação de investimento.
