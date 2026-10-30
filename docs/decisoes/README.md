# Decisões de arquitetura (ADRs)

Um ADR registra uma decisão com consequências duradouras que **completa ou diverge** do
[`CLAUDE.md`](../../CLAUDE.md): um `[PREMISSA]` revisto, um `[VALIDAR]` que a fonte real
desmentiu, um detalhe que o guia não fixava e que muda números. Antes de seguir uma seção do
`CLAUDE.md`, confira na tabela abaixo se algum ADR a alterou: **o ADR aceito vence o texto do guia**.

Itens `[DECIDIDO]` não mudam por ADR sem o aval do usuário (regra 7 do `CLAUDE.md`).

## Índice

| ADR | Decisão | Seções do `CLAUDE.md` afetadas | Status |
|---|---|---|---|
| [0001](0001-estrutura-repositorio.md) | Raiz `Lastro/`, guia só em `CLAUDE.md` (sem `PROJETO.md`), Python 3.12 via `uv`, layout `src/`, mypy strict | 4, 5 | aceito |
| [0002](0002-moeda-da-vale.md) | Vale avaliada em BRL (`brl_direto`): na CVM ela reporta em `REAL`; `usd_crp` só com dados sintéticos | 2 (#21), 7.4, 10.2, 16 | aceito |
| [0003](0003-escala-das-acoes.md) | Escala da quantidade de ações: `escala_acoes` no cadastro manual + correção automática de datas em milhares | 6.1, 6.2 | aceito |
| [0004](0004-validacao-cruzada-de-apis.md) | Preço, Selic, IPCA, dólar e Rf vêm de uma fonte principal e são conferidos numa segunda | 6.2, 6.3 | aceito |
| [0005](0005-padronizacao-contabil.md) | Reapresentações por família e período, dívida × arrendamento separados, D&A pela DFC, métricas históricas, periodicidade `S` | 7.1, 7.3, 7.6 | aceito |
| [0006](0006-premissas-e-projecao.md) | `sugerido` permanece no YAML (valor em comentário), margem ajustada com reversão de metade, ΔNWC incremental, deltas de ±1 desvio-padrão, `arrendamento_sobre_receita`, anos-ponte e fração do ano | 9.1, 9.2, 9.3 | aceito |
| [0007](0007-custo-de-capital.md) | Kd histórico (despesas financeiras / dívida bruta média, 3 anos) limitado a Rf + faixa, benefício fiscal pela alíquota nominal, IPCA de longo prazo do Focus, precedência do beta do YAML, pesos com a dívida bruta do último balanço, comando `wacc` | 10.1, 10.2, 10.3, 14 | aceito |
| [0008](0008-dcf-ponte-e-cenarios.md) | Ke e WACC implícitos no preço, teto do g de 5%, prazos com meio período e VT no τ do último ano, RONIC, saldos e ações da ponte, cenário único, eixos da sensibilidade, `rodar` antecipado | 8.4, 11.1, 11.2, 12, 14, 19 (#3) | aceito |
| [0009](0009-multiplos-e-comparaveis.md) | Pares por setor (petróleo E&P, mineração × siderurgia, máquinas), EV inverso da ponte e EBITDA ajustado, winsorização 10/90 com mediana e P25–P75, exclusão por P/VP implausível, beta e estrutura dos pares, minoritários pelo P/VP, g implícito no múltiplo de saída, `comparar` e `atualizar --com-pares` | 10.1, 10.3, 11.1, 11.2, 11.4, 14, 19 (#4) | aceito |
| [0010](0010-universo-ibovespa-e-pares-da-mineracao.md) | Universo = carteira teórica da B3 (JSON `GetPortfolioDay`), CSNA3 como terceiro par da mineração, cadastro manual de BPAC11, CEAB3 e MBRF3 | 11.4, 19 (#4) | aceito |
| [0011](0011-plano-de-contas-das-financeiras.md) | Plano `financeira` por regex de descrição (bancos, seguradoras, comercial), individual quando não há consolidado, documento só com zeros ignorado, ROE sobre o PL inicial, dividendos ausentes vazios, QA próprio, corretoras (WIZC3, QUAL3) como não financeiras | 6.4, 7.2, 7.5 | aceito |
| [0012](0012-premissas-e-projecao-das-financeiras.md) | ROE de longo prazo pela mediana de 10 anos, payout da mediana de 5 anos até 1 − g/ROE_LP, YAML `projecao`/`cenarios` conforme o tipo, cenários por ROE (inclusive o de longo prazo), projeção a partir do PL do último balanço | 9.1, 9.2, 11.3 | aceito |
| [0013](0013-ddm-ke-e-cenarios-das-financeiras.md) | DDM descontado no fim do ano, lucro residual com o custo de cada trecho (igual ao DDM), valor da controladora sem ponte, Ke sem WACC (comparáveis sem Hamada), Ke implícito como retorno esperado, matrizes Ke × g e ROE_LP × Ke | 10.4, 11.3, 12 | aceito |
| [0014](0014-multiplos-e-pares-das-financeiras.md) | Múltiplos das financeiras (P/L, P/VP, DY, sem EV), regressão P/VP × ROE, setores `bancos` (18) e `seguradoras` (4), escala de ações de 5 bancos | 11.4 | aceito |
| [0015](0015-units-no-market-cap.md) | `acoes_por_unit` no cadastro manual; com unit cotada, ON e PN valem preço da unit / ações por unit (BPAC11, BRBI11, SANB11) | 6.2, 6.4 | aceito |
| [0016](0016-saidas-da-fase-9.md) | Saídas da Fase 9: IPCA do Focus para deflacionar (último Focus além do horizonte), `valores_reais.csv` longo, `meta.json` com commit e hashes, `premissas_usadas.yaml`, gráficos sem `pyplot`, cascata só no DCF, DDM anualizado no gráfico, `--sem-graficos` | 11.5, 12, 13, 14 | aceito |
| [0017](0017-kd-manual-da-petr4.md) | Kd da PETR4 manual: Rf (NTN-F) + spread de crédito de 0,60% do guia do usuário = 15,60%; número fixo; efeito de −1,3% no valor | 10.3 | aceito |
| [0019](0019-rodar-por-setor.md) | Setores como enum (`SetorCVM`, do `setor_cvm` do universo) e `valuation setores` / `rodar-setor`: roda o `rodar` em cada empresa do setor, uma após a outra; holdings puladas, falha isolada por empresa | 11 (lote), 14 | aceito |
| [0018](0018-erp-implicito-do-ibovespa.md) | ERP implícito do Ibovespa: dividendos agregados, Focus (PIB + IPCA) em 5 anos e g perpétuo pelo CAGR histórico (teto 5%), sem convergência, faixa ±1 p.p., erro fora de [0%, 15%], `valuation erp` grava o JSON lido pelo Ke; em 30/10/2026 o ERP deu −4,2% (padrão segue manual) | 10.2 | aceito |

## Quando escrever um ADR

- Um `[PREMISSA]` do `CLAUDE.md` foi trocado (regra de "Como usar este documento").
- A inspeção de uma fonte mostrou que o guia está errado, e isso muda o desenho (o simples
  registro do que foi observado vai em [`docs/fontes.md`](../fontes.md)).
- Uma escolha técnica afeta várias camadas ou os dados já gravados: formato de parquet,
  dependência nova fora da seção 4 do `CLAUDE.md`, contrato entre camadas.

Não precisa de ADR: detalhe de implementação que só um módulo vê (vai no `guia.md`) e correção de
bug que deixa o código de acordo com o guia.

## Como escrever

1. Crie `NNNN-titulo-curto.md` com o próximo número livre.
2. Use o modelo abaixo; seja curto e cite os números ou arquivos observados que motivaram a decisão.
3. Acrescente a linha na tabela do índice, com as seções do `CLAUDE.md` afetadas.
4. Se a decisão muda o que o `CLAUDE.md` afirma num ponto que engana quem o lê (como a moeda da
   Vale), deixe uma nota curta naquela seção apontando para o ADR.

Um ADR aceito **não é reescrito**. Se a decisão mudar, o novo ADR diz qual substitui, e o antigo
passa a `substituído por NNNN` (no cabeçalho e no índice).

```markdown
# ADR NNNN — Título da decisão

- **Data:** AAAA-MM-DD
- **Status:** aceito | substituído por NNNN

## Contexto

O que o guia previa, o que foi observado (dados, arquivos, números) e as alternativas consideradas.

## Decisão

O que passa a valer, em itens objetivos.

## Consequências

O que muda nos dados, nos testes e nas fases seguintes; limitações que ficam.
```
