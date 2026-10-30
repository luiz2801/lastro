# ADR 0003 — Escala da quantidade de ações

- **Data:** 2026-10-30
- **Status:** aceito

## Contexto

O arquivo de composição do capital da CVM não tem coluna de escala. Observado em 2026-10-30:

- Vale: todas as datas em milhares (4.262.534 ações em 2026-03-31, contra cerca de 4,26 bilhões).
- Petrobras: só a DFP 2020 em milhares (13.044.497); as demais em unidades (13.044.496.930).
- WEG: unidades; a metade em 2020 é o desdobramento 2:1 de 2021, não erro de escala.

## Decisão

Duas camadas, aplicadas na ingestão (`cvm.corrigir_escala_acoes`):

1. `escala_acoes` em `config/cadastro_manual.csv` (1 ou 1000) para companhias que informam tudo em
   milhares. Hoje só a VALE3.
2. Correção automática: datas com 500x a 2000x menos ações que a data mais recente são multiplicadas
   por 1000, com aviso no log. Desdobramentos e grupamentos reais têm razões pequenas e não caem na
   faixa.

A escala usada fica gravada por linha (`escala_acoes_aplicada`).

## Consequências

- Uma companhia inteira em milhares sem entrada no cadastro manual passa sem correção. A checagem
  de market cap contra o preço (Fase 3) deve pegar esse caso.
- Se a data mais recente for a errada, a correção automática erra junto. A checagem da Fase 3
  também cobre isso.
