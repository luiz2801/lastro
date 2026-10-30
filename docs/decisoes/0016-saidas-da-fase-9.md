# ADR 0016 — Saídas da Fase 9: reprodutibilidade, valores reais e gráficos

- **Data:** 2026-10-30
- **Status:** aceito

## Contexto

A seção 13 do `CLAUDE.md` lista os arquivos e gráficos da saída, mas deixa em aberto como
deflacionar (seção 11.5: "Focus no curto prazo, meta/parâmetro no longo"), que dados entram no
`meta.json` e o que cada gráfico mostra quando o modelo é o DDM (sem ponte EV → equity).

## Decisão

1. **Um bloco comum a DCF e DDM** (`cli._gravar_complementos`) grava `historico.csv`, `qa.json`,
   `valores_reais.csv`, `premissas_usadas.yaml`, os PNG e, por último, o `meta.json`. Os módulos
   ficam em `saida/` (`arquivos`, `real`, `graficos`); os gráficos usam `matplotlib.figure.Figure`
   sem `pyplot` e a paleta categórica de ordem fixa (azul, laranja, verde-água).
2. **IPCA para deflacionar**: o do Focus de cada ano; entre anos do Focus e além do último vale o
   último Focus anterior (a mesma convenção do IPCA de longo prazo do `usd_crp`, ADR 0007); antes
   do primeiro, o IPCA de 12 meses. Sem Focus, o IPCA de 12 meses vale em todos os anos, com
   aviso. Nenhum parâmetro novo no `settings.yaml`.
3. **`valores_reais.csv`** (formato longo): fluxos (FCFF ou dividendos) e valor terminal
   deflacionados pelo fator acumulado até o τ de cada fluxo; o valor por ação, que já está em reais
   da data-base, entra com deflator 1; a taxa de desconto e o g entram nominais e reais (Fisher
   com o IPCA do último ano projetado). Não substitui o resultado nominal.
4. **`meta.json`**: versão, commit do código (`+sujo` com alterações), comando equivalente, perfil
   e origem, moeda e câmbio, fontes (preços, Ibovespa, macro, market cap e URL/data/sha256 dos
   arquivos da CVM em cache), hash de `contas_padronizadas.parquet` e os arquivos presentes na
   pasta (inclusive de execuções anteriores com outras opções).
5. **`premissas_usadas.yaml`**: premissas da empresa, premissas resolvidas de cada cenário, perfil
   efetivo e `settings` inteiro. É cópia para reprodutibilidade, não a fonte editável.
6. **Gráficos**:
   - football field: modelo (pessimista a otimista, ponto no base), faixa da sensibilidade
     principal, múltiplos de P25 a P75 (ponto na mediana; esmaecido com baixa confiança) e faixa
     de 52 semanas do fechamento não ajustado; linhas do preço atual e do preço máximo;
   - cascata EV → equity só no DCF (o DDM avalia o patrimônio direto, sem ponte);
   - dois heatmaps por execução (`sensibilidade_heatmap.png` com WACC × g ou Ke × g, e o da
     segunda matriz); célula central contornada;
   - histórico × projeção: no DDM, lucro e dividendos do ano corrente são anualizados (divididos
     pela fração do ano) só no gráfico, para não parecer uma queda; os CSVs mantêm o trecho;
   - composição do valor: VP dos fluxos e VP do terminal por cenário.
7. `--sem-graficos` suprime os PNG; os demais arquivos são sempre gravados.

## Consequências

- `resumo.csv` não ganha os avisos novos (QA, 52 semanas, Focus ausente), que vão ao terminal e
  ao `meta.json`.
- O QA roda de novo dentro do `rodar` (custo pequeno) e `qa.json` fica junto da saída, além de
  `data/processed/qa/`.
- Sem gráfico para o ano corrente parcial do DDM além da anualização; sem tabela de dados
  alternativa dos PNG (os CSVs são a tabela).
