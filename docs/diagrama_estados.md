# Diagramas de Estados — Lastro

Mostram os estados pelos quais um objeto (ou uma execução) passa durante a vida, e os **eventos** que provocam cada transição. Só entram os elementos que têm ciclo de vida de fato; os cálculos puros (`dcf`, `ponte`…) não têm estado, e por isso não aparecem. Índice em [`diagramas.md`](diagramas.md).

> **Notação** (Aula 09). Transição: `evento [guarda] / ação`. `[*]` = estado inicial ou final. `entry/` e `exit/` = ações ao entrar e sair; `do/` = atividade em andamento. Estados compostos agrupam subestados; `<<choice>>` é uma decisão sobre a guarda.

| # | Objeto | Onde está no código |
|---|---|---|
| 1 | Perfil do investidor (`perfil_investidor.json`) | `perfil/registro.py` |
| 2 | Arquivo no cache de download | `data/http.py` (`baixar`) |
| 3 | Leitura validada entre duas fontes (`Validado`) | `data/validacao.py` (`cruzar`) |
| 4 | Execução do comando `rodar` | `cli.py` (`rodar`) |
| 5 | Importação de transações da carteira | `carteira/arquivo.py` (`acrescentar`) |
| 6 | Favorito e o seu último resultado | `saida/favoritos.py` |

## 1. Perfil do investidor (`perfil_investidor.json`)

O perfil tem **validade de 12 meses** e um esquema rígido: `registro.ler` recalcula a pontuação e recusa um arquivo adulterado. O perfil `--perfil X` (override) não passa por aqui: não lê nem grava o arquivo.

```mermaid
stateDiagram-v2
    direction LR
    [*] --> Ausente

    Ausente --> Valido : perfil / responder questionário, gravar JSON
    Valido --> Vencido : hoje > valido_ate
    Vencido --> Valido : perfil / responder questionário, gravar JSON
    Valido --> Valido : perfil --refazer / responder de novo
    Valido --> Invalido : arquivo editado, versão do questionário diferente
    Invalido --> Valido : perfil --refazer / responder de novo
    Vencido --> Invalido : arquivo editado
    Ausente --> Ausente : perfil --mostrar / erro, saída 1

    state Valido {
        [*] --> EmUso
        EmUso : <b>EmUso</b><br/>rodar, rodar-setor e favoritos atualizar leem o perfil
        EmUso : entry / valido_ate = data + 12 meses
    }
    state Vencido {
        [*] --> Bloqueado
        Bloqueado : <b>Bloqueado</b><br/>rodar recusa (sem --perfil)
        Bloqueado : perfil mostra "venceu em AAAA-MM-DD"
    }
    state Invalido {
        [*] --> Recusado
        Recusado : <b>Recusado</b><br/>ler levanta ErroPerfil
        Recusado : só --refazer aceita o arquivo corrompido
    }
```

- **Ausente**: não há arquivo (`FileNotFoundError` em `ler`). `rodar` sem `--perfil` falha com a instrução de rodar `valuation perfil`.
- **Válido** inclui o dia de `valido_ate` (`vencido` é `hoje > valido_ate`). Um perfil gravado em 29/02 vale até 28/02 do ano seguinte.
- O **veto** (horizonte menor que 2 anos ou "não aceito perdas") é aplicado dentro da transição de gravação e força `conservador`; não é um estado.

## 2. Arquivo no cache de download (`http.baixar`)

Estados de um arquivo em `data/raw/`, com o seu `.meta.json`. É por esta máquina que o resto do projeto fica **offline dentro do TTL**.

