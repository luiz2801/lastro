# ADR 0025 — Preço teto de Bazin e recomendação

- **Data:** 2026-11-05
- **Status:** aceito

## Contexto

A Etapa 5 do `docs/backlog.md` pedia um "preço teto" e uma recomendação (compra, manter ou venda). O
preço máximo de compra do perfil (valor justo ponderado × (1 − margem de segurança), seção 8.4 do
`CLAUDE.md`) já saía no `resumo.csv` e no football field desde a Fase 9 (ADR 0016). A mensagem do
`rodar` comparava o preço com ele de forma neutra, sem sinal. As alternativas estavam no backlog: o teto
de Bazin (dividendos ÷ yield mínimo) ou só renomear o preço máximo.

## Decisão

Decidido pelo usuário em 2026-11-05:

1. **Os dois preços, com rótulos distintos.** O preço máximo de compra do perfil é a referência da
   recomendação. O **preço teto de Bazin** é informativo.
2. **Bazin:** média dos dividendos e JCP pagos (DFC, conta `dividendos_pagos`, a mesma do dividend
   yield dos múltiplos) nos últimos **5 exercícios** encerrados antes da data-base × câmbio ÷ ações em
   circulação atuais (as do valor por ação, em units quando o papel é unit) ÷ **yield mínimo de 6%**.
   Os dois números ficam em `settings.yaml > preco_teto` (`bazin_anos`, `bazin_yield_minimo`).
3. **Regra da recomendação:**
   - compra: preço ≤ preço máximo de compra **e** Ke implícito ≥ hurdle do perfil;
   - venda: preço > valor justo ponderado;
   - manter: o resto.
4. **Confiança:** baixa quando há erro de QA, VT/EV (ou VT/valor no DDM) do cenário de referência
   acima de `dcf.alerta_tv_sobre_ev`, menos pares medidos que `multiplos.min_pares` (ou nenhum) ou R²
   do beta da regressão abaixo de `custo_capital.beta.min_r2_aviso`. **Confiança baixa rebaixa a
   compra para manter**; venda e manter não mudam. Os motivos vão para a saída.
5. Exibição: colunas novas no `resumo.csv`, linhas na CLI, linha própria do Bazin no football field
   (PNG e GUI) e cartões na aba Valuation.

Escolhas do agente nos casos que a pergunta não cobriu (podem ser revistas):

- Exercício da janela sem dado (sem DFP ou NaN) fica fora da média, com aviso. Com menos de 5, a
  média usa os que houver. Sem dividendo médio positivo, o teto fica vazio ("—"), com aviso.
- Ke implícito sem solução não atende ao hurdle: com preço abaixo do máximo, o sinal é manter.
- VT/EV indefinido (EV ≤ 0) conta como motivo de confiança baixa.
- Preço igual ao preço máximo ainda é compra; preço igual ao valor ponderado ainda é manter.

## Consequências

- `analise/decisao.py` (puro): `teto_bazin`, `motivos_baixa_confianca`, `recomendar`.
- `resumo.csv` ganha `preco_teto_bazin`, `dividendo_por_acao_bazin`, `yield_minimo_bazin`,
  `recomendacao`, `recomendacao_modelo` (antes do rebaixamento), `confianca` e `motivos_confianca`.
  Rodadas antigas não têm essas colunas: a GUI mostra "—" e pede para rodar de novo.
- O QA passa a rodar antes do `resumo.csv` (o resultado é o mesmo, gravado em `qa.json`).
- Limites: o teto de Bazin usa dividendos pelo regime de caixa (pagos no ano, não declarados), as
  ações de hoje (sem ajuste de desdobramento no passado) e o mesmo valor para todas as classes. Ele
  ignora crescimento e risco. A recomendação continua sendo estudo pessoal, não recomendação de
  investimento.
