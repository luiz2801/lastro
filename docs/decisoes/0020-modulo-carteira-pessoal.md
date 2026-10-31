# ADR 0020 — Módulo de carteira pessoal (RF-004, 007, 008, 009, 010, 011, 012)

- **Data:** 2026-10-31
- **Status:** aceito (planejamento; implementação por etapas, ver backlog "Carteira pessoal")

## Contexto

O projeto foi especificado como motor de valuation de ações da B3 (seções 1 e 17 do `CLAUDE.md`).
O plano de requisitos do usuário (RF-001 a RF-013) descreve, além disso, um gestor de carteira
pessoal. Na análise de 2026-10-31, os RF-004, 007, 008, 009, 010, 011 e 012 ficaram "parcial" ou
"pode ser". O usuário decidiu implementá-los de forma plena.

O `CLAUDE.md` não lista carteira pessoal entre as exclusões da v1 (ele exclui holdings, FIIs,
REITs, RJ, SOTP, Monte Carlo, lote e interface web). Mesmo assim é mudança de escopo, então registro
aqui. O que **não** muda: as seções 1 a 16 de valuation, os dados e os modelos.

Estado de partida (verificado no código em 2026-10-31):

- Indicadores existentes (`contabil/nao_financeiras.py`, `cli.py` `historico`): P/L, P/VP, DY,
  EV/EBITDA, EV/EBIT, ROIC, dívida líquida, margem EBITDA, ROE só nas financeiras
  (`contabil/financeiras.py`). Faltam margem líquida, dívida líquida/EBITDA e ROE das não
  financeiras.
- Proventos: só agregados (`dividendos_pagos`, `payout`, DFC 6.03). Não há calendário por evento.
- Carteira, transações e alocação: não existem.
- Setor: `setor_cvm` está no cadastro (`universo.py`, enum `SetorCVM`).
- Interface: só CLI e PNG estáticos. A GUI está no backlog (Etapa 9), fora da v1.

## Decisão

1. **Nova camada `carteira/`** no topo da cadeia (acima de `saida`): lê transações e alvos, consulta
   cotações (`data/precos.py`) e o cadastro, e não é importada por nenhuma camada inferior. As
   funções de cálculo são puras (`data_base` como parâmetro), como no restante do motor.
2. **Indicadores por ativo (RF-004)** ficam em `analise/indicadores.py`, funções puras sobre o
   histórico padronizado. Acrescentam margem líquida, dívida líquida/EBITDA e ROE das não
   financeiras. O cálculo não muda os valores já existentes de DCF, DDM e múltiplos.
3. **Transações em arquivo local, sem banco.** `carteira/transacoes.csv` (fora do git, `;` e
   decimal `,`, como manda a decisão 20 da seção 2 do `CLAUDE.md`). Colunas fixas: `data`, `ticker`,
   `tipo` (`compra`, `venda`, `provento`, `agrupamento`, `desdobramento`, `bonificacao`),
   `quantidade`, `preco`, `valor`, `taxas`, `observacao`. A validação recusa linha com tipo
   desconhecido, quantidade ou preço negativo, e venda acima da posição. Histórico imutável: correção
   é linha nova ou edição explícita.
4. **Importação CSV e XLSX (RF-007).** XLSX exige a dependência `openpyxl`. **Esta é a dependência
   nova autorizada por este ADR**; o `pyproject.toml` e a lista da seção 4 do `CLAUDE.md` são
   atualizados na etapa de implementação. A importação converte para o schema acima e rejeita o
   arquivo inteiro se qualquer linha falhar (falhe alto), com o número da linha no erro.
5. **Posição e preço médio (RF-008).** Preço médio recalculado a cada compra (média ponderada pelo
   custo, taxas incluídas); venda reduz a quantidade sem alterar o preço médio; agrupamento e
   desdobramento ajustam quantidade e preço médio pelo fator; bonificação entra a custo zero.
   Patrimônio = Σ quantidade × cotação; lucro/prejuízo nominal e percentual = patrimônio + vendas
   + proventos recebidos − custo. Cotação de fechamento na data-base (mesma regra do `mercado`).
6. **Proventos (RF-010 e RF-011).** Recebidos vêm das linhas `provento`. Provisionados vêm de um
   calendário de eventos anunciados (data "com", data de pagamento, valor por ação), e a fonte **ainda
   não foi escolhida nem validada**. Pela regra 2 do `CLAUDE.md`, nenhum dado de proventos é
   inventado: a etapa começa por inspecionar a fonte real e registrar o resultado em
   `docs/fontes.md`. Candidatos a checar: yfinance (`dividends`, sem data de pagamento) e o
   cadastro de eventos da CVM. Sem fonte confiável, RF-010 e RF-011 viram aviso e o histórico de
   recebidos segue funcionando.
7. **Alocação (RF-009).** Classes de ativo: `acao` (ON, PN, unit, ETF não entram). Por setor usa
   `setor_cvm`. Fundos e renda fixa ficam de fora deste ADR. Saída em CSV e PNG (rosca), como o
   resto das saídas.
8. **Alocação-alvo e aportes (RF-012).** Alvos por classe e por ativo em `carteira/alvos.yaml`
   (validados com pydantic; a soma tem de dar 100%). O cálculo de aporte (RF-013, fora do escopo
   destes sete RFs) fica para depois, mas o modelo de alvo já a comporta.
9. **Tela (RF-008 e RF-009 em forma de dashboard).** Com a CLI, a entrega é `valuation carteira
   posicao|alocacao|proventos|indicadores`. A tela visual (dashboard, RF-005 e a "página por
   ativo") depende de escolha de tecnologia, que o ADR não decide: fica na pergunta 2 do backlog.

## Consequências

- Nova dependência: `openpyxl` (XLSX). Nenhuma outra. Chaves de API seguem não necessárias.
- Nova pasta `carteira/` (git-ignored, junto de `perfil/`) e nova camada `src/valuation/carteira/`.
  O `guia.md` ganha a seção do módulo e o `docs/diagrama_atividades.md` o fluxo de importação e
  posição.
- Testes com transações sintéticas (`tests/sintetico.py`), sem rede; preço médio e lucro com valores
  calculados à mão. Fontes de proventos só entram após validação em `docs/fontes.md`.
- Valuation (DCF, DDM, múltiplos) não muda. O `CLAUDE.md` ganha uma nota na seção 1 apontando este
  ADR; o corpo da especificação não é reescrito.
- Limitações: sem IR, sem custos de corretagem além do campo `taxas`, sem cotação intradiária (a
  posição usa fechamento diário, como o resto do motor), e preço médio não ajusta impostos.
- Não substitui o plano de dados: a validação de fontes segue o `docs/regras/REGRAS_DADOS.md`.
