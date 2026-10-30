# ADR 0008 — DCF, ponte EV → equity, cenários e sensibilidade

- **Data:** 2026-10-30
- **Status:** aceito

## Contexto

A Fase 7 implementa o DCF (seção 11.1 do `CLAUDE.md`), a ponte (11.2), a ponderação pelo perfil
(8.4) e a sensibilidade (12). O guia deixa em aberto pontos que mudam números:

- o que é a "TIR ao comprar a preço de mercado" comparada ao hurdle;
- o teto do crescimento perpétuo (dúvida 19.3);
- a contagem do prazo de desconto com ano parcial e meio período, e onde descontar o valor
  terminal;
- de onde vêm os saldos e a quantidade de ações da ponte;
- o que varia em cada tabela de sensibilidade;
- como cumprir o critério de pronto (valor por cenário e ponderado, sensibilidade em CSV) antes do
  comando `rodar` completo da Fase 9.

Os dois primeiros pontos foram decididos pelo usuário em 2026-10-30.

## Decisão

1. **Retorno esperado em duas leituras**, as duas no `resumo.csv` e no terminal (decisão do
   usuário):
   - **Ke implícito**: retorno do acionista que, posto no lugar do Ke dentro do WACC (Kd, alíquota
     e pesos fixos), iguala o valor ponderado ao preço. É o que se compara com o hurdle.
   - **WACC implícito**: taxa de desconto do FCFF que iguala o valor ponderado ao preço.
   Os dois são resolvidos numericamente (`scipy.optimize.brentq`) entre o g terminal e 100% a.a.;
   fora dessa faixa a taxa sai como "sem solução", com aviso. Como o valor é linear nos fluxos,
   ponderar os valores dos cenários equivale a descontar os fluxos ponderados.
2. **Teto do g perpétuo nominal = 5,0%** (`settings.terminal.g_nominal_max`, decisão do usuário,
   dúvida 19.3). Continua sendo também o g padrão e o fim da trajetória de crescimento sugerida.
3. **Prazos:** tau = dias entre a data-base e 31/12 do ano / 365. Com `convencao_meio_periodo`,
   tau = fim − fração / 2 (no ano corrente, o ponto médio do trecho por vir). Ano-ponte já
   encerrado sem DFP (fração 0) não é descontado. O **valor terminal é descontado pelo tau do
   último ano explícito** (o meio dele, com a convenção), como diz a fórmula do guia; isso é
   coerente com fluxos perpétuos recebidos no meio de cada ano.
4. **RONIC:** `wacc` acompanha a taxa de cada cálculo (inclusive cada célula da sensibilidade);
   `roic_historico` é a mediana do ROIC dos 5 últimos exercícios; RONIC ≤ g é erro. O
   `terminal.ronic` do YAML da empresa vence o `settings`. Com RONIC = WACC o g quase não muda o
   valor (crescer sem retorno acima do custo não cria valor): é esperado, não é bug.
5. **Múltiplo de saída:** o DCF mostra o EV/EBITDA implícito no terminal (VT / EBITDA do último
   ano explícito) quando `checagem_multiplo_saida` está ligada. O g implícito num múltiplo de saída
   precisa do múltiplo dos pares e fica para a Fase 8.
6. **Ponte:** saldos do mesmo balanço dos pesos do WACC (última data até a data-base com ITR/DFP);
   investimentos = conta BPA `1.02.02` inteira (inclui propriedades para investimento), somada só
   com `coligadas: somar_investimento_contabil`; minoritários pelo valor contábil
   (`multiplo_pvp` dá erro até a Fase 8); ações = ON + PN em circulação da composição usada no
   market cap. Empresa que reporta em USD tem o valor por ação convertido pelo dólar da data-base.
7. **Cenário único:** `rodar --cenario X` avalia só X e usa o valor dele como referência do preço
   máximo de compra (peso 100%). Ponderação só com os três.
8. **Sensibilidade:**
   - WACC × g varia só a taxa de desconto e o g da perpetuidade; a projeção explícita fica igual.
   - Margem EBITDA × crescimento soma deltas a todos os anos explícitos, como os cenários; as
     linhas são rotuladas pela margem do último ano e as colunas pelo crescimento médio.
   - Parâmetros novos `sensibilidade.margem_{passo,faixa}` e `crescimento_{passo,faixa}`.
   - Célula impossível (g ≥ WACC, RONIC ≤ g) fica vazia.
9. **`valuation rodar` entra na Fase 7** e já grava `resumo.csv` (sem múltiplos), `wacc.csv`,
   `projecao_{cenario}.csv` (com tau, fator e VP), `ponte_ev_equity.csv` (uma coluna por cenário)
   e as duas `sensibilidade_*.csv`. A Fase 9 completa a pasta (gráficos, `meta.json`,
   `premissas_usadas.yaml`, `qa.json`, `historico.csv`, valores reais).

## Consequências

- Com a Rf atual (NTN-F de 14,9%) os WACC dos pilotos ficam entre 16% e 18% e o VT pesa só de 32%
  a 41% do EV; o WACC implícito no preço mostra quanto o mercado desconta a menos.
- `scipy` passa a ser usado (já estava na lista da seção 4 do `CLAUDE.md`).
- O valor por ação é o mesmo para todas as classes e ignora diluição (limitações já previstas).
