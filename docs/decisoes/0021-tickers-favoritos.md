# ADR 0021 — Tickers favoritos e cache de resultados (`valuation favoritos`)

- **Data:** 2026-11-02
- **Status:** aceito

## Contexto

Etapa 8 do `docs/backlog.md`: agilizar a revisão rotineira de algumas empresas sem refazer o
`rodar` nem usar a rede. O backlog deixava em aberto o formato da lista (YAML próprio ou seção do
`settings.yaml`) e o cache dos resultados calculados.

## Decisão

1. **Lista em `config/favoritos.yaml`**, arquivo próprio (`favoritos: [PETR4, ...]`), não o
   `settings.yaml`: é preferência pessoal e muda com frequência, enquanto o `settings.yaml` é
   parâmetro de modelo. Chave desconhecida é erro; tickers saem em maiúsculas e sem repetição;
   arquivo ausente equivale a lista vazia. Caminho em `config.CAMINHO_FAVORITOS`.
2. **O cache de resultados é o `resumo.csv` já existente** da pasta de data mais recente em
   `saida/{TICKER}/`. Nenhum `resumo.json` ou parquet novo é gravado: o snapshot não duplica
   dado nem precisa de invalidação própria. A consulta lê só arquivos locais (sem rede).
3. **Comandos** (`saida/favoritos.py` + `cli.py`):
   - `valuation favoritos`: tabela com data-base, idade em dias, perfil, preço, valor ponderado,
     preço máximo de compra, upside e nº de avisos do último resultado; "sem rodada" se não houver.
   - `favoritos adicionar T...` (só tickers de `config/universo_ibovespa.csv`) e `remover T...`.
   - `favoritos atualizar [--max-idade-dias N] [--forcar] [--sem-graficos]`: roda `rodar` (padrões:
     todos os cenários, perfil gravado) só nos favoritos cujo resultado tem mais de N dias
     (padrão 1; `0` roda todos). Perfil inválido sai com 1 antes do laço; falha de uma empresa não
     interrompe as demais, e a execução sai com 1 se houver falha (mesmo critério do `rodar-setor`).
4. **Idade** é `hoje − data_base` do resumo gravado; é um aviso de defasagem, não um TTL de cache.

## Consequências

- O valor exibido é o da última rodada, com o preço daquele dia: a coluna "Idade" é o aviso para
  não o tomar como cotação atual.
- `resumo.csv` em formato `br` ou `intl` é lido (tenta o do `settings.csv`, depois o internacional).
- A aba de favoritos da GUI (Etapa 9) reaproveita `saida/favoritos.py`.
