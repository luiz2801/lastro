# ADR 0026 — Aba Valuation em cartões e comparação com setor e mercado

- **Data:** 2026-11-05
- **Status:** aceito

## Contexto

O usuário não gostou das tabelas da aba Valuation (custo de capital e checagens) e pediu algo parecido com um
site de fundamentos (seções com cartões e um alternador de comparação com setor, subsetor e segmento). Foram
mostradas três amostras (cartões, faixa de preço e gráficos), e o usuário quis as três na tela, com a de cartões
como principal, e a comparação com setor e mercado.

## Decisão

Decidido pelo usuário em 2026-11-05:

1. **Três visuais**, escolhidos na própria aba: Cartões (padrão), Faixa de preço e Gráficos. Os números são os do `resumo.csv`,
   `wacc.csv` e `ponte_ev_equity.csv`; nada é recalculado na tela.
2. **Comparar com setor e mercado** (alternador) em todos os visuais, com três grupos: **Pares** (`setores.yaml` + `pares.incluir`
   - `pares.excluir`), **Setor CVM** (universo com o mesmo setor do cadastro da CVM e mesmo tipo de modelo) e **Ibovespa**
   (universo do mesmo tipo, sem holdings). Referência: a escolhida na aba Geral (mediana por padrão).
3. **Valuation dos grupos a partir das rodadas em `saida/`** (beta, Ke, Kd, WACC, g, upside, retorno esperado, VT), e **múltiplos**
   (P/L, EV/EBITDA, EV/EBIT, P/VP, DY) das medidas em disco, a mesma conta da aba Geral. Botões rodam os pares e o setor CVM que
   faltam, para ter Ke e WACC.

Escolhas do agente nos casos que a resposta não cobriu (podem ser revistas):

- "Setor, Subsetor e Segmento" da B3 não existem nas fontes do projeto (só o `SETOR_ATIV` da CVM, um nível); os três níveis
  viraram Pares, Setor CVM e Ibovespa.
- Upside, retorno esperado e VT dependem do horizonte do perfil: só entram na referência as rodadas com o mesmo perfil da rodada
  do ativo. Beta, Ke, Kd, WACC e g não dependem. DCF e DDM não se misturam.
- Os botões rodam com o perfil da rodada do ativo. O Ibovespa não tem botão (seriam dezenas de rodadas): usa o que já existe.
- Rodar os pares para na primeira falha; rodar o setor CVM continua nas falhas (`rodar-setor`).
- Mesmo filtro de anomalias (Tukey) dos gráficos nas referências do valuation; sem rodada, o grupo mostra "—" e n = 0.

## Consequências

- Cartões são HTML (`st.html`), com CSS próprio; os testes da aba leem o HTML em vez de `st.metric`.
- A comparação só é tão boa quanto as rodadas em disco: pares sem rodada aparecem com n = 0 e o botão de rodar.
- Abrir a comparação pela primeira vez mede o Ibovespa (dezenas de segundos); depois vale o cache em disco.
