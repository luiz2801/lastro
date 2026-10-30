# Fontes de dados — registro de validação

Cada URL, nome de arquivo, código de conta ou série marcado `[VALIDAR]` no guia é registrado aqui
depois de inspecionado na fonte real.

Legenda: ✅ confirmado · ⚠️ diferente do guia · ⏳ pendente

## CVM (dados.cvm.gov.br)

| Item | Esperado no guia | Status | Observado / data |
|---|---|---|---|
| Cadastro | `CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv` | ✅ | Existe na listagem (2026-10-30); conteúdo ainda não inspecionado |
| DFP | `CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_{ano}.zip` | ✅ | Anos 2010–2026 (2026-10-30); 2025 tem 13 MB |
| ITR | `CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_{ano}.zip` | ✅ | Existe até 2026 na listagem; conteúdo ainda não inspecionado |
| FCA | `CIA_ABERTA/DOC/FCA/DADOS/fca_cia_aberta_{ano}.zip` | ✅ | Existe até 2026 na listagem |
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
