# Fontes de dados — registro de validação

Cada URL, nome de arquivo, código de conta ou série marcado `[VALIDAR]` no guia é registrado aqui
depois de inspecionado na fonte real.

Legenda: ✅ confirmado · ⚠️ diferente do guia · ⏳ pendente

## CVM (dados.cvm.gov.br)

| Item | Esperado no guia | Status | Observado / data |
|---|---|---|---|
| Cadastro | `CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv` | ⏳ | |
| DFP | `CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_{ano}.zip` | ⏳ | |
| ITR | `CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_{ano}.zip` | ⏳ | |
| FCA | `CIA_ABERTA/DOC/FCA/DADOS/fca_cia_aberta_{ano}.zip` | ⏳ | |
| Arquivos internos (BPA, BPP, DRE, DFC_MD/MI, DVA, DMPL, composição do capital) | ver seção 6.1 | ⏳ | |

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
