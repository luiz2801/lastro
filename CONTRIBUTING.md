# Guia de contribuição

Como mudar este repositório: ambiente, política de commits, quais documentos atualizar, quando
escrever um ADR, testes e convenções de código. As regras valem para pessoas e para agentes de IA;
as do agente estão na seção 0 do [`CLAUDE.md`](CLAUDE.md), e este guia as reúne num lugar só.

Antes de mexer em código, leia a seção do módulo no [`guia.md`](guia.md) (e as seções 13 e 16,
convenções e armadilhas), consulte o [`docs/diagrama_atividades.md`](docs/diagrama_atividades.md) e
as regras modulares da camada correspondente em [`docs/regras/`](docs/regras/README.md) ([`REGRAS_DADOS.md`](docs/regras/REGRAS_DADOS.md),
[`REGRAS_CONTABIL.md`](docs/regras/REGRAS_CONTABIL.md), [`REGRAS_MODELOS.md`](docs/regras/REGRAS_MODELOS.md) e
[`REGRAS_TESTES.md`](docs/regras/REGRAS_TESTES.md)). Eles **não se substituem, se complementam**: o diagrama
orienta a visão dinâmica do fluxo e decisões de processo, o guia mapeia a estrutura, contratos e
parâmetros do código, e as regras modulares orientam os limites e convenções específicas da camada.
Antes de seguir uma seção do `CLAUDE.md`, confira no [índice de ADRs](docs/decisoes/README.md) se alguma
decisão a alterou.

## Ambiente

- Linux, [`uv`](https://docs.astral.sh/uv/) e Python 3.12 (fixado em `.python-version`; o `uv`
  baixa). `requires-python` aceita 3.11 a 3.13 (ADR 0001).
- `make setup` cria a `.venv` e instala tudo, inclusive as ferramentas de desenvolvimento.
- Nenhuma chave é necessária. `BRAPI_TOKEN` (opcional, gratuito em brapi.dev) habilita a segunda
  fonte de preço para tickers além de PETR4, VALE3, MGLU3 e ITUB4.
- `data/`, `saida/`, `perfil/perfil_investidor.json` e o conteúdo de `referencias/` ficam fora do
  git. `make atualizar` recria `data/` a partir da CVM.

## Fluxo de trabalho

Projeto pessoal, com remoto em `origin` (GitHub) e sem CI: a verificação é local. Os commits vão
na `main`, e o push só é feito quando o usuário pede.

Trabalhe por fase (seção 17 do `CLAUDE.md`). Não avance de fase com testes falhando; ao fechar uma,
atualize o `CHANGELOG.md`, rode `make lint tipos testes` e resuma ao usuário o que ficou pronto, o
que foi decidido e o que depende dele.

## Política de commits

**Antes de todo commit, `make lint tipos testes` passa.** Não faça commit com lint, mypy ou testes
falhando, nem sem tê-los rodado. Se não for possível rodar, não faça o commit: avise e peça ao
usuário que rode ou autorize explicitamente.

**Commit ao concluir uma aplicação 100% integrada.** Quando uma mudança está inteira (código,
CLI quando couber, testes, documentação e ADR), `make lint tipos testes` passa e não sobra parte
pendente, o commit é feito logo, sem esperar pedido do usuário. Isso vale só para a mudança
completa: não commite trabalho parcial, WIP nem etapa que depende de decisão ainda aberta (dúvida
da seção 19 do `CLAUDE.md`). O push continua só quando o usuário pede.

Um commit é **atômico**: uma única mudança lógica, completa e que funciona sozinha.

- **Um propósito por commit**: um módulo novo, uma correção, uma refatoração ou uma mudança de
  documentação, não várias. Um adaptador novo e o comando da CLI que o usa podem ser dois commits.
- **Sem commits "catch-all"**: commit que toca muitos arquivos sem motivo claro provavelmente
  deveria ser vários.
