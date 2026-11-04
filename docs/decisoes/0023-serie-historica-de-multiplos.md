# ADR 0023 — Série histórica de múltiplos e anomalias da GUI

- **Data:** 2026-11-04
- **Status:** aceito

## Contexto

A S2 da Sprint GUI 1 mostra P/L, P/VP, EV/EBITDA, EV/EBIT e dividend yield em série. As decisões do
backlog (terceira rodada, 2026-11-03) supunham duas coisas que a fonte real desmentiu:

- **A CVM não tem a quantidade de ações dos 10 anos.** A composição do capital só existe a partir de
  31/03/2020: o ITR 2017 e o 2019 não trazem o arquivo, e o ITR 2020 e o 2021 trazem (conferido em
  2026-11-04). O `docs/fontes.md` dizia "em todos os ITR", e estava errado.
- **Só com a coleta normal, o LTM muda uma vez por ano** fora dos 2 últimos anos, porque `atualizar`
  baixa só ITR de `ano` e `ano - 1`.

O `DT_RECEB` existe e está sempre preenchido no CSV-índice de cada zip
(`{dfp,itr}_cia_aberta_{ano}.csv`), com uma linha por versão.

A fórmula aprovada, Close ajustado(t) × ações vigentes × F(t), erra entre um split e a composição
seguinte. WEGE3 fez 2:1 em 28/04/2021; a composição vigente em 15/05/2021 (de 31/03) tem 2,1 bi de
ações pré-split e F(15/05) = 1, logo o market cap sairia pela metade até 30/06.

## Decisão

Escolhas do usuário, em 2026-11-04, entre opções apresentadas:

1. **Lacuna antes de 2020.** Múltiplos só a partir de 31/03/2020 (cerca de 6,5 anos), com o motivo na
   tela. A cotação continua com os 10 anos. Sem estimar a quantidade de ações pelos splits.
2. **F na data da composição.** Market cap(t) = Close ajustado(t) × ações(c) × F(c), com c = data da
   composição vigente em t e F(c) = produto dos fatores de split posteriores a c. Substitui a fórmula
   com F(t) do backlog.
3. **Corte fixo (n < 15):** P/L 80x, P/VP 15x, EV/EBITDA 40x, EV/EBIT 60x (`multiplos.corte_*`).
   Julgamento, não dado de mercado.
4. **Data de divulgação = 1ª divulgação** do período (o `DT_RECEB` mais antigo). Os valores continuam
   os da última versão, como no resto do projeto, o que traz um pequeno olhar para o futuro em
   reapresentações. Sem a data: fim do período + 45 dias (ITR) ou + 90 dias (DFP).

Consequências desses itens no desenho, decididas na implementação sem efeito sobre o que é mostrado:

5. **ITR a partir de 2019, não de 2016.** A opção escolhida previa baixar 2016–2024. Sem quantidade de
   ações antes de 2020 nenhum múltiplo é calculável, e o LTM de 03/2020 precisa do balanço de 03/2019.
   Baixar 2016–2018 gastaria cerca de 75 MB sem mudar nenhum número.
6. **Arquivos à parte:** `series_itr.parquet`, `series_composicao.parquet` e `divulgacoes.parquet` em
   `data/processed/cvm/{cd_cvm}/`. `demonstracoes.parquet`, `composicao_capital.parquet` e
   `contas_padronizadas.parquet` não mudam, então `rodar` e os demais comandos dão o mesmo resultado.
7. **Aviso de splits:** variação das ações da CVM diferente dos splits do yfinance em mais de 5% entre
   duas composições (`TOLERANCIA_SPLITS`). Emissão ou recompra grande também aparece: daqui não dá para
   distingui-las de um split não listado.
8. **Métrica que pode ser negativa, ou de só marcar, com menos de 4 pontos:** sem quartil, sem corte.

## Consequências

- `comparar` e `modelos/multiplos.py` não mudam. `analise/anomalias.py` é usado só pela GUI; unificar
  depende de outro ADR, comparando os valores implícitos antes e depois.
- A janela de "10 anos" dos múltiplos hoje tem cerca de 6,5 anos, e cresce com o tempo.
- Companhia com a composição escrita em milhares em parte das datas é corrigida por
  `corrigir_escala_acoes`, agora também nos ITR antigos (Petrobras em 2020–2021).
- Um FRE (Formulário de Referência) traz quantidade de ações antes de 2020, mas sem tesouraria e por
  versão de formulário. Fica como caminho possível, se a lacuna incomodar.
