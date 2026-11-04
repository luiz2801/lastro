# Diagramas UML do Lastro — índice e convenções

O modelo do sistema é um conjunto de diagramas **consistentes entre si**, cada um uma vista diferente do mesmo código (Aula 03: "um diagrama é uma vista sobre um modelo; o mesmo elemento pode aparecer em vários diagramas"). Este arquivo diz qual diagrama responder a qual pergunta, como eles se ligam e como mantê-los.

> Os diagramas **não substituem** o [`guia.md`](../guia.md) (contratos, parâmetros, armadilhas) nem as [regras modulares](regras/README.md); eles dão as vistas estrutural e dinâmica. Se código e diagrama discordarem, **o código vence** e o diagrama deve ser corrigido.

## 1. Mapa: diagrama, pergunta e arquivo

| Aula | Diagrama UML | Pergunta que responde | Arquivo |
|---|---|---|---|
| 04 | **Casos de uso** | Quem usa o sistema e o que pode pedir? | [`diagrama_casos_de_uso.md`](diagrama_casos_de_uso.md) |
| 05 | **Classes** | Que objetos existem, com que atributos, e como se relacionam? | [`diagrama_classes.md`](diagrama_classes.md) |
| 06 | **Objetos** | Como é uma execução "congelada", com valores reais? | [`diagrama_objetos.md`](diagrama_objetos.md) |
| 07 | **Sequência** | Em que ordem os módulos se chamam? | [`diagrama_sequencia.md`](diagrama_sequencia.md) (`rodar`) e [`diagrama_interacao.md`](diagrama_interacao.md) (demais comandos) |
| 07 | **Comunicação** (colaboração) | Quem fala com quem, e em que encadeamento? | [`diagrama_interacao.md`](diagrama_interacao.md) |
| 08 | **Atividades** | Qual o fluxo de ponta a ponta, com decisões e paralelismo? | [`diagrama_atividades.md`](diagrama_atividades.md) |
| 09 | **Estados** | Que estados tem um objeto ou uma execução, e o que muda cada um? | [`diagrama_estados.md`](diagrama_estados.md) |
| 10 | **Pacotes** (arquitetura lógica) | Como o código se divide em camadas e quem depende de quem? | [`diagrama_arquitetura.md`](diagrama_arquitetura.md) §1 |
| 10 | **Componentes** (arquitetura física) | Quais as peças físicas, interfaces e arquivos? | [`diagrama_arquitetura.md`](diagrama_arquitetura.md) §2 |
| 10 | **Implantação** (distribuição) | Onde roda e com quem fala? | [`diagrama_arquitetura.md`](diagrama_arquitetura.md) §3 |

A Aula 03 (visão geral) não pede um diagrama: este índice e a seção 2 cobrem os seus elementos de modelagem.

## 2. Elementos de modelagem (Aula 03) e onde aparecem

| Elemento | No Lastro |
|---|---|
| **Estruturais** — classe, objeto, interface, componente, nó | Dataclasses e modelos pydantic (classes); instâncias do `rodar` (objetos); `PrecosProvider` e `SessaoHttp` (interfaces); `cli`, `data`, motor, `saida` (componentes); a máquina do investidor e as fontes públicas (nós) |
| **Comportamentais** — caso de uso, ator, estado, mensagem, transição | Comandos da CLI (casos de uso); Investidor, CVM, BCB e Tesouro, Yahoo e brapi (atores); perfil, cache, `Validado`, execução do `rodar` (estados); chamadas entre módulos (mensagens) |
| **Agrupamento** — pacote | `data`, `contabil`, `projecao`, `custo_capital`, `modelos`, `analise`, `saida`, `perfil`, `carteira` |
| **Extensão e anotação** — estereótipo, nota | `«include»`, `«extend»`, `«Protocol»`, `«enumeration»`, `«executable»`, `«file»`; notas de texto sob cada diagrama |

## 3. Rastreabilidade: do caso de uso às classes

Cada linha é uma mesma funcionalidade vista por vários diagramas.

