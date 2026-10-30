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
- ⚠️ **Significado de `QT_ACAO_TOTAL_CAP_INTEGR` varia por companhia.** Na Vale é o total **sem**
  tesouraria (4.255.763 mil = "Total (sem ações em tesouraria)" do RI; capital total 4.439.159.764).
  Na WEG é o capital total (4.197.317.998). Calcular "total − tesouraria" para todas subtrai a
  tesouraria duas vezes na Vale. Tratar na Fase 3 (market cap).

### Conciliação com documentos das companhias (2026-10-30)

Valores em `tests/golden/referencias.yaml`. Resultado:

- Receita, lucro (controladora e total) e EBITDA (= EBIT + D&A) batem **exatamente** com a CVM para
  Petrobras (1S26, 2T26, 1S25) e Vale (1T25, 4T25, 1T26, 2T26; 4T25 = DFP − ITR 9M25).
- Vale 2025: receita, lucro atribuído, caixa e dívida bruta do Relatório da Administração batem.
- ⚠️ **Códigos de conta mudam entre períodos da mesma companhia.** D&A da Vale na DFC é
  `6.01.01.06` no 1T26 e `6.01.01.05` no 2T26. O mapeamento da Fase 2 precisa de regex em
  `DS_CONTA` (ou da DVA `7.04.01`, que é conta fixa).
- Petrobras: "disponibilidades ajustadas" (53.931) > caixa + aplicações CP da CVM (53.764). Diferença
  de títulos que a companhia soma ao caixa; candidata a `caixa_extra`.

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
- Nem toda companhia entrega o FCA do ano corrente: o código usa os FCA de `ano` e `ano - 1` e fica
  com o documento mais recente de cada CNPJ.

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

| Item | Esperado | Status | Observado |
|---|---|---|---|
| yfinance ações | `PETR4.SA` | ⏳ | |
| Ibovespa | `^BVSP` | ⏳ | |
| Dólar | `BRL=X` | ⏳ | |

## Macro (BCB / Tesouro)

| Série | Código SGS esperado | Status | Observado |
|---|---|---|---|
| Selic meta | 432 | ⏳ | |
| Selic diária | 11 | ⏳ | |
| CDI | 12 | ⏳ | |
| IPCA mensal | 433 | ⏳ | |
| IGP-M | 189 | ⏳ | |
| Dólar | 1 | ⏳ | |
| Focus (Olinda `ExpectativasMercadoAnuais`) | — | ⏳ | |
| Tesouro Transparente (taxas do prefixado) | — | ⏳ | |
