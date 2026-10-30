# ADR 0004 — Dados de mercado por API com validação cruzada

- **Data:** 2026-10-30
- **Status:** aceito

## Contexto

Preços, câmbio, Selic, IPCA e taxa livre de risco eram parâmetros manuais. Fontes gratuitas
erram e saem do ar (yfinance é não oficial), e um número errado de Rf ou preço contamina o
valuation inteiro sem avisar.

## Decisão

Cada dado vem de uma fonte principal e é conferido em uma segunda, independente quando possível
(`data/validacao.py`):

| Dado | Principal | Segunda fonte |
|---|---|---|
| Preço da ação | yfinance | brapi |
| Selic | SGS 432 | SGS 11 anualizada |
| IPCA 12m | SGS 13522 | SGS 433 composto |
| Dólar | SGS 1 | yfinance `BRL=X` |
| Rf BRL | NTN-F ~10a | NTN-B ~10a + Focus (Fisher) |

- A principal sempre vence; divergência acima da tolerância gera aviso e fica na saída.
- Só uma fonte respondendo: usa e marca `sem_validacao`. Nenhuma: erro.
- Rf manual (`rf_brl.fonte: manual`) dispensa o Tesouro e aparece como `manual`.
- A brapi só informa a cotação atual; entra na comparação só se a data estiver a até 4 dias do
  fechamento principal.

## Consequências

- Sem `BRAPI_TOKEN`, só PETR4, VALE3, MGLU3 e ITUB4 têm segunda fonte de preço; ^BVSP e demais
  aparecem como `sem_validacao`.
- O par do Rf é fraco por natureza (prêmio de inflação): a tolerância é de 2,5 p.p. e hoje o
  aviso dispara. É informação, não erro de leitura (ver `docs/fontes.md`).
- Selic meta e diária diferem ~0,10 p.p. por construção (taxa efetiva abaixo da meta).
- O SGS 1 e o Olinda PTAX são a mesma fonte; por isso o par do dólar usa o yfinance.