| Caso de uso | Sequência ou comunicação | Atividades | Estados | Classes principais |
|---|---|---|---|---|
| UC01 Definir perfil | [interação §2](diagrama_interacao.md#2-sequência--valuation-perfil) | raia 1 | [perfil](diagrama_estados.md#1-perfil-do-investidor-perfil_investidorjson) | `RegistroPerfil`, `Classificacao`, `ParametrosPerfil` |
| UC02 Atualizar dados | [interação §1](diagrama_interacao.md#1-sequência--valuation-atualizar) | raia 2 | [cache](diagrama_estados.md#2-arquivo-no-cache-de-download-httpbaixar) | `ArquivoBaixado`, `MetaDownload`, `Empresa`, `AlvoCVM` |
| UC09 Avaliar empresa | [sequência](diagrama_sequencia.md), [comunicação](diagrama_interacao.md#5-comunicação--valuation-rodar-ticker-visão-condensada) | raias 1 a 6 | [rodar](diagrama_estados.md#4-execução-do-comando-rodar) | `Avaliacao`, `ResultadoDCF`, `AvaliacaoDDM`, `CustoCapital`, `ResultadoCenarios` |
| UC10 e UC11 Lote | [interação §4](diagrama_interacao.md#4-sequência--execução-em-lote-rodar-setor-e-favoritos-atualizar) | raia 1 | [favorito](diagrama_estados.md#6-favorito-e-o-seu-último-resultado) | `EmpresaUniverso`, `SetorCVM`, `ResumoFavorito` |
| UC17 Posição | — | seção 4 (posição) | — | `Posicao`, `Preco`, `LinhaCarteira`, `ResumoCarteira` |
| UC14 e UC15 Carteira | [interação §3](diagrama_interacao.md#3-sequência--valuation-carteira-importar), [§6](diagrama_interacao.md#6-comunicação--valuation-carteira-lancar) | seção 4 | [importação](diagrama_estados.md#5-importação-de-transações-da-carteira) | `Transacao`, `TipoTransacao` |

## 4. Notação e limites do Mermaid

Todos os diagramas são **Mermaid** em Markdown: aparecem renderizados no GitHub e em editores com suporte, e diferenciam-se bem em `git diff`. O Mermaid cobre nativamente classes, sequência e estados; os demais tipos usam `flowchart` com convenções, que estão explicadas no começo de cada arquivo:

| Diagrama | Como é desenhado |
|---|---|
| Casos de uso | Elipses e atores estereotipados; `«include»` e `«extend»` como setas tracejadas rotuladas |
| Objetos | Caixas com o nome sublinhado (`nome : Classe`) e os valores dos atributos |
| Comunicação | Objetos como nós e mensagens numeradas (`1`, `1.1`, `1.2.1`) nas arestas |
| Pacotes, componentes, implantação | Grupos aninhados, círculos para interfaces, artefatos dentro de nós |

Convenções comuns: nomes iguais aos do código (módulos, funções e classes), texto em português, estereótipos entre `« »`, e nota sob cada diagrama com o que o desenho não mostra.

## 5. Manutenção

Atualize o diagrama **na mesma entrega** da mudança que o afeta (regra 11 do `CLAUDE.md`, estendida a todos os tipos):

| O que mudou | Diagrama a atualizar |
|---|---|
| Comando novo, removido ou com opção que muda o comportamento; novo ator ou fonte externa | Casos de uso; implantação, se houver fonte nova |
| Classe, dataclass ou campo novo, removido ou renomeado; nova relação entre classes | Classes (e Objetos, se o exemplo usa o campo) |
| Ordem das chamadas entre módulos, novo módulo na orquestração | Sequência e Comunicação |
| Etapa, decisão, bifurcação ou saída do pipeline | Atividades |
| Novo estado, regra de validade ou de TTL, nova transição (perfil, cache, validação, carteira, favoritos) | Estados |
| Novo pacote, nova dependência entre pacotes, nova biblioteca ou fonte externa, novo arquivo persistido | Arquitetura (pacotes, componentes, implantação) |

A direção das dependências entre pacotes pode ser conferida com o código; o grafo de [arquitetura §1](diagrama_arquitetura.md) foi extraído dos `import` por análise da AST e não deve ganhar ciclos.

### Como renderizar e validar

Para conferir um diagrama antes de commitar, com o [`mermaid-cli`](https://github.com/mermaid-js/mermaid-cli) (não é dependência do projeto):

```bash
npx -p @mermaid-js/mermaid-cli mmdc -i diagrama.mmd -o diagrama.png
```

Cuidados que já causaram erro de sintaxe: `par` e outras palavras reservadas como identificador de participante em `sequenceDiagram`; `;` dentro de `Note` ou de mensagem (encerra o comando); parênteses ou `|` em rótulo sem aspas num `flowchart` (use `"..."`). Na 11.4.1 as ligações `---` saíram com ponta de seta; na 11.17 saem como linha simples (as duas versões foram testadas aqui), então confira com uma versão recente.
