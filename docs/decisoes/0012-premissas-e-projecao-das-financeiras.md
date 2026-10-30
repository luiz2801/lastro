# ADR 0012 — Premissas e projeção das financeiras (DDM)

- **Data:** 2026-10-30
- **Status:** aceito

## Contexto

A seção 11.3 do `CLAUDE.md` define o DDM em dois estágios: ROE convergindo linearmente para o
ROE de longo prazo (`ROE_LP`, "sugerido pela mediana histórica"), payout convergindo para
`1 − g/ROE_LP` e `LL_t = ROE_t × PL_{t−1}`. Ficavam em aberto: qual mediana, de onde parte o
payout, como escrever isso no YAML da empresa (seção 9.1, feita para o FCFF), o que os cenários
variam e onde começa a projeção.

Inspeção (ITUB4, 2016–2025): ROE de 13,8% (2020) a 21,6% (2024); payout de caixa entre 23% e 108%
(2025, com extraordinários) e mediana de 5 anos de 31%.

## Decisão

1. **ROE de longo prazo = mediana de 10 anos** (decisão do usuário); o ROE parte da mediana de 5
   anos e converge linearmente até ele. ROE histórico sobre o PL da controladora do início do ano
   (ADR 0011).
2. **Payout** parte da mediana de 5 anos (limitada a [0, 100%]; sem dividendos no histórico, o de
   longo prazo) e converge linearmente para `1 − g/ROE_LP`. Esse fim **não é configurável**: é o
   que sustenta g na perpetuidade. ROE_LP ≤ g é erro.
3. **YAML por tipo**: numa financeira, `projecao:` traz `horizonte_anos`, `roe` (trajetória ou
   lista), `payout_inicio` e `terminal.g_nominal`; `cenarios:` traz `roe_pp`. Só `consolidado` e
   `mapeamento_extra` valem em `ajustes`, e `custo_capital.kd` não se aplica; o resto gera erro. O
   esquema é escolhido pelo `tipo_modelo`.
4. **Cenários**: ±1 desvio-padrão (10 anos) do ROE, limitado a [1, 5] p.p., somado ao ROE de
   **todos** os anos, inclusive o de longo prazo (o payout final acompanha). É o análogo da
   margem no FCFF, que também chega à perpetuidade.
5. **A projeção parte do PL da controladora no último balanço até a data-base** e começa no
   primeiro exercício aberto (o corrente, com a fração restante do ano); a lista de ROE do YAML
   começa nesse ano (no FCFF, começa no ano seguinte ao último histórico). Não há ano-ponte: o
   lucro entre o balanço e a data-base fica de fora, como no FCFF.

## Consequências

- Itaú hoje: ROE 19,7% → 19,4% e payout 31% → 74% (g = 5%); o payout inicial baixo vem dos anos de
  restrição do BCB (2020–2021) e da defasagem de caixa.
- `projecao/financeira.py` concentra sugestão, resolução, cenários e projeção; o projetor do FCFF
  não muda (só expõe `linear`, `escolher` e `trajetoria`).
- O DDM, o Ke e a ponderação dos cenários vêm no ADR seguinte.
