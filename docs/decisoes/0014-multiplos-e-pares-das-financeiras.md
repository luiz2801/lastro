# ADR 0014 — Múltiplos e pares das financeiras

- **Data:** 2026-10-30
- **Status:** aceito

## Contexto

A seção 11.4 do `CLAUDE.md` pede, para financeiras, P/L, P/VP, dividend yield e ROE, com
"regressão opcional P/VP × ROE entre pares", calculados pelo mesmo pipeline contábil do alvo. O
usuário pediu pares que "abranjam o máximo de empresas possíveis". O cadastro tem 21 bancos e 4
seguradoras listados; BPAN4, MERC4 e DMFN3 não têm cotação, BPAC11 e BRBI11 só cotam a unit, e
BSLI4 (BRB) não tem DRE anual em parte dos anos. Ao medir os pares, SANB11, BRSR6, BMEB4, BNBR3 e
BMIN4 saíram com P/VP perto de 0,001: quantidade de ações em milhares na CVM (ADR 0003).

## Decisão

1. **Múltiplos das financeiras: P/L, P/VP e dividend yield**, sem múltiplos de EV (dívida de banco
   é operação). Lucro e PL da controladora, dividendos pagos no LTM e ROE LTM sobre o PL da
   controladora de 12 meses antes (`contabil.financeiras.metricas_ltm`). O ROE vai à tabela dos
   pares.
2. **Regressão P/VP × ROE** (mínimos quadrados, sem winsorizar) entre os pares com os dois
   definidos, com pelo menos `multiplos.min_pares` pontos e ROE com variação; senão, aviso. O
   P/VP previsto no ROE do alvo dá um valor por ação (`valor_regressao_pvp_roe` no `resumo.csv`),
   mostrado com o R².
3. **Pares** (decisão do usuário): setor `bancos` com os 18 bancos cotados (inclusive os
   ilíquidos, cujos extremos a winsorização 10/90 segura) e setor `seguradoras` com BBSE3,
   CXSE3, PSSA3 e IRBR3.
4. **Escala das ações**: `escala_acoes: 1000` no cadastro manual para todas as classes de
   Santander, Banrisul, Mercantil do Brasil, Banco do Nordeste e Mercantil Investimentos.
5. **`rodar` de financeira sempre mede os pares** (como o das não financeiras); par sem dados
   vira aviso.

## Consequências

- Itaú contra 14 pares medidos: P/L mediano 6,0x, P/VP 0,7x, DY 6,6%; regressão P/VP = 0,40 +
  2,56 × ROE (R² 0,61), que no ROE do Itaú (22,5%) dá P/VP 1,0x.
- Pares com balanço antigo (ABCB4, último em 2023-12-31) entram com a data na tabela, como nas não
  financeiras.
- BPAC11 e BRBI11 ficam como "par ignorado" até o market cap tratar units (ADR seguinte); BSLI4
  fica de fora por falta de LTM.
