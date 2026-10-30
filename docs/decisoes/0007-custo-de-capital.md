# ADR 0007 — Custo de capital: Kd histórico limitado, alíquota do benefício fiscal e precedências

- **Data:** 2026-10-30
- **Status:** aceito

## Contexto

A Fase 6 implementa beta, CAPM, Kd e WACC (seção 10 do `CLAUDE.md`). O guia deixa em aberto pontos
que mudam números:

- o Kd histórico é "despesas financeiras com dívida / dívida bruta média (limitado por faixas
  razoáveis)", mas a DRE da CVM só traz as **despesas financeiras totais** (`3.06.02`), que incluem
  variação cambial e monetária, encargos e juros de arrendamento. Nos pilotos (mediana 2023–2025),
  Petrobras dá 7,8% (dívida majoritariamente em dólar), Vale 17,8% e WEG 44,1% (pouca dívida e
  despesas financeiras de outra natureza);
- qual alíquota usar no benefício fiscal da dívida;
- de onde vem a inflação brasileira de longo prazo do método `usd_crp`;
- qual beta vale quando o `settings.yaml` e o YAML da empresa divergem;
- que dívida e que data entram nos pesos do WACC.

## Decisão

1. **Kd histórico** = mediana, nos últimos 3 exercícios encerrados, de `-despesas_financeiras /
   média(dívida bruta do início e do fim do ano)`, só em anos consecutivos e com dívida média > 0.
   O resultado é **limitado a [Rf + `kd.spread_min`, Rf + `kd.spread_max`]** (novos parâmetros
   em `settings.custo_capital.kd`, placeholders 0 e 5 p.p.), sendo Rf a da moeda de reporte
   (NTN-F em BRL, `rf_usd` em USD). Fora da faixa, o Kd é o limite mais próximo e sai um aviso.
   `custo_capital.kd: {metodo: manual, valor}` no YAML da empresa ignora o histórico.
2. **Benefício fiscal** pela **alíquota nominal** (`impostos.aliquota_nominal`), não pela
   efetiva: o benefício é marginal e a efetiva histórica pode ser distorcida por JCP e incentivos.
3. **Inflação brasileira de longo prazo** (`usd_crp` para empresa em BRL) = mediana do Focus para o
   **ano mais distante** publicado. A inflação americana continua manual (`inflacao_usd_lp`).
4. **Quem reporta em USD usa `usd_crp`** mesmo com `metodo: brl_direto` no `settings`, com aviso.
5. **Precedência do beta**: `custo_capital.beta` do YAML da empresa, quando declarado, vence o
   `settings.custo_capital.beta.metodo`. Na regressão, a janela, o Blume e o R² mínimo vêm sempre
   do `settings`.
6. **Regressão**: preços ajustados (`adj_close`) até a data-base, último preço de cada semana
   (sexta), retornos simples, últimas `janela_semanas` semanas; menos de 52 semanas ⇒ erro. A classe
   de ação usada é a de maior **volume financeiro mediano** (close × volume) na janela. Avisos: R²
   abaixo do mínimo, janela incompleta, mais de 10% das semanas sem variação (baixa liquidez).
7. **Pesos do WACC**: equity = market cap na data-base (convertido para USD pelo câmbio do dia se a
   empresa reporta em USD); dívida = **dívida bruta** (com arrendamento se `ifrs16: divida`) do
   **último balanço até a data-base**. `divida_extra` (pensão, contingências) fica fora dos pesos;
   entra só na ponte da Fase 7. Balanço mais de 140 dias antes da data-base gera aviso.
8. **Estrutura-alvo `manual`** exige `estrutura_alvo.divida_sobre_capital` (D/(D+E)); o beta da
   regressão é desalavancado na estrutura atual e realavancado no alvo (Hamada). `setor` e beta por
   `comparaveis` dependem dos pares (Fase 8) e hoje dão erro explicativo.
9. Comando novo **`valuation wacc TICKER`**, fora da seção 14 do `CLAUDE.md`, para gerar o
   `wacc.csv` (critério de pronto da Fase 6) antes de existir o `rodar`.

## Consequências

- O Kd dos pilotos hoje é decidido pelo limite (Petrobras no piso, WEG no teto); só a Vale fica com
  o valor histórico. A faixa é placeholder: o usuário precisa revisá-la (seção 19 do `CLAUDE.md`).
- O piso em Rf faz a dívida em dólar da Petrobras custar o mesmo que um título soberano em BRL, o
  que é conservador e aproxima o custo em reais da dívida em moeda forte (paridade de juros).
- WACC menor ou igual ao g terminal é erro já na Fase 6.
- O DCF (Fase 7) consome `wacc.CustoCapital`, montado por `cli._custo_capital`.
