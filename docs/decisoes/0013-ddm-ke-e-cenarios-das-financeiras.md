# ADR 0013 — DDM, Ke, cenários e sensibilidade das financeiras

- **Data:** 2026-10-30
- **Status:** aceito

## Contexto

A seção 11.3 do `CLAUDE.md` fixa o DDM (`Valor = Σ Div_t/(1+Ke)^t + VT/(1+Ke)^T`, VT pelo P/VP
justificado) e pede a checagem por lucro residual; a 10.4 diz que financeiras só têm Ke; a 12
pede as matrizes Ke × g e ROE_LP × Ke. Ficavam em aberto: o prazo de desconto com o ano parcial,
se a convenção de meio período do FCFF vale aqui, como o lucro residual trata o trecho parcial,
como o beta por comparáveis funciona sem estrutura de capital, o que é o "retorno esperado" sem
WACC e o que cada matriz varia.

## Decisão

1. **Desconto no fim de cada ano** (tau = dias até 31/12 do ano / 365), como na fórmula do guia;
   `dcf.convencao_meio_periodo` não se aplica ao DDM. No ano corrente entram só o lucro e os
   dividendos da fração restante. O VT é descontado pelo tau do último ano.
2. **Lucro residual com o custo de capital de cada trecho**: `c_t = d_{t−1}/d_t − 1`
   (`(1+Ke)^fração − 1` no ano corrente). Com isso e o PL fechando (`PL_t = PL_{t−1} + lucro −
   dividendos`), lucro residual e DDM coincidem por construção; divergência acima de 0,1% vira
   aviso. O `resumo.csv` traz os dois valores e a divergência.
3. **O valor é o do acionista da controladora** (lucro e PL da controladora): não há ponte EV →
   equity. Valor por ação = valor / ações em circulação (ON + PN da composição usada no market
   cap).
4. **Ke sem WACC**: mesmo beta e CAPM das não financeiras; sem Kd nem estrutura. Beta por
   comparáveis = mediana dos betas dos pares **sem Hamada** (depósitos e captações são operação,
   não alavancagem financeira). `custo_capital.kd` no YAML de uma financeira é erro (ADR 0012).
   O `wacc.csv` traz só os componentes até o Ke e a data do balanço.
5. **Retorno esperado = Ke implícito**: a taxa que, no lugar do Ke, iguala o valor ponderado dos
   cenários ao preço; comparado ao hurdle do perfil. Não há WACC implícito.
6. **Sensibilidade**: Ke × g (o payout final acompanha o g) e ROE de longo prazo × Ke, com o
   delta do ROE em rampa (zero no primeiro ano, inteiro no último) para mudar o ponto de chegada
   e não o de partida. O eixo do Ke usa `sensibilidade.wacc_{passo,faixa}`; o do ROE, os novos
   `roe_{passo,faixa}` (1 p.p. e 3 p.p.).
7. **Avisos próprios**: VT/valor acima de `dcf.alerta_tv_sobre_ev`, valor não positivo,
   divergência do lucro residual e ROE de longo prazo abaixo do Ke (P/VP justificado < 1).

## Consequências

- Saídas do `rodar` de uma financeira: `resumo.csv` (com `modelo = ddm`, ROE de longo prazo, P/VP
  justificado e implícito, lucro residual), `wacc.csv`, `projecao_{cenario}.csv` (com tau, fator,
  VP e lucro residual), `sensibilidade_ke_g.csv` e `sensibilidade_roe_ke.csv`.
- Com a NTN-F de 14,9% e ERP de 5%, o Ke dos bancos fica perto de 20% e o ROE de longo prazo do
  Itaú (19,4%) dá P/VP justificado ≈ 1: o valor sai perto do PL, metade do preço (Ke implícito de
  13%). É o que o modelo diz com essas premissas, e o aviso de ROE < Ke aparece.
- O lucro entre o balanço e a data-base fica de fora (como no FCFF), e o payout projetado não vê
  o capital regulatório (Basileia): limitação já prevista na seção 11.3 do `CLAUDE.md`.
