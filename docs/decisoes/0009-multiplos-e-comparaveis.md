# ADR 0009 — Múltiplos e comparáveis

- **Data:** 2026-10-30
- **Status:** aceito

## Contexto

A Fase 8 implementa os múltiplos (seção 11.4 do `CLAUDE.md`) e o que dependia dos pares: beta por
comparáveis (10.1), estrutura-alvo do setor (10.3), minoritários pelo P/VP do setor (11.2) e o g
implícito num múltiplo de saída (11.1). O guia não fixava:

- quais são os pares de cada setor (dúvida 19.4);
- a definição exata de EV e das métricas, para que alvo e pares sejam consistentes com a ponte;
- como winsorizar e qual estatística dá o valor implícito;
- o que fazer com um par sem dados ou com dado implausível.

Os pares e o tratamento estatístico foram decididos pelo usuário em 2026-10-30. Ao rodar com dados
reais, 7 dos 13 pares novos tinham a composição do capital em milhares (market cap de poucos
milhões de reais), o mesmo problema do ADR 0003.

## Decisão

1. **Pares por setor** (`config/setores.yaml`, decisão do usuário):
   - `petroleo_gas` só exploração e produção: PETR4, PRIO3, RECV3, BRAV3.
   - `mineracao` separada do novo setor `siderurgia`: VALE3, CMIN3, CBAV3 (só 2 pares para a
     VALE3, todos os múltiplos dela saem com "baixa confiança"); `siderurgia`: GGBR4, GOAU4, USIM5,
     CSNA3.
   - `maquinas_equipamentos` em lista ampla: WEGE3, EMBJ3, RAPT4, TUPY3, POMO4, KEPL3, ROMI3,
     LEVE3, MYPK3, FRAS3.
   - A lista pode conter a própria empresa (é retirada no cálculo); `pares.incluir`/`excluir` do
     YAML da empresa somam e tiram tickers; classes da mesma companhia contam uma vez.
2. **Métricas** iguais para alvo e pares, do mesmo pipeline do DCF: LTM no último balanço até a
   data-base e market cap na data-base, em BRL.
   - EV = market cap + dívida bruta − caixa e aplicações + minoritários − investimentos em
     coligadas + `divida_extra`: o inverso exato da ponte, de modo que um múltiplo de EV volta
     pela mesma ponte ao valor por ação.
   - EBITDA e EBIT **ajustados** (sem equivalência quando as coligadas entram pelo investimento),
     coerentes com esse EV.
   - P/L e P/VP com lucro e PL da **controladora**; EV/FCF com o **FCFF**; dividend yield =
     dividendos pagos no LTM (DFC) / market cap.
3. **Estatística** (decisão do usuário): múltiplo com numerador ou denominador ≤ 0 é descartado;
   os válidos são limitados aos percentis 10 e 90 dos pares (`multiplos.winsorizar`); valor
   implícito pela **mediana**, com faixa P25–P75; menos de `multiplos.min_pares` (3) válidos ⇒
   "baixa confiança", com aviso. No dividend yield a relação é inversa (P25 dá o maior valor).
4. **Dado implausível:** par com P/VP < 0,05 é excluído das estatísticas, com aviso que aponta a
   escala das ações; no alvo, o mesmo sinal só avisa. Os 7 pares observados ganharam
   `escala_acoes: 1000` no cadastro manual (VALE3 continua; ADR 0003).
5. **Par sem dados** (sem `atualizar`, sem preço, sem balanço LTM) vira aviso e fica de fora; o
   `rodar` segue sem múltiplos se nenhum par for medido. `atualizar --com-pares` baixa os pares
   de cada ticker.
6. **Beta por comparáveis:** beta de cada par pela mesma regressão do alvo (classe mais líquida,
   com Blume se configurado), desalavancado pelo D/E dele (dívida bruta / market cap), mediana,
   realavancada na estrutura do alvo.
7. **`estrutura_alvo: setor`** = mediana de D/(D+E) dos pares medidos.
8. **`minoritarios: multiplo_pvp`** = PL dos não controladores × mediana do P/VP dos pares.
9. **g implícito no múltiplo de saída** = g que faz VT = EV/EBITDA mediano dos pares × EBITDA do
   último ano explícito, com o RONIC do cálculo. Com RONIC = WACC o g quase não muda o VT, então
   um múltiplo acima de cerca de VT(g → WACC) / EBITDA não tem solução ("nenhum g abaixo do
   WACC"); vai ao terminal (se `checagem_multiplo_saida`) e ao `resumo.csv`.
10. **Comando `comparar`** grava `multiplos_pares.csv` (alvo e pares) e
    `multiplos_implicitos.csv`; o `rodar` grava os mesmos e acrescenta ao `resumo.csv` o valor
    pela mediana de cada múltiplo, o número de pares, o EV/EBITDA mediano e o g implícito.

## Consequências

- O `rodar` passa a consultar preço e padronizar cada par (cerca de 1 s por par com cache).
- A WEG não tem comparável próximo na B3: os múltiplos dos pares implicam valores muito abaixo do
  preço (EV/EBITDA de 5x contra 23x). É o que os dados dizem; a faixa serve de referência, não de
  âncora.
- Com 2 pares, os múltiplos da VALE3 têm baixa confiança até que o usuário amplie o setor.
- `pares` e escala de ações são configuração: um par novo pode precisar de `escala_acoes` no
  cadastro manual; o aviso de P/VP implausível aponta o caso.
- Universo do Ibovespa (`config/universo_ibovespa.csv`, outra metade da dúvida 19.4) continua
  pendente.
