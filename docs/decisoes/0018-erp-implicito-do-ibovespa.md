# ADR 0018 — ERP implícito do Ibovespa em BRL

- **Data:** 2026-10-30
- **Status:** aceito (regras escolhidas pelo usuário; padrão do `settings.yaml` ainda `manual`, ver Consequências)

## Contexto

`custo_capital.erp` era a premissa de 5,0% do usuário, sem fonte (`docs/fontes.md`). A opção D da
decisão sobre o ERP calibra-o no preço do mercado: o `ke` que iguala o valor do Ibovespa ao valor
presente dos dividendos agregados, e `ERP = ke − Rf` (mesma Rf em BRL do Ke das empresas, sem
`crp`; seção 10.2 do `CLAUDE.md`). Sem consenso de analistas (decisão 12), a âncora externa de
crescimento é o Focus.

## Decisão

Respostas do usuário às perguntas da proposta: curto prazo pelo Focus, depois dele a média
histórica, convergência a mais simples, cinco anos e uso do ERP implícito no Ke (opção B).

1. **Fluxo e valor.** Soma, sobre os componentes de `config/universo_ibovespa.csv`, dos dividendos e
   JCP pagos no LTM (`dividendos_pagos`) e do market cap (multi-classe, sem tesouraria). Uma
   companhia entra uma vez (duas classes contam uma). Companhia com erro (holding, sem preço, sem
   balanço, moeda não BRL) sai dos dois lados e vira aviso; companhia que não pagou dividendos
   **fica** (fluxo zero). Recompras ficam fora na v1 (sem conta mapeada na DFC): aviso, fluxo
   subestimado, ERP tende a ficar abaixo do real.
2. **Crescimento em N = 5 anos explícitos.** O ano 1 é o ano da data-base. Em cada ano com PIB real
   **e** IPCA no Focus (`ExpectativasMercadoAnuais`, indicadores `PIB Total` e `IPCA`, mediana,
   última pesquisa até a data-base), o crescimento é nominal: `(1 + PIB) × (1 + IPCA) − 1`. Ano sem
   Focus usa o g perpétuo.
3. **Perpetuidade e "média histórica".** `g perpétuo = CAGR de 5 anos da soma dos dividendos`
   (média geométrica, nas companhias com dividendo positivo nas duas pontas, último exercício
   presente em ao menos metade delas), com piso 0 e teto `terminal.g_nominal_max` (5,0%).
4. **Convergência: nenhuma** (degrau). Os anos do Focus e a perpetuidade se encadeiam sem transição.
5. **Equação.** `P0 = Σ_{t=1..N} FC_t/(1+ke)^t + [FC_N × (1+g)/(ke − g)]/(1+ke)^N`, com
   `FC_t = FC_0 × Π(1+g_s)`, resolvida por `brentq` em `ke > g`; fluxos no fim do ano (como o DDM,
   ADR 0013).
6. **Faixa.** Central com o g do item 3; limites com `g ± faixa_g` (1 p.p., piso 0). Só o g perpétuo
   muda; os anos do Focus ficam. O Ke usa o **central** (opção B).
7. **Avisos e erro.** Aviso: ERP central fora de [2%, 10%], faixa mais larga que 2 p.p., menos de
   80% do universo medido, recompras ignoradas. **Erro** (sem gravar; os números saem antes): ERP
   central fora de [0%, 15%], Focus de PIB/IPCA ausente, fluxo ou valor não positivos.
8. **Campo e arquivo.** `custo_capital.erp: {fonte: manual | implicito_ibovespa, valor,
   anos_explicitos: 5, faixa_g: 0.01, validade_dias: 30}`; um número solto no YAML vale `manual`.
   `valuation erp` calcula e grava `data/processed/erp_implicito.json`; `wacc` e `rodar` o leem
   quando `fonte = implicito_ibovespa` e falham se ele faltar ou tiver mais que `validade_dias`
   da data-base (a agregação de ~70 companhias não roda a cada comando).
9. **Fora do escopo.** ERP por setor, calibração no preço da empresa avaliada e `crp` em BRL. O yield
   spread segue como termômetro de contexto.

## Consequências

- **Resultado em 30/10/2026 (dados reais):** 70 de 74 companhias (BRAP4 e ITSA4 holdings, KLBN11 sem
  preço, TIMS3 sem balanço), valor R$ 4.033 bi, dividendos LTM R$ 215 bi (yield 5,3%), Focus nominal
  de 7,1% a 5,6% nos 5 anos, g perpétuo 5,0% (o CAGR de 23% parte de 2020, um fundo, e o teto
  manda), **ke do mercado 10,8% contra Rf de 15,0%: ERP implícito de −4,2%** (faixa −5,0% a −3,4%).
  O comando recusa o resultado (item 7) e não grava.
- Leitura: com a NTN-F em 15%, o preço do índice só se justifica por dividendos com um retorno
  abaixo da renda fixa; é o mesmo sinal do yield spread (earnings yield − NTN-F ≈ −5,5 p.p.).
  Um ERP negativo não serve de insumo do Ke. Por isso o `settings.yaml` ficou em `manual` (5,0%);
  trocar para `implicito_ibovespa` só faz sentido quando `valuation erp` passar a gravar.
- Código: `custo_capital/erp_implicito.py` (puro), `ConfigErp`, `Macro.pib_esperado`, `_macro`,
  `_medir_para_erp`, `erp` e `_erp_efetivo` na CLI. Testes à mão (Gordon, um ano explícito).
- Limitações: dividendos, não lucros (payouts baixos deprimem o `ke`); sem recompras; o CAGR de 5
  anos é sensível ao ponto inicial; resultado é termômetro do mercado, não verdade.
