# ADR 0005 — Padronização contábil: reapresentações, dívida x arrendamento e métricas

- **Data:** 2026-10-30
- **Status:** aceito

## Contexto

A Fase 2 transforma DFP/ITR em contas padronizadas e métricas. O guia (seções 7.2, 7.3 e 7.6)
deixa como ponto de partida alguns códigos `[VALIDAR]` e não fixa detalhes que mudam números:
qual documento vence para um período reapresentado, onde está o arrendamento, de onde vem a D&A e
qual alíquota entra no NOPAT histórico. A inspeção dos três pilotos (2016–2026) mostrou:

- Vale, DFP 2022: custo dos produtos com sinal positivo; a DFP 2023 (`PENÚLTIMO`) traz o mesmo ano
  com o sinal certo.
- Códigos de conta mudam entre trimestres (D&A da Vale `6.01.01.05` × `6.01.01.06`).
- Arrendamento dentro de empréstimos (`2.01.04.03`/`2.02.01.03`) em Petrobras e Vale, e em
  "outras obrigações" na WEG.
- Petrobras 2019–2022: a D&A da DVA (`7.04.01`) é maior que a da DFC (ex.: 2022, 75.121 × 68.202).

## Decisão

1. **Reapresentação:** por família de demonstração (BPA, BPP, DRE, DFC, DVA) e período
   (`dt_ini`, `dt_fim`), vale o documento mais recente (`dt_refer`, depois `versao`), e **todas** as
   contas daquele período vêm dele. Corrige o sinal da Vale 2022 e evita somar códigos que mudaram.
2. **Regras do plano de contas:** por período vence a primeira regra que casa; regex em `DS_CONTA`
   sem acentos; com várias contas casadas, soma só as de nível mais alto.
3. **Dívida e arrendamento separados:** `divida_financeira = empréstimos − arrendamento dentro de
   empréstimos`; `arrendamento = dentro + fora de empréstimos`. `ifrs16: divida` soma os dois na
   dívida bruta.
4. **D&A pela DFC** (valor somado de volta ao caixa, coerente com o FCFF), com a DVA como
   alternativa. O QA avisa quando as duas divergem mais de 5%.
5. **Fluxos a partir do acumulado no ano:** trimestre = diferença de YTDs; LTM = exercício + YTD
   atual − YTD do ano anterior. O trimestre isolado da DRE não é usado (só confere).
6. **Métricas históricas:**
   - `ebitda` = EBIT contábil + D&A (definição das companhias, bate com os releases);
   - `ebit_ajustado` exclui a equivalência patrimonial (`coligadas: somar_investimento_contabil`,
     o investimento entra na ponte) e os não recorrentes configurados;
   - NOPAT histórico com a alíquota efetiva limitada a [0, nominal]; nominal quando LAIR ≤ 0;
   - com `ifrs16: divida` e `capex_equivalente_arrendamento`, o FCFF desconta os pagamentos de
     arrendamento da DFC (proxy da reposição dos direitos de uso);
   - ROIC = NOPAT / média de (PL total + dívida líquida).
7. Saldos ganham `periodicidade = S` na tabela padronizada (o guia só listava A, T e YTD).

## Consequências

- Os valores de Petrobras, Vale e WEG em `tests/golden/referencias.yaml` batem com o pipeline
  (83 conferências).
- Itens que as companhias somam ao caixa (títulos da Petrobras, aplicações de LP e derivativos da
  WEG) ficam fora de `caixa_e_aplicacoes` até o YAML da empresa (`caixa_extra`, Fase 5).
- A WEG não tem linha de pagamento de arrendamento na DFC: o desconto no FCFF fica zero.