- **Cada commit passa nos testes**: a história da `main` é sempre funcional.

A mensagem diz **o quê** mudou (e por quê, se não for óbvio), em português, começando pela área
em minúsculas: a camada (`data`, `contabil`, `projecao`, `custo_capital`, `modelos`, `analise`,
`saida`, `perfil`), `cli`, `config`, `docs` ou `fix`.

| Bom | Ruim |
|---|---|
| `data: download com cache, retry e metadados (http.py)` | `atualiza código` |
| `contabil: padronização, períodos/LTM, QA e métricas (Fase 2)` | `fix e refatoração e docs` |
| `fix: ancora data/ do .gitignore na raiz` | `WIP` |
| `docs: registra fontes CVM validadas e ADR da moeda da Vale` | |

A documentação da própria mudança (`guia.md`, `CHANGELOG.md`, `docs/fontes.md`, ADR) vai **no
mesmo commit** do código: a regra 10 do `CLAUDE.md` exige o `guia.md` na mesma entrega.

## Documentação

Toda mudança de lógica, contrato, parâmetro, arquivo ou comando atualiza a documentação afetada
**na mesma entrega**, antes de a tarefa ser dada por concluída. Não exigem atualização: refatoração
sem mudança de comportamento, typo e mudança só em testes (salvo a tabela de testes do `guia.md`,
se um arquivo de teste surgir ou sumir).

| O que mudou | Documento |
|---|---|
| Módulo, função, contrato, fórmula, parâmetro lido, comando da CLI, armadilha | [`guia.md`](guia.md) (versão no topo, conforme a regra de manutenção dele) |
| Fluxo do pipeline, etapas, bifurcações, modelos ou saídas | [`docs/diagrama_atividades.md`](docs/diagrama_atividades.md) (complementa o `guia.md` com o fluxo dinâmico; atualizar com a evolução do fluxo) |
| Procedimento operacional frequente (nova empresa, métrica, parâmetro, etc.) | [`docs/recipes_agentes.md`](docs/recipes_agentes.md) |
| Princípios inegociáveis ou armadilhas de uma camada técnica | [`docs/regras/`](docs/regras/README.md) ([`REGRAS_*.md`](docs/regras/README.md)) |
| Entrega concluída (o quê, por fase) | [`CHANGELOG.md`](CHANGELOG.md), seção `[Não lançado]` |
| Decisão que completa ou diverge do `CLAUDE.md` | novo ADR em [`docs/decisoes/`](docs/decisoes/README.md) + linha no índice + item em "Decisões" do README |
| URL, arquivo, código de conta ou série confirmado na fonte real | [`docs/fontes.md`](docs/fontes.md) |
| Valor conferido com documento da companhia | `tests/golden/referencias.yaml` (R$ milhões) + chave em `tests/test_golden.py` |
| Documento de companhia baixado | [`referencias/README.md`](referencias/README.md) (índice; os arquivos ficam fora do git) |
| Fase concluída, comandos, como rodar, riscos | [`README.md`](README.md), seções 1 e 12 do `guia.md` e o ✅ na seção 17 do `CLAUDE.md` |
| Especificação, escopo, fórmulas previstas, roadmap | [`CLAUDE.md`](CLAUDE.md), só com o aval do usuário (itens `[DECIDIDO]` não mudam sem perguntar) |

Se código e `guia.md` discordarem, o código vence e o guia é corrigido no mesmo commit. Se código e
`CLAUDE.md` discordarem, não escolha um lado em silêncio: aponte a divergência ao usuário e, se a
decisão for mantida, registre-a num ADR.

### Antes de concluir

