# ADR 0002 — Vale avaliada em BRL; caminho `usd_crp` testado com dados sintéticos

- **Data:** 2026-10-30
- **Status:** aceito

## Contexto

O guia (seções 7.4 e 16) assume que a Vale reporta em USD e a usa como piloto do método `usd_crp`.
Na DFP 2025 da CVM, porém, a coluna `MOEDA` é `REAL` para todas as companhias, inclusive a Vale
(`CD_CVM` 004170). A versão em USD é a que a Vale publica para o mercado americano (20-F), fora
das fontes da v1.

Foi considerado converter as demonstrações em BRL para USD pela cotação. Rejeitado porque:

- a conversão exige taxa de fechamento para saldos e taxa média para fluxos, e o resultado não
  reproduz as demonstrações em USD da empresa (moeda funcional, variação cambial e hedge ficam
  distorcidos);
- acrescenta ruído cambial sem ganho: fluxos em BRL descontados por taxa em BRL já são
  consistentes (`brl_direto`).

## Decisão

- A Vale continua piloto, avaliada em BRL com `brl_direto`, como PETR4 e WEGE3.
- A detecção de moeda (`MOEDA` ≠ `REAL`) e o método `usd_crp` continuam implementados, mas são
  testados só com dados sintéticos até aparecer uma empresa que reporte em outra moeda na CVM.
- `moeda_relatorio: auto` no YAML da empresa continua sendo o padrão.
