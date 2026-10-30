# Contexto rápido

Cheatsheet para começar uma tarefa sem carregar o `CLAUDE.md` (cerca de 850 linhas) nem o
`guia.md` inteiro. **Não substitui nenhum dos dois**: serve para decidir o que ler. Em caso de
divergência, valem o código, o `guia.md` e os ADRs, nessa ordem.

## O que é

Valuation de ações da B3 em Python, uso pessoal e local, sem recomendação de investimento. Uma
empresa por execução (`valuation rodar TICKER`). Não financeiras: DCF (FCFF) + múltiplos.
Financeiras: DDM / lucro residual + P/VP justificado + múltiplos.

## Camadas (de baixo para cima; a de cima nunca é importada pela de baixo)

`data` → `contabil` → `projecao` → `custo_capital` → `modelos` → `analise` → `saida`
(`perfil/` e `cli.py` ficam ao lado). Código em `src/valuation/`, configuração em `config/`,
dados em `data/` (fora do git), saída em `saida/{TICKER}/{AAAA-MM-DD}/` (fora do git).

## Onde ler antes de mexer

| Vou mexer em… | Leia (só isto) |
|---|---|
| Download, cache, tickers, escala, preços, macro | `docs/regras/REGRAS_DADOS.md` + `guia.md` seções 5 a 10 |
| Padronização, mapeamento de contas, QA, LTM | `docs/regras/REGRAS_CONTABIL.md` + `guia.md` seção 11 |
| Projeção, WACC/Ke, DCF, DDM, múltiplos, cenários | `docs/regras/REGRAS_MODELOS.md` + `guia.md` seções 18 a 20 |
| Perfil do investidor | `guia.md` seção 17 |
| Testes, fixtures, golden | `docs/regras/REGRAS_TESTES.md` + `tests/README.md` |
| Comandos da CLI | `guia.md` seção 3 (o `cli.py` tem mais de 2 mil linhas: não leia inteiro) |
| Tarefa recorrente (empresa, métrica, parâmetro, múltiplo) | o playbook certo em `docs/recipes_agentes.md` |
| Por que algo é assim | o ADR citado, via `docs/decisoes/README.md` |
| Fluxo geral do pipeline | `docs/diagrama_atividades.md` |
| Que documento atualizar | tabela em `CONTRIBUTING.md` |

## Convenções (as que mais pesam)

1. Motor de cálculo = **funções puras**: sem I/O e sem `date.today()`; `data_base` é parâmetro.
2. Dinheiro em **unidades da moeda** (a escala é aplicada na ingestão); taxas em decimal (0,1375).
3. I/O por injeção (sessão HTTP, diretórios) em parâmetros keyword-only: testes rodam offline.
4. Identificadores de domínio e mensagens ao usuário em português; exceções `ErroX`.
5. Docstrings e strings em ASCII para símbolos (`x`, `-`): o ruff recusa `×`, `−`, `–`, `σ`.
6. Nunca invente dado financeiro: falte o dado, falhe com mensagem clara ou use o `settings.yaml`.
7. Dataclasses `frozen=True` entre camadas; pydantic só para configuração.

## Armadilhas mais repetidas (lista completa: `guia.md` seção 16)

- `CD_CVM` com zero à esquerda na DFP/ITR e sem no cadastro: use `normalizar_cd_cvm`.
- Market cap de poucos milhões e P/VP perto de zero: ações da CVM em milhares, falta
  `escala_acoes: 1000` no `config/cadastro_manual.csv`.
- Regex do mapeamento roda sobre `DS_CONTA` sem acento e minúscula: regex com acento nunca casa.
- `golden/referencias.yaml` está em R$ milhões; os parquets estão em unidades.
- `premissas sugerir --escrever` regenera o YAML da empresa inteiro (comentários próprios se
  perdem; o anterior fica em `.yaml.bak`).
- Com `ronic: wacc` o g quase não muda o valor: é teoria, não bug.

## Antes de commitar

`make lint tipos testes` passa (sem rede). Commit atômico, mensagem `area: o quê` em português.
Documentação da mudança (`guia.md` com a versão, `CHANGELOG.md`, ADR se divergir do `CLAUDE.md`)
vai no mesmo commit. Push só quando o usuário pedir.

## Como pedir a um agente, gastando menos contexto

- Aponte o arquivo: "em `src/valuation/projecao/premissas.py`, ajuste X", não "olhe o `cli.py`".
- Aponte o playbook: "execute o Playbook 1 de `docs/recipes_agentes.md` para RAIL3".
- Cite ADR por número: "siga o ADR 0006".
- Aponte a regra modular: "consulte apenas `REGRAS_DADOS.md`".
- Separe entender de implementar, e use `/compact` em conversas longas.
- Não corte: ADRs, docstrings, validações do `qa.py` e testes sintéticos.
