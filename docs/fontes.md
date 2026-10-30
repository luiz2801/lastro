# Fontes de dados — registro de validação

Cada URL, nome de arquivo, código de conta ou série marcado `[VALIDAR]` no guia é registrado aqui
depois de inspecionado na fonte real.

Legenda: ✅ confirmado · ⚠️ diferente do guia · ⏳ pendente

## CVM (dados.cvm.gov.br)

| Item | Esperado no guia | Status | Observado / data |
|---|---|---|---|
| Cadastro | `CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv` | ✅ | 1,5 MB, latin-1, CRLF (2026-10-30) |
| DFP | `CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_{ano}.zip` | ✅ | Anos 2010–2026 (2026-10-30); 2025 tem 13 MB |
| ITR | `CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_{ano}.zip` | ✅ | Até 2026; 2026 tem 20 MB. Mesmos arquivos internos da DFP com prefixo `itr_` |
| FCA | `CIA_ABERTA/DOC/FCA/DADOS/fca_cia_aberta_{ano}.zip` | ✅ | Até 2026; arquivo de tickers: `fca_cia_aberta_valor_mobiliario_{ano}.csv` |
| Arquivos internos da DFP | ver seção 6.1 | ✅ | `dfp_cia_aberta_{BPA,BPP,DRE,DFC_MD,DFC_MI,DMPL,DRA,DVA}_{con,ind}_{ano}.csv`, `dfp_cia_aberta_composicao_capital_{ano}.csv`, `dfp_cia_aberta_parecer_{ano}.csv`, `dfp_cia_aberta_{ano}.csv` (índice) |
| Dicionário DFP | — | ✅ | `DOC/DFP/META/meta_dfp_cia_aberta_txt.zip` (um `.txt` por arquivo) |
| Dicionário FCA | — | ⚠️ | Nome fora do padrão: `DOC/FCA/META/fca_cia_aberta.zip` |

### Observado na DFP 2025 (DRE consolidada, 2026-10-30)

- Colunas: `CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;GRUPO_DFP;MOEDA;ESCALA_MOEDA;ORDEM_EXERC;DT_INI_EXERC;DT_FIM_EXERC;CD_CONTA;DS_CONTA;VL_CONTA;ST_CONTA_FIXA`.
- Encoding `latin-1`, separador `;`.
- `ESCALA_MOEDA`: `MIL` e `UNIDADE`. `ORDEM_EXERC`: `ÚLTIMO` e `PENÚLTIMO` (com acento).
- ⚠️ `MOEDA`: só `REAL`, inclusive para a Vale. Ver [ADR 0002](decisoes/0002-moeda-da-vale.md).
- `CD_CVM` vem com zeros à esquerda (`009512`): tratar como texto ou normalizar.
- Os dicionários não listam os valores possíveis dos campos, só o tipo.

- Aspas aparecem literais dentro de `DS_CONTA` (ex.: `("VJORA")`), sem delimitar campos: ler com
  `QUOTE_NONE`. Contagem de linhas conferida com o pandas em DFP 2011, DFP 2025, ITR 2026 e FCA 2026.
- BPA/BPP não têm `DT_INI_EXERC` (saldo numa data). Só a DMPL tem `COLUNA_DF`.
- Os arquivos de dados só trazem a versão mais recente de cada documento; o índice
  (`dfp_cia_aberta_{ano}.csv`) lista todas as versões. O código mantém a maior `VERSAO` mesmo assim.

### ITR (2026, observado em 2026-10-30)

- DRE traz, por data, o acumulado no ano **e** o trimestre (`DT_INI_EXERC` distingue), para o
  exercício atual e o anterior (`PENÚLTIMO`). DFC só traz o acumulado. Confirma a seção 7.3 do guia.
- Não há ITR do 4º trimestre (vem na DFP). Em 2026-10-30 PETR4 e VALE3 tinham até 30/06, WEGE3 até 30/09.

### Composição do capital

- Existe na DFP a partir de 2020 (DFP 2010–2019 não trazem o arquivo) e em todos os ITR.
- ⚠️ **Sem coluna de escala.** A Vale informa em milhares em todas as datas (4.262.534 em 2026-03-31);
  a Petrobras informou em milhares só na DFP 2020 (13.044.497). Ver [ADR 0003](decisoes/0003-escala-das-acoes.md).
  Escala da Vale confirmada pela composição acionária publicada pela companhia (31/08/2026).