1. Li a seção do `guia.md` (e do `CLAUDE.md`, se for regra de negócio) antes de começar?
2. Consultei o [`docs/diagrama_atividades.md`](docs/diagrama_atividades.md) para me guiar pelo fluxo de atividades e, se o fluxo/etapas mudaram, o atualizei?
3. O `guia.md` reflete a mudança, e a versão no topo subiu conforme a regra dele?
4. O `CHANGELOG.md` tem a entrada?
5. Decisão nova ou divergência do `CLAUDE.md` virou ADR e entrou no índice?
6. Fonte ou código de conta validado foi registrado em `docs/fontes.md`?
7. Contagens e listas do README e do `guia.md` (testes, comandos, fases) estão corretas?
8. `make lint tipos testes` passa?

No resumo final, diga quais documentos foram atualizados (ou por que nenhum precisou).

### Quando escrever um ADR

Ver [`docs/decisoes/README.md`](docs/decisoes/README.md): quando escrever, modelo e regra de
substituição. Um ADR aceito não é reescrito; o novo marca o antigo como substituído.

## Testes e lint

| Comando | O que faz | Quando |
|---|---|---|
| `make lint` | `ruff check` e `ruff format --check` em `src` e `tests` | Antes de cada commit |
| `make formatar` | Corrige o que o ruff consegue e formata | Quando o lint reclamar |
| `make tipos` | `mypy` em modo strict | Antes de cada commit |
| `make testes` | `pytest` (sem rede) | Antes de cada commit |
| `make cobertura` | Testes com cobertura por linha (`--cov-report=term-missing`) | Ao fechar uma fase |
| `uv run pytest tests/test_cvm.py -k escala -q` | Teste focado | Durante o desenvolvimento |

- Teste novo em `tests/test_<modulo>.py`. Sem rede: use `SessaoFalsa` e `zip_cvm` (`conftest.py`)
  ou os geradores de `tests/sintetico.py` (detalhes na seção 14 do `guia.md`).
- Fórmula nova (métrica, DCF, WACC…) leva um teste com valor **calculado à mão** (seção 15 do
  `CLAUDE.md`).
- `test_golden.py` roda contra os dados reais de `data/processed/cvm/` e é pulado se eles não
  existirem: rode `make atualizar` antes de conferir a conciliação.
- Meta de cobertura: 80% nas camadas `contabil`, `modelos`, `custo_capital` e `perfil`.

## Convenções de código

Resumo; a lista completa e os exemplos estão na seção 13 do [`guia.md`](guia.md).

- **Camadas de baixo para cima** (`data` → `contabil` → `projecao` → `custo_capital` → `modelos` →
  `analise` → `saida`): camada inferior nunca importa superior. Todo dado externo entra por um
  adaptador em `data/` com cache em `data/raw/`.
- **Funções puras** no cálculo: `data_base` e `agora` são parâmetros; `date.today()` só no `cli.py`.
  I/O (sessão HTTP, diretórios) entra por parâmetro nomeado.
- **Dinheiro em unidades da moeda** (escala aplicada na ingestão), taxas em decimal.
- **Nunca invente dado financeiro**: faltou, falhe com mensagem clara ou use o `settings.yaml`.
- **Falhe alto**: exceções `ErroX` em português; o QA gera erro ou aviso explícito.
- **Tipos e formato**: mypy strict limpo, ruff com linha de 100. Identificadores de domínio em
  português (`receita_liquida`), termos genéricos de programação em inglês quando for o natural.
- **Objetos entre camadas** em dataclasses `frozen=True`; pydantic para configuração, com
  `extra=forbid` (campo novo exige a classe em `config.py` e o `settings.yaml`).
- **Dependência nova** fora da lista da seção 4 do `CLAUDE.md` exige ADR.

## Dúvidas

Dúvida de **negócio** (premissa, fórmula, tratamento contábil, parâmetro de mercado) se pergunta
ao usuário em vez de decidir sozinho, e entra na seção 19 do `CLAUDE.md` se ficar pendente. Faça
perguntas objetivas, com as opções e a sua recomendação; se a dúvida não bloquear o resto, avance
no que for inequívoco enquanto espera. Dúvida de **código** se resolve pelo `guia.md` e pelo código.
