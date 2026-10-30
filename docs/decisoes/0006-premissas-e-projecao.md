# ADR 0006 — Premissas sugeridas e projeção do FCFF

- **Data:** 2026-10-30
- **Status:** aceito

## Contexto

A Fase 5 implementa o YAML por empresa (seção 9.1 do `CLAUDE.md`), o sugestor (9.2) e o projetor
(9.3). O guia deixa em aberto pontos que mudam números ou o fluxo de trabalho: como `--escrever`
grava as sugestões, quanto a margem reverte, como projetar o capital de giro, o tamanho dos deltas
dos cenários e como tratar o arrendamento na projeção, embora a fórmula da seção 11.1 o desconte.
Os quatro primeiros pontos foram decididos pelo usuário em 2026-10-30. Para calibrar, foi usado o
histórico real dos pilotos (2016–2025). Exemplos: margem EBITDA da WEG de 21,8% (mediana de 5a)
contra 18,7% (mediana de 10a); desvio-padrão do crescimento da Petrobras de 27 p.p.

## Decisão

1. **`sugerido` continua `sugerido` no YAML** e é recalculado do histórico a cada execução.
   `premissas sugerir --escrever` regenera o arquivo inteiro, com o valor de hoje e a origem em
   comentário. Campos já fixados como número são preservados e mostram a sugestão ao lado. O
   arquivo anterior vira `.yaml.bak`, e os comentários próprios do usuário se perdem. Os números
   efetivamente usados vão para `premissas_usadas.yaml` de cada saída (Fase 9). O guia dizia
   "grava no YAML"; aqui o valor gravado fica no comentário.
2. **Margem EBITDA sugerida = margem ajustada** (sem equivalência patrimonial e sem não
   recorrentes), coerente com o EBIT projetado, que exclui a equivalência quando
   `coligadas: somar_investimento_contabil`. Começa na mediana de 5a e termina na **média entre
   as medianas de 5a e 10a** (reversão de metade do caminho), com convergência linear.
3. **ΔNWC incremental:** ΔNWC_t = (NWC/receita) × (receita_t − receita_{t−1}). O primeiro ano
   não absorve a diferença entre o NWC real e a razão-alvo.
4. **Deltas sugeridos dos cenários:** ±1 desvio-padrão (10a) do crescimento e da margem, limitado
   a [1, 5] p.p.; capex ±0,5 desvio-padrão do capex/receita, limitado a [0,25; 2] p.p.
   Pessimista: −crescimento, −margem, +capex. Os deltas valem para todos os anos explícitos; o g
   terminal não muda.
5. **Campo novo `projecao.arrendamento_sobre_receita`** (mediana de 5a do pagamento de
   arrendamento da DFC sobre a receita). Com `ifrs16: divida` e `capex_equivalente_arrendamento`,
   ele é descontado do FCFF projetado, como no histórico (ADR 0005).
6. **Anos projetados:** do exercício seguinte ao último histórico até completar `horizonte` anos
   com fluxo por vir. `fracao` = 0 para exercício já encerrado sem DFP (ponte), dias restantes /
   365 no ano corrente e 1 depois. Listas explícitas no YAML começam no exercício seguinte ao
   último histórico. O horizonte entra na lista de anos de `PremissasResolvidas`; por isso
   `projetar(historico, premissas, *, data_base)` não recebe `horizonte` como no guia.
7. **Imposto sobre o EBIT** em todos os anos, inclusive com EBIT negativo (crédito suposto
   aproveitável), com a mesma convenção do NOPAT histórico.
8. **Erros explícitos:** `terminal.g_nominal` acima de `settings.terminal.g_nominal_max`,
   alíquota manual acima do limite e lista explícita mais curta que a projeção geram erro.
9. `pares.setor` é opcional (`null`). Os setores ficam em `config/setores.yaml` (`commodity`,
   `tipo_modelo` e `pares`; os pares chegam na Fase 8).
10. Os caracteres das mensagens no código seguem ASCII (`x`, `-`), como o resto do código e o
    `ruff` (RUF001).

## Consequências

- Os YAMLs dos pilotos (`config/empresas/{PETR4,VALE3,WEGE3}.yaml`) ficam quase todos em
  `sugerido`, com o setor definido; mudam de valor quando novos dados entram.
- O primeiro ano projetado parte do último exercício completo e **ignora o YTD já divulgado** do
  ano corrente (com data-base em 30/10/2026, a WEG cresce 16,9% em 2026 sobre 2025, sem olhar o
  acumulado até setembro). Ancorar o primeiro ano no LTM fica como possível evolução, se o usuário
  pedir.
- `caixa_extra` entra no caixa da ponte, mas não sai do capital de giro: use contas fora do ativo
  circulante.