- Também em milhares em todas as datas (observado em 2026-10-30, ITR de 30/06/2026; `escala_acoes`
  1000 no cadastro manual): CBAV3 651.073, EMBJ3 740.465, RAPT3/4 349.725, TUPY3 132.450, KEPL3
  179.720, MYPK3 153.720, FRAS3 280.335. Em unidades: PRIO3, RECV3, BRAV3, CMIN3, POMO3/4, ROMI3,
  LEVE3. Sintoma do erro: market cap de poucos milhões de reais e P/VP perto de zero.
- ⚠️ **Significado de `QT_ACAO_TOTAL_CAP_INTEGR` varia por companhia.** Na Vale é o total **sem**
  tesouraria (4.255.763 mil = "Total (sem ações em tesouraria)" do RI; capital total 4.439.159.764).
  Na WEG é o capital total (4.197.317.998). Calcular "total − tesouraria" para todas subtrai a
  tesouraria duas vezes na Vale. Tratar na Fase 3 (market cap).

### Conciliação com documentos das companhias (2026-10-30)

Valores em `tests/golden/referencias.yaml`; documentos em `referencias/` (ver o índice lá). Resultado:

- Receita, lucro (controladora e total) e EBITDA (= EBIT + D&A) batem **exatamente** com a CVM para
  Petrobras (1S26, 2T26, 1S25) e Vale (1T25, 4T25, 1T26, 2T26; 4T25 = DFP − ITR 9M25).
- Vale 2025: receita, lucro atribuído, caixa e dívida bruta do Relatório da Administração batem.
- ⚠️ **Códigos de conta mudam entre períodos da mesma companhia.** D&A da Vale na DFC é
  `6.01.01.06` no 1T26 e `6.01.01.05` no 2T26. O mapeamento da Fase 2 precisa de regex em
  `DS_CONTA` (ou da DVA `7.04.01`, que é conta fixa).
- Petrobras: "disponibilidades ajustadas" (53.931) > caixa + aplicações CP da CVM (53.764). Diferença
  de títulos que a companhia soma ao caixa; candidata a `caixa_extra`.
- WEG (release 3T26): receita, lucro, IR, resultado financeiro e EBITDA (= EBIT + D&A) de 3T26, 2T26,
  3T25, 9M26 e 9M25 batem com a CVM (diferenças de R$ 1 mil são arredondamento do release).
  "Caixa líquido" da WEG = disponibilidades CP + aplicações LP + derivativos líquidos − financiamentos
  (dez/2025: 2.652.010 mil). Na DFP/ITR, D&A da WEG está na DFC (`6.01.01.02` em 2025), achada por regex.
- ⚠️ **Arrendamento fora de empréstimos.** Na WEG, arrendamentos ficam em "Outras obrigações"
  (`2.01.05.02.07` / `2.02.02.02.05`) e `2.01.04.03`/`2.02.01.03` existem com valor zero. Na Petrobras
  e na Vale ficam dentro de empréstimos (`2.01.04.03`/`2.02.01.03`). O mapeamento precisa somar os
  dois lugares sem contar duas vezes.

### Plano de contas padronizado (Fase 2, 2026-10-30)

`config/mapeamento_contas.yaml` conferido contra PETR4, VALE3 e WEGE3 (DFP 2016–2025, ITR
2025–2026): 100% de cobertura das 18 contas críticas nos 11 exercícios (2015 vem como
`PENÚLTIMO` da DFP 2016) e QA sem erros. Decisões em [ADR 0005](decisoes/0005-padronizacao-contabil.md).

| Código do guia (seção 7.2) | Status | Observado |
|---|---|---|
| DRE `3.01`, `3.05`, `3.06`, `3.08`, `3.11`, `3.11.01` | ✅ | Iguais nos três pilotos e em todos os anos |
| BPA `1.01.01`, `1.01.02`; BPP `2.03`, `2.03.09` | ✅ | Idem |
| BPP `2.01.04` / `2.02.01` (dívida) | ⚠️ | Incluem o arrendamento (`x.03`) em Petrobras e Vale; separado em `arrendamento_*_em_emprestimos` |
| Arrendamento por regex em `DS_CONTA` | ⚠️ | Precisa de duas contas padrão por prazo (dentro e fora de empréstimos) para não contar duas vezes |
| D&A: DVA `7.04.01` primeiro | ⚠️ | Invertido: DFC (`6.01.01.xx` por regex) primeiro. Petrobras 2019–2022: DVA > DFC (2022: 75.121 × 68.202 mi) |
| Capex por regex na DFC | ✅ | Restrito a `6.02` e sem linhas de venda/alienação. Vale 9M25: "Adições ao Imobilizado e investimentos". Petrobras 2019: bônus da Cessão Onerosa (`6.02.06`, 63 bi) fica fora |
| DFC `6.01` (caixa operacional) | ✅ | Só DFC indireta (`DFC_MI`) nos pilotos |

