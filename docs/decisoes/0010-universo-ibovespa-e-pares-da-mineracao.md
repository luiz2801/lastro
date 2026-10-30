# ADR 0010 — Universo do Ibovespa e pares da mineração

- **Data:** 2026-10-30
- **Status:** aceito

## Contexto

A dúvida 19.4 do `CLAUDE.md` tinha uma metade pendente (o universo) e o ADR 0009 deixou a VALE3
com 2 pares (CMIN3 e CBAV3), todos os múltiplos dela em "baixa confiança". Não existe outro par
puro: no cadastro da CVM, "Extração Mineral" só tem VALE3, CBAV3 e CMIN3 (e holdings da Vale).
As duas decisões foram do usuário em 2026-10-30.

## Decisão

1. **Universo** = carteira teórica do Ibovespa da B3, lida do JSON público `GetPortfolioDay`
   (ver `docs/fontes.md`): 76 ativos em 30/10/26, gravados em `config/universo_ibovespa.csv`
   com `ticker;cnpj;setor_cvm;tipo_modelo` e cabeçalho com data e fonte. Atualização manual a
   cada quadrimestre (decisão 18 do guia).
2. **Cadastro manual** para os três tickers do universo que o FCA não resolve: BPAC11 (unit com
   código `000000`), CEAB3 (fim de negociação igual ao início) e MBRF3 (Marfrig após a
   incorporação da BRF; o FCA só lista o ADR; não confirmado que a DFP já consolida a BRF).
3. **CSNA3 entra nos pares de `mineracao`** (completa o ADR 0009, item 1), mantendo `siderurgia`
   separada. É integrada (minério e aço) e controla a CMIN3, o que enviesa a mediana; a escolha é
   deliberada e fica registrada em comentário no `setores.yaml`.

## Consequências

- `atualizar --tudo` funciona (53 s para 83 companhias com os zips em cache).
- A VALE3 passa a ter 3 pares em 5 dos 7 múltiplos; P/L e EV/FCF continuam com 2, porque a CSNA3
  tem lucro e FCFF negativos no LTM.
- Das 76, 9 são financeiras (Fase 10) e 2 holdings (fora da v1); o `rodar` só avalia as 65 não
  financeiras, e só as que tiverem YAML e setor em `setores.yaml`.
- Units (BPAC11) não têm market cap no cálculo atual.
