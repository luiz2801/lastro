# Backlog

Itens fora do roadmap das fases (seção 17 do `CLAUDE.md`), registrados para depois.

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