Outras observações:

- **Sinal invertido na fonte**: Vale DFP 2022 traz o custo (`3.02`) positivo; a DFP 2023 reapresenta
  2022 com sinal certo e vence pela regra do documento mais recente.
- **Dividendos pagos** (`6.03`): WEG escreve "Juros s/ Capital Próprio". O YTD da WEG nem sempre cresce
  ao longo do ano (1T25 −1.808,5 mi; 1S25 −1.806,6 mi; 1T26 −5 mi): é o que a companhia publicou.
- **Pagamento de arrendamento** (`6.03`): existe em Petrobras e Vale; a WEG não tem a linha.
- **Aplicações de longo prazo** (`1.02.01.01`–`.03`): mapeadas em `aplicacoes_financeiras_lp`, fora do caixa.
- Vale 2019: "Aplicações financeiras de curto prazo" dentro de `1.01.08` (outros ativos), fora do caixa
  padronizado.

### Cadastro (`cad_cia_aberta.csv`)

- Várias linhas por CNPJ: uma por mercado (`TP_MERC`) e registros cancelados com outro `CD_CVM`
  (Itaú: 1279 cancelado, 19348 ativo). O código fica com o registro `ATIVO` mais recente.
- `CD_CVM` sem zeros à esquerda (`9512`), diferente da DFP/ITR (`009512`).
- `SETOR_ATIV` tem variantes "Emp. Adm. Part. - <setor>", que incluem companhias operacionais
  (a WEG é "Emp. Adm. Part. - Máqs., Equip., Veíc. e Peças"). Holdings não são detectáveis pelo
  setor: ficam marcadas em `config/cadastro_manual.csv`.

### FCA `valor_mobiliario`

- `Valor_Mobiliario` usado: "Ações Ordinárias", "Ações Preferenciais", "Units"; `Mercado` = "Bolsa".
- Lixo conhecido: códigos "NÃO HÁ", "N/A" e numéricos (`713854`); o mesmo ticker como ON e PN
  (`CRTE3`); tickers encerrados com `Data_Fim_Negociacao` preenchida (`BRFS3`, 2025-09-22).
- Código CVM no lugar do ticker (FCA 2025 e 2026): CSN (`33.042.730/0001-04`, `4030`) e CSN
  Mineração (`08.902.291/0001-15`, `25585`). CSNA3 e CMIN3 entram pelo cadastro manual.
- A Embraer negocia como `EMBJ3` (não mais `EMBR3`).
- Nem toda companhia entrega o FCA do ano corrente: o código usa os FCA de `ano` e `ano - 1` e fica
  com o documento mais recente de cada CNPJ.

### Ibovespa (B3, 2026-10-30)

- Carteira teórica do dia: `GET https://sistemaswebb3-listados.b3.com.br/indexProxy/indexCall/GetPortfolioDay/<base64>`,
  com `<base64>` do JSON `{"language":"pt-br","pageNumber":1,"pageSize":120,"index":"IBOV","segment":"1"}`.
  ✅ Sem autenticação; devolve JSON (`header.date`, `results[].cod/asset/type/part/theoricalQty`).
  Em 30/10/26: 76 ativos, participações somando 100,000, sem duplicados. Há também
  `GetDownloadPortfolioDay/<base64>` (CSV em base64, latin-1), não usado.
- Dos 76 tickers, 73 casam com o cadastro. BPAC11 (unit, FCA com `000000`), CEAB3 (fim de
  negociação = início no FCA) e MBRF3 (Marfrig; FCA só com ADR) entram pelo cadastro manual.
- Composição por tipo: 65 não financeiras, 9 financeiras e 2 holdings (BRAP4 e ITSA4).

### Chaves entre arquivos

- `composicao_capital`: só `CNPJ_CIA` (sem `CD_CVM`). Colunas `QT_ACAO_{ORDIN,PREF,TOTAL}_CAP_INTEGR` e `QT_ACAO_{ORDIN,PREF,TOTAL}_TESOURO`.
- FCA `valor_mobiliario`: `CNPJ_Companhia`, `Codigo_Negociacao` (ticker), `Valor_Mobiliario`, `Mercado`, `Segmento`, `Composicao_BDR_Unit`, datas de início/fim de negociação. Sem `CD_CVM`.
- Ligação: ticker → (FCA) → CNPJ → (cadastro) → `CD_CVM` → DFP/ITR; CNPJ → composição do capital.

