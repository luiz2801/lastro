# ADR 0018 — ERP implícito do Ibovespa em BRL (regra de crescimento esperado)

- **Data:** 2026-10-30
- **Status:** proposto (aguarda aprovação do usuário; nenhum código foi escrito)

## Contexto

Hoje `custo_capital.erp` é a premissa de 5,0% do usuário, sem fonte (`docs/fontes.md`). A opção D da
decisão sobre o ERP é calibrá-lo no preço do próprio mercado: o `ke` que iguala o valor do
Ibovespa ao valor presente dos fluxos aos acionistas, e `ERP = ke − Rf` (com a mesma Rf em BRL do
Ke das empresas, sem somar `crp`; seção 10.2 do `CLAUDE.md`). O ponto frágil é o crescimento
esperado desses fluxos: não há consenso de analistas (decisão 12), então a única âncora externa é
o Focus.

## Decisão proposta

1. **Fluxo agregado.** Soma, sobre os componentes de `config/universo_ibovespa.csv` com balanço
   disponível, dos dividendos e JCP pagos no LTM (`dividendos_pagos`). Recompras ficam fora na v1
   (a DFC da CVM não tem conta mapeada) e o resultado leva aviso: o fluxo é subestimado, logo o
   `ke` e o ERP também. O valor do índice é o market cap agregado dos mesmos componentes, na
   data-base (multi-classe, sem tesouraria). Componente sem fluxo ou sem market cap sai dos dois
   lados e é listado nos avisos.
2. **Crescimento em duas fases**, com `N = 5` anos explícitos:
   - `g_longo = min(PIB real do Focus + IPCA do Focus, terminal.g_nominal_max)`, tomando o último
     ano divulgado do Focus (horizonte de 4 anos à frente) e aplicando-o à perpetuidade.
   - `g_curto = min(CAGR de 5 anos do fluxo agregado, g_longo + 5 p.p.)`, piso em 0. O histórico
     manda no curto prazo, mas nunca passa um teto ligado ao Focus.
   - `g_t` converge linearmente de `g_curto` (ano 1) para `g_longo` (ano N); depois da fase
     explícita, perpetuidade a `g_longo`.
3. **Equação.** `P0 = Σ_{t=1..N} FC_t/(1+ke)^t + [FC_N × (1+g_longo)/(ke − g_longo)]/(1+ke)^N`,
   com `FC_t = FC_0 × Π(1+g_s)`, resolvida por `brentq` em `ke > g_longo`. Fluxos no fim de cada
   ano (como o DDM, ADR 0013).
4. **Saída é faixa, não número.** Central com `g_longo`; limites com `g_longo ± 1 p.p.` e `g_curto`
   recalculado de acordo. `custo_capital.erp.fonte: implicito_ibovespa` usa o **central** no Ke e
   imprime/grava a faixa. Avisos: faixa mais larga que 2 p.p., ERP central fora de [2%, 10%], menos
   de 80% do valor do índice coberto, recompras ignoradas. Fora de [0%, 15%] ou sem Focus ⇒ erro
   pedindo `fonte: manual` (falha alto).
5. **Campo e padrão.** `custo_capital.erp: {fonte: manual | implicito_ibovespa, valor: 0.05}`; o
   padrão continua `manual` com 5,0%, para não mudar nenhum resultado existente sem pedido.
6. **Fora do escopo.** ERP por setor, calibração no preço da empresa avaliada e `crp` em BRL. O
   yield spread (earnings yield − NTN-F) segue como termômetro de contexto, nunca como insumo.
7. **Fonte nova.** O Focus de PIB (`Indicador eq 'PIB Total'` em `ExpectativasMercadoAnuais`)
   `[VALIDAR]` na API real e registrar em `docs/fontes.md` antes de codar.

## Consequências

- Código: `custo_capital/erp_implicito.py` (função pura, sem rede nem `date.today()`), campo
  em `config.py` e `settings.yaml`, leitura do Focus de PIB em `data/macro.py`, agregação na CLI.
  Testes calculados à mão (fluxo constante com `g` conhecido ⇒ `ke = FC1/P0 + g`, Gordon).
- Exige `valuation atualizar --tudo` (as 76 companhias) para o fluxo agregado ser confiável.
- Limitações: o fluxo exclui recompras; o crescimento do curto prazo é histórico e pode refletir
  ciclo de commodities (Vale e Petrobras pesam muito no índice); o resultado é um termômetro do
  mercado, não uma verdade.

## Perguntas para o usuário

- Aceita a regra do item 2 (teto Focus no longo prazo, histórico no curto, convergência em 5 anos)?
- `N = 5` e a faixa de ±1 p.p. em `g_longo` estão bons, ou prefere outros valores?
- Usar o ERP central no Ke (item 4) ou manter `manual` como padrão e só exibir o implícito?
