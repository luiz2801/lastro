# ADR 0017 — Kd manual da PETR4 (custo marginal em BRL)

- **Data:** 2026-10-30
- **Status:** aceito

## Contexto

O Kd histórico (ADR 0007) divide as despesas financeiras totais da DRE (que incluem variação
cambial e monetária) pela dívida bruta média. Na PETR4, com dívida relevante em dólar, o resultado
bruto é de 7,77% (mediana 2023–2025), abaixo da faixa [Rf, Rf + 5 p.p.]; o piso levava o Kd a 15,00%
(a própria Rf). Além de depender de um limite e não de uma taxa de mercado, o Kd histórico é
contábil: o valuation precisa do custo **marginal** de captar hoje (guia do usuário
`kd_petrobras.md`, seção 1.1).

## Decisão

1. `config/empresas/PETR4.yaml`: `custo_capital.kd: {metodo: manual, valor: 0.156}`.
2. Valor = Kd pré-imposto em BRL pelo método B/C do guia: **Rf (NTN-F longa) + spread de crédito**.
   Rf = 15,00% (NTN-F, 30/10/2026, a mesma do Ke); spread = **0,60%**, o valor do guia para rating
   BBB/BB+. O spread é **premissa do usuário, sem fonte externa conferida aqui** (como o ERP; ver
   `docs/fontes.md`). O exemplo de Rf do guia (11,80%) é ilustrativo e não foi usado.
3. Moeda coerente com o Ke (BRL), benefício fiscal pela alíquota nominal de 34% (ADR 0007), como o
   guia prescreve. Arrendamentos continuam em D (`ifrs16: divida`).
4. O Kd manual não passa pela faixa de Rf + spread do `settings.yaml`.

## Consequências

- Efeito medido em 30/10/2026 (perfil moderado): Kd 15,00% → 15,60%, WACC 16,38% → 16,51%, valor
  ponderado R$ 43,36 → R$ 42,79 (−1,3%), preço máximo de compra R$ 34,69 → R$ 34,23. A mudança é
  pequena porque o piso já neutralizava o Kd histórico; o ganho é de método.
- **É número fixo**: quando a Rf mudar, o valor precisa ser refeito à mão (Rf nova + 0,60%). Um
  método `rf_mais_spread` no YAML (acompanha a Rf de cada execução) fica como evolução possível.
- VALE3 e WEGE3 seguem com o Kd histórico limitado. A dúvida 8 da seção 19 do `CLAUDE.md` (faixa e
  piso do Kd) continua aberta para elas.
- O guia `kd_petrobras.md` fica na raiz, fora do git; os números usados estão registrados aqui.