```mermaid
stateDiagram-v2
    [*] --> SemCache

    SemCache --> Baixando : baixar()
    Fresco --> Fresco : baixar() / devolver cache, sem rede
    Fresco --> Vencido : agora - verificado_em ≥ ttl
    Fresco --> Baixando : baixar(forcar)
    Vencido --> Baixando : baixar()
    Vencido --> Baixando : baixar(forcar)

    state Baixando {
        [*] --> Requisitando
        Requisitando : <b>Requisitando</b><br/>do / GET (If-Modified-Since, se houver e sem forcar)
        Requisitando --> Gravando : HTTP 200
        Gravando : <b>Gravando</b><br/>do / gravar .parcial e calcular sha256
        Gravando --> Validando : bytes completos
        Validando : <b>Validando</b><br/>do / validar(temp), ex.: é um zip?
        Validando --> [*] : válido / os.replace e gravar meta
    }

    Baixando --> Fresco : 200 válido / baixado_em e verificado_em = agora
    Baixando --> Fresco : 304 / só verificado_em = agora
    Baixando --> Fresco : falha de rede ou HTTP, com cópia e sem forcar / usar cópia vencida, com warning
    Baixando --> Erro : 404 / ArquivoNaoEncontrado
    Baixando --> Erro : falha sem cópia, ou com forcar / ErroDownload
    Baixando --> Erro : conteúdo inválido / ErroDownload
    Erro --> [*]
```

- `Fresco` aqui inclui a "cópia vencida usada com aviso": o chamador recebe `do_cache=True`, mas o `verificado_em` **não** é renovado, então a próxima chamada tenta a rede de novo.
- `404` ignora a cópia: propaga sempre. `forcar` desliga o `If-Modified-Since` **e** o *fallback* para cópia.
- O `.parcial` é descartado se a validação falhar; o arquivo anterior nunca é sobrescrito por conteúdo inválido.

## 3. Leitura validada entre duas fontes (`Validado`)

Cada dado de mercado e macro (preço, dólar, Selic, IPCA, Rf) nasce de uma comparação entre fonte principal e alternativa (ADR 0004). O `status` final é o estado do objeto; **só** a ausência das duas fontes interrompe.

```mermaid
stateDiagram-v2
    [*] --> Coletando : cruzar(nome, principal, alternativa)
    [*] --> Manual : manual(nome, valor)

    Coletando --> Comparando : as duas fontes responderam
    Coletando --> SemValidacao : só uma respondeu
    Coletando --> Falha : nenhuma respondeu

    Comparando --> Ok : divergência ≤ tolerância
    Comparando --> Divergente : divergência > tolerância

    Ok --> [*]
    Divergente --> [*] : valor = o da fonte principal, aviso e warning
    SemValidacao --> [*] : valor = o da que respondeu, aviso e warning
    Manual --> [*] : valor = o do settings (ex.: rf_brl.override)
    Falha --> [*] : ErroDadosExternos, o comando termina com erro
```

A divergência é relativa (`|a−b|/|a|`) em preço e câmbio (2% e 1,5%) e absoluta nas taxas (Selic, IPCA, Rf). Os avisos sobem para o terminal e para o `meta.json`.

## 4. Execução do comando `rodar`

Estados da execução de `valuation rodar TICKER` (acompanha o [diagrama de atividades](diagrama_atividades.md); aqui o interesse é **onde ela pode terminar**). Qualquer erro de domínio leva a `Interrompido`, com mensagem em PT-BR e saída 1.

```mermaid
stateDiagram-v2
    [*] --> ValidandoPerfil : rodar(ticker)

    ValidandoPerfil --> Padronizando : perfil válido ou --perfil
    Padronizando --> EscolhendoModelo : QA sem erro
    EscolhendoModelo --> Avaliando : nao_financeira ou financeira
    EscolhendoModelo --> Interrompido : holding ou nao_suportada

    state Avaliando {
        [*] --> Premissas
        Premissas --> Mercado : sugeridas e resolvidas
        Mercado --> Pares : preço, macro e market cap
        Pares --> CustoCapital : pares medidos (aviso se falharem)
        CustoCapital --> Cenarios : WACC > g (ou Ke > g)
        Cenarios --> Sensibilidade : valor ponderado e preço máximo
        Sensibilidade --> [*]
        Premissas : <b>Premissas</b><br/>DCF: FCFF · DDM: ROE e payout
        CustoCapital : <b>CustoCapital</b><br/>DCF: beta, Ke, Kd, WACC · DDM: beta e Ke
        Cenarios : <b>Cenarios</b><br/>pessimista, base e otimista (ou só um)
    }

    Avaliando --> Gravando : resultados em memória
    Gravando --> Concluido : CSV, JSON, YAML e PNG, meta.json por último
    Concluido --> [*]

    ValidandoPerfil --> Interrompido : ErroPerfil
    Padronizando --> Interrompido : ErroContabil ou erro de QA
    Avaliando --> Interrompido : ErroDadosExternos, ErroCustoCapital, ErroProjecao, ErroModelo
    Interrompido --> [*] : saída 1
```