### Pilotos

| Ticker | CNPJ | CD_CVM | Moeda | Escala |
|---|---|---|---|---|
| PETR4 | 33.000.167/0001-01 | 009512 | REAL | MIL |
| VALE3 | 33.592.510/0001-54 | 004170 | REAL | MIL |
| WEGE3 | 84.429.695/0001-11 | 005410 | REAL | MIL |

## Preços

Cada preço é conferido em duas fontes (`yfinance` e `brapi`); ver ADR 0004. Validado em 2026-10-30.

| Item | Esperado | Status | Observado |
|---|---|---|---|
| yfinance ações | `PETR4.SA` | ✅ | `history(auto_adjust=False)` traz `Close`, `Adj Close`, `Volume`; índice com fuso `-03:00` (removido na leitura) |
| Ibovespa | `^BVSP` | ✅ | fechamento 169.186 em 2026-10-29 |
| Dólar | `BRL=X` | ✅ | 5,3872 em 2026-10-30; índice em UTC |
| brapi sem token | `/api/quote/PETR4` | ✅ | funciona só para PETR4, VALE3, MGLU3 e ITUB4 (campos `regularMarketPrice`, `regularMarketTime`, `marketCap`) |
| brapi WEGE3, `^BVSP` sem token | — | ⚠️ | HTTP 401 `MISSING_TOKEN`; defina `BRAPI_TOKEN` (cadastro gratuito) para validar os demais |
| brapi com `range=1y&interval=1d` | `historicalDataPrice` | ⏳ | sem token não foi possível testar; implementado conforme a documentação |
| Stooq | alternativa à brapi | ⚠️ | exige JavaScript (anti-bot); descartado |

O `marketCap` da brapi não bate com ações × preço da CVM (PETR4: 716,8 bi contra 672,8 bi pelo
preço do PN sobre todas as ações), então não é usado como checagem.

## Macro (BCB / Tesouro)

Validado em 2026-10-30. Todas as chamadas são GET sem chave.

| Série | Código SGS esperado | Status | Observado |
|---|---|---|---|
| Selic meta | 432 | ✅ | % a.a., 13,75; a série **traz datas futuras** (até 04/11 na consulta de 30/10): filtrar por `data <= data_base` |
| Selic diária | 11 | ✅ | % a.d. (0,050788); anualizada por `(1+d)^252-1` dá 13,65%, 0,10 p.p. abaixo da meta |
| CDI | 12 | ⏳ | não usado na Fase 3 |
| IPCA mensal | 433 | ✅ | % no mês, data = dia 1 do mês |
| IPCA 12 meses | 13522 | ✅ | novo na lista; bate com a composição dos 12 últimos valores do 433 |
| IGP-M | 189 | ⏳ | não usado na Fase 3 |
| Dólar | 1 | ✅ | PTAX venda; idêntico ao Olinda `CotacaoDolarDia` (5,3420 em 28/10) |
| Focus (Olinda `ExpectativasMercadoAnuais`) | — | ✅ | `$filter=Indicador eq 'IPCA' and Data le '…' and baseCalculo eq 0`; horizonte do ano corrente até +4 anos; `Mediana` em % |
| Tesouro Transparente (taxas) | — | ✅ | CKAN `taxas-dos-titulos-ofertados-pelo-tesouro-direto`; recurso `precotaxatesourodireto.csv` (14 MB, `;`, decimal `,`), **não ordenado por data**; colunas `Tipo Titulo`, `Data Vencimento`, `Data Base`, `Taxa Compra Manha` (% a.a.) |

Para o Rf usa-se a NTN-F (`Tesouro Prefixado com Juros Semestrais`) com vencimento mais próximo de
10 anos (aceita 7 a 13) na última `Data Base` ≤ `data_base`, taxa de compra da manhã.
Em 2026-10-28: NTN-F 01/2037 a 14,87%; NTN-B 05/2037 a 7,72% real.

Validação do Rf: NTN-B real composta com o IPCA do Focus no último ano divulgado (2030: 3,50%)
dá 11,49%, 3,4 p.p. abaixo da NTN-F. A diferença é a inflação implícita no mercado (~6,6%)
contra a expectativa do Focus (3,5%) mais prêmios; o aviso é esperado enquanto isso durar e
não indica erro de leitura.
