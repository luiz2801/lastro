# ADR 0015 — Units no market cap

- **Data:** 2026-10-30
- **Status:** aceito

## Contexto

A composição do capital da CVM só separa ações ON e PN, e o market cap (Fase 3) ignorava units.
Companhias cujo papel líquido é a unit ficavam sem market cap (BPAC11, BRBI11: "nenhuma classe
ON/PN com preço") ou dependiam de ON/PN pouco negociadas: BPAC3 + 2 × BPAC5 = R$ 58,05 contra
BPAC11 a R$ 51,55 em 30/10/2026. O FCA (`valor_mobiliario`) informa a composição da unit na coluna
`Composicao_BDR_Unit`, em texto livre ("1 ON + 1 PN", "2 ações preferenciais e 1 ação ordinária").

## Decisão

1. Coluna nova e opcional `acoes_por_unit` em `config/cadastro_manual.csv` (só em linhas de
   unit; inteiro ≥ 2), preenchida à mão a partir do FCA. Arquivo sem a coluna continua válido.
2. Unit cotada com `acoes_por_unit` conhecido: ON e PN em circulação valem preço da unit / ações
   por unit, com aviso. A unit é o papel líquido; o preço de ON e PN avulsas é ignorado.
3. Configurados: BPAC11 = 3 (1 ON + 2 PNA), BRBI11 = 3 (1 ON + 2 PN), SANB11 = 2 (1 ON + 1 PN).

## Consequências

- BPAC11 (R$ 198,7 bi) e BRBI11 (R$ 1,1 bi) entram nos pares de bancos; SANB11 passa a usar a unit
  (R$ 89,7 bi, contra R$ 89,8 bi pelas classes avulsas).
- Supõe o mesmo preço por ação para ON e PN dentro da unit (a mesma aproximação do valor por ação
  igual entre classes, seção 11.2 do `CLAUDE.md`).
- Units do Ibovespa fora da lista (TAEE11, KLBN11, ENGI11, IGTI11) continuam pelas classes avulsas
  até alguém preencher a coluna.