- `Gravando` só começa depois do cálculo dos cenários e da sensibilidade: um erro de domínio no cálculo não deixa saída pela metade. O `meta.json` é gravado por último, e lista os arquivos que existem na pasta (inclusive os de execuções anteriores).
- `Concluido` com avisos continua sendo sucesso (saída 0): divergência de fontes, par sem dados, VT/EV alto, ROE abaixo do Ke e semelhantes são avisos, não erros.

## 5. Importação de transações da carteira

Estados de uma importação (`carteira importar`) ou de um lançamento (`carteira lancar`, que pula a leitura do arquivo). A saída é **tudo ou nada**.

```mermaid
stateDiagram-v2
    [*] --> Lendo : carteira importar ARQUIVO

    Lendo --> Convertendo : cabeçalho válido
    Lendo --> Recusada : coluna obrigatória ausente ou desconhecida
    Convertendo --> ConferindoDuplicadas : todas as linhas válidas
    Convertendo --> Recusada : alguma linha inválida / linha N e motivo

    ConferindoDuplicadas --> ValidandoHistorico : sem repetidas, ou --permitir-duplicadas
    ConferindoDuplicadas --> Recusada : idêntica a linha já gravada

    ValidandoHistorico --> Gravando : carteira + novas fecham, por data
    ValidandoHistorico --> Recusada : venda acima da posição, evento sem posição, data futura

    Gravando --> Gravada : acrescentar ao fim, sem reescrever o que existe
    Gravada --> [*] : "Importadas N transações"
    Recusada --> [*] : uma linha por erro, saída 1, nada gravado

    note right of Recusada
        o arquivo transacoes.csv
        permanece como estava
    end note
```

## 6. Favorito e o seu último resultado

O "cache de resultados" é o `resumo.csv` da pasta mais recente de `saida/{TICKER}/` (ADR 0021). O estado é **derivado** (idade do resultado contra `--max-idade-dias`); não há campo persistido.

```mermaid
stateDiagram-v2
    [*] --> SemRodada : favoritos adicionar TICKER

    SemRodada --> Rodando : favoritos atualizar
    EmDia --> Desatualizado : idade > N dias (o tempo passa)
    Desatualizado --> Rodando : favoritos atualizar
    EmDia --> Rodando : favoritos atualizar --max-idade-dias 0 (todos)
    EmDia --> EmDia : favoritos atualizar / pula, "em dia"

    Rodando --> EmDia : rodar ok / novo resumo.csv
    Rodando --> Desatualizado : rodar falhou, havia resultado antigo
    Rodando --> SemRodada : rodar falhou, nunca houve resultado

    SemRodada --> [*] : favoritos remover
    EmDia --> [*] : favoritos remover
    Desatualizado --> [*] : favoritos remover

    SemRodada : <b>SemRodada</b><br/>tabela mostra "sem rodada"
    EmDia : <b>EmDia</b><br/>idade ≤ N, o valor é o da data-base daquela rodada
    Desatualizado : <b>Desatualizado</b><br/>idade > N, preço e valor ficam do dia da rodada
```

`favoritos` (sem subcomando) só **lê**: mostra o estado de cada ticker sem rede. O valor exibido é sempre o da última rodada, com o preço daquele dia (por isso existe a coluna *Idade*).
