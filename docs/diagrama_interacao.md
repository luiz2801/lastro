# Diagramas de Interação — Lastro

Mostram **mensagens trocadas entre objetos** para realizar um caso de uso: o de **sequência** enfatiza a ordem no tempo; o de **comunicação** (colaboração, na Aula 07) enfatiza quem fala com quem, com as mensagens numeradas. Índice em [`diagramas.md`](diagramas.md).

- `valuation rodar TICKER` (o fluxo principal) tem o seu próprio [diagrama de sequência](diagrama_sequencia.md). Aqui estão os **demais** fluxos e a visão de comunicação do `rodar`.
- Os participantes são módulos do código (as classes do [diagrama de classes](diagrama_classes.md) são dados; o comportamento é de funções de módulo).

> **Notação.** Sequência: seta cheia = chamada síncrona (o emissor espera), tracejada = retorno; `alt`/`opt`/`loop` = fragmentos combinados (condição, opcional, repetição); `autonumber` numera as mensagens. Comunicação: o Mermaid não tem esse diagrama, então é um `flowchart` com os objetos como nós e as mensagens como rótulos numerados (`1`, `1.1`, `1.2.1`…): o prefixo indica a *thread* de controle (quem chamou quem); a letra, quando há, indica fluxos concorrentes.

## 1. Sequência — `valuation atualizar`

Realiza o **UC02**. Mostra o ponto único de download (`http.baixar`) e as três saídas possíveis do cache.

```mermaid
sequenceDiagram
    autonumber
    actor U as Investidor
    participant CLI as cli.atualizar
    participant CFG as config
    participant CAD as data.cadastro
    participant CVM as data.cvm
    participant HTTP as data.http<br/>baixar()
    participant WEB as dados.cvm.gov.br
    participant FS as data/raw<br/>data/processed

    U->>CLI: atualizar --tickers PETR4,VALE3 [--com-pares] [--forcar]
    alt nenhum ou os dois de --tickers e --tudo
        CLI-->>U: erro, saída 1
    end
    CLI->>CFG: carregar_settings()
    CFG-->>CLI: Settings (ttl, historico_anos)

    CLI->>CAD: atualizar_cadastro(ano, ttl, forcar)
    CAD->>HTTP: baixar(cad_cia_aberta.csv e FCA de ano-1 e ano)
    HTTP->>FS: ler .meta.json
    alt meta fresca (agora - verificado_em < ttl) e sem --forcar
        HTTP-->>CAD: arquivo do cache, sem rede
    else vencida ou --forcar
        HTTP->>WEB: GET (If-Modified-Since, se houver)
        alt 304 Not Modified
            WEB-->>HTTP: 304
            HTTP->>FS: atualizar só verificado_em
        else 200 OK
            WEB-->>HTTP: bytes
            HTTP->>HTTP: gravar .parcial, validar (zip), os.replace
            HTTP->>FS: gravar arquivo e .meta.json (sha256, last_modified)
        else 404
            WEB-->>HTTP: 404
            HTTP-->>CAD: ArquivoNaoEncontrado (sempre propaga, mesmo com cópia)
        else falha de rede ou outro HTTP
            alt há cópia antiga e sem --forcar
                HTTP-->>CAD: cópia vencida, com warning
            else sem cópia ou com --forcar
                HTTP-->>CAD: ErroDownload
            end
        end
        HTTP-->>CAD: ArquivoBaixado
    end
    CAD->>FS: cadastro.parquet
    CAD-->>CLI: cadastro

    loop cada ticker (e cada par, com --com-pares)
        CLI->>CAD: empresa_por_ticker(cadastro, ticker)
        CAD-->>CLI: Empresa (cnpj, cd_cvm, escala_acoes)
        opt tipo_modelo = holding ou nao_suportada
            CLI-->>U: aviso: baixa os dados, mas a v1 não avalia
        end
    end

    CLI->>CVM: coletar(alvos, anos, ttl, forcar)
    loop DFP (ano-10 a ano) e ITR (ano-1 e ano)
        CVM->>HTTP: baixar(zip do ano)
        HTTP-->>CVM: ArquivoBaixado
        opt 404 no ano mais recente de cada tipo
            CVM->>CVM: registra em anos_indisponiveis e segue
        end
        CVM->>CVM: ler demonstrações e composição do capital
    end
    CVM->>CVM: valor x escala_moeda, maior versão, corrigir_escala_acoes
    CVM->>FS: demonstracoes.parquet e composicao_capital.parquet por cd_cvm
    CVM-->>CLI: ResumoColeta
    CLI-->>U: tabela por companhia e caminho gravado
```

Pontos de atenção:

- **404 nunca usa a cópia em cache** (`http.baixar` sempre o propaga) e só é tolerado por `cvm.coletar` no ano mais recente de cada tipo (o documento do ano corrente ainda pode não existir); em anos antigos vira erro.
- `--forcar` ignora o cache **e** desliga o *fallback* para cópia vencida: falha de rede vira erro.
- O download vai para `.parcial`, é validado (`validar_zip`) e só então substitui o arquivo, para nunca gravar uma página de erro HTML como se fosse zip.

## 2. Sequência — `valuation perfil`

Realiza o **UC01**. Ciclo de vida do perfil em [estados](diagrama_estados.md#1-perfil-do-investidor-perfil_investidorjson).

```mermaid
sequenceDiagram
    autonumber
    actor U as Investidor
    participant CLI as cli.perfil
    participant CFG as config
    participant REG as perfil.registro
    participant Q as perfil.questionario<br/>perfil.pontuacao
    participant PRM as perfil.parametros
    participant FS as perfil_investidor.json

    U->>CLI: perfil [--mostrar | --refazer]
    alt --mostrar e --refazer juntos
        CLI-->>U: erro, saída 1
    end
    CLI->>CFG: carregar_settings()
    CLI->>REG: ler(caminho)
    REG->>FS: abrir
    alt arquivo ausente
        REG-->>CLI: FileNotFoundError (atual = nenhum)
    else JSON inválido, versão diferente ou classificação inconsistente
        REG-->>CLI: ErroPerfil
        alt sem --refazer
            CLI-->>U: erro, saída 1
        else com --refazer
            CLI-->>U: aviso e segue
        end
    else válido
        REG-->>CLI: RegistroPerfil
    end

    alt --mostrar
        alt sem perfil gravado
            CLI-->>U: erro, saída 1
        else
            CLI->>PRM: parametros_do_perfil(perfil, settings.perfil)
            CLI-->>U: perfil e parâmetros
        end
    else perfil ainda válido e sem --refazer
        CLI-->>U: "já existe um perfil válido" e mostra
    else sem perfil, vencido ou --refazer
        opt perfil vencido
            CLI-->>U: aviso: venceu em AAAA-MM-DD
        end
        loop 10 perguntas
            CLI->>U: enunciado e alternativas
            U-->>CLI: número da alternativa
            Note over CLI,U: resposta inválida ⇒ pergunta de novo
        end
        CLI->>REG: criar_registro(respostas, hoje)
        REG->>Q: classificar(respostas)
        Q-->>REG: Classificacao (pontuação, perfil, vetos)
        REG-->>CLI: RegistroPerfil (valido_ate = hoje + 12 meses)
        CLI->>REG: gravar(registro, caminho)
        REG->>FS: escrever JSON
        CLI->>PRM: parametros_do_perfil(perfil, settings.perfil)
        PRM-->>CLI: ParametrosPerfil
        CLI-->>U: perfil, margem, pesos, horizonte, hurdle
    end
```

A validade é conferida contra `date.today()` (passado por `cli`), **não** contra a `data_base` da avaliação.

## 3. Sequência — `valuation carteira importar`

Realiza o **UC15** (o **UC14**, `lancar`, é o mesmo fluxo com uma só transação e sem a leitura de arquivo). A regra é *tudo ou nada*: nada é gravado se qualquer linha ou o histórico falhar.

```mermaid
sequenceDiagram
    autonumber
    actor U as Investidor
    participant CLI as cli.carteira_importar
    participant ARQ as carteira.arquivo
    participant TR as carteira.transacoes
    participant FS as carteira/transacoes.csv

    U->>CLI: carteira importar ARQ.xlsx [--formato-csv] [--permitir-duplicadas]
    CLI->>ARQ: ler_arquivo(arquivo, config_csv)
    ARQ->>ARQ: cabeçalho (data, ticker, tipo, quantidade obrigatórias)
    loop cada linha
        ARQ->>TR: nova_transacao(data, ticker, tipo, quantidade, ...)
        TR-->>ARQ: Transacao ou erro da linha
    end
    alt alguma linha inválida
        ARQ-->>CLI: ErroCarteira(erros: "linha N: motivo")
        CLI-->>U: uma linha por erro, saída 1
    end
    ARQ-->>CLI: transações e números das linhas

    CLI->>ARQ: acrescentar(caminho, config, transações, linhas, hoje, permitir_duplicadas)
    ARQ->>FS: carregar histórico existente
    FS-->>ARQ: transações gravadas
    alt há linha idêntica a uma gravada e sem --permitir-duplicadas
        ARQ-->>CLI: ErroCarteira (reimportação?)
        CLI-->>U: erro, saída 1, nada gravado
    end
    ARQ->>TR: validar_historico(existentes + novas, rótulos, hoje)
    Note right of TR: reproduz a carteira por data,<br/>no mesmo dia vale a ordem do arquivo
    alt venda acima da posição, evento sem posição ou data futura
        TR-->>ARQ: ErroCarteira (todos os erros juntos)
        ARQ-->>CLI: ErroCarteira
        CLI-->>U: erros, saída 1, nada gravado
    end
    ARQ->>FS: acrescentar ao fim (BOM só na criação do arquivo)
    ARQ-->>CLI: quantidade gravada
    CLI-->>U: "Importadas N transações"
```

## 4. Sequência — execução em lote: `rodar-setor` e `favoritos atualizar`

Realizam o **UC10** e o **UC11**. Ambos chamam o `rodar` de cada empresa; uma falha isolada não interrompe as demais, e o comando sai com 1 se alguma falhou.

```mermaid
sequenceDiagram
    autonumber
    actor U as Investidor
    participant CLI as cli
    participant UNI as universo /<br/>saida.favoritos
    participant REG as perfil.registro
    participant RODAR as cli.rodar

    U->>CLI: rodar-setor SETOR  ou  favoritos atualizar [--max-idade-dias N]
    alt rodar-setor
        CLI->>UNI: buscar_setor, carregar_universo, empresas_do_setor
        UNI-->>CLI: empresas do setor (ordem do CSV)
    else favoritos atualizar
        CLI->>UNI: carregar_favoritos(config/favoritos.yaml)
        UNI-->>CLI: tickers
    end
    CLI->>REG: resolver_perfil(caminho, hoje, override)
    alt perfil ausente ou vencido, sem --perfil
        REG-->>CLI: ErroPerfil
        CLI-->>U: erro, saída 1, antes do laço
    end

    loop cada empresa ou favorito
        alt rodar-setor e tipo fora de nao_financeira e financeira
            CLI->>CLI: resultado = "pulado (fora da v1)"
        else favoritos e último resumo.csv com idade ≤ N dias (N > 0)
            CLI->>UNI: ultimo_resumo(ticker, saida/)
            CLI->>CLI: resultado = "em dia (idade d)"
        else
            CLI->>RODAR: rodar(ticker, padrões)
            alt rodar termina com erro (typer.Exit)
                RODAR-->>CLI: Exit
                CLI->>CLI: resultado = "falhou"
            else
                RODAR-->>CLI: pasta saida/TICKER/data-base/
                CLI->>CLI: resultado = "ok"
            end
        end
    end
    CLI-->>U: tabela ticker × resultado
    opt alguma falhou
        CLI-->>U: "N empresa(s) falharam", saída 1
    end
```

O `rodar-setor` não gera resumo consolidado entre empresas (ADR 0019); cada empresa grava a sua pasta como em `rodar`. No `favoritos atualizar`, o "cache de resultados" é o próprio `resumo.csv` da pasta mais recente (ADR 0021): nada novo é persistido.

## 5. Comunicação — `valuation rodar TICKER` (visão condensada)

Os mesmos objetos do [diagrama de sequência](diagrama_sequencia.md), vistos pelas **ligações** entre eles. O número indica a ordem; `1.8.1` é uma mensagem enviada **durante** a `1.8`.

```mermaid
flowchart LR
    inv(["<u>:Investidor</u>"])
    cli["<u>:cli</u>"]
    reg["<u>:perfil.registro</u>"]
    ctb["<u>:contabil</u>"]
    prj["<u>:projecao</u>"]
    dad["<u>:data</u><br/>precos, macro, validacao"]
    cc["<u>:custo_capital</u>"]
    mod["<u>:modelos</u><br/>dcf, ponte, multiplos"]
    ana["<u>:analise</u><br/>cenarios, sensibilidade"]
    out["<u>:saida</u>"]

    inv -->|"1: rodar(ticker)"| cli
    cli -->|"1.1: resolver_perfil()"| reg
    cli -->|"1.2: _padronizar() e qa"| ctb
    cli -->|"1.3: _sugerir() e _resolver()"| prj
    cli -->|"1.4: _mercado()"| dad
    cli -->|"1.5: _coletar_pares()"| dad
    cli -->|"1.6: _custo_capital()"| cc
    cli -->|"1.7: _multiplos()"| mod
    cli -->|"1.8: analisar(...)"| ana
    ana -->|"1.8.1: projetar()"| prj
    ana -->|"1.8.2: dcf.avaliar() e ponte()"| mod
    cli -->|"1.9: wacc_x_g() e margem_x_crescimento()"| ana
    cli -->|"1.10: gravar CSV, JSON, YAML, PNG"| out
    cli -->|"2: tabelas e caminho gravado"| inv

    classDef obj fill:#fff8e1,stroke:#f08c00,color:#1a1a1a
    classDef ator fill:#dbe4ff,stroke:#3b5bdb,color:#1a1a1a
    class cli,reg,ctb,prj,dad,cc,mod,ana,out obj
    class inv ator
```

A estrutura em **estrela** em torno de `cli` é intencional (regra do projeto): `cli.py` só orquestra; as camadas não se chamam entre si, e o motor de cálculo recebe tudo por parâmetro. A única colaboração direta entre camadas é `analise → projecao` e `analise → modelos`, dentro do laço de cenários, que dependem só de funções puras.

## 6. Comunicação — `valuation carteira lancar`

Realiza o **UC14**.

```mermaid
flowchart LR
    inv(["<u>:Investidor</u>"])
    cli["<u>:cli</u><br/>carteira_lancar"]
    cfg["<u>:config</u>"]
    tr["<u>:carteira.transacoes</u>"]
    arq["<u>:carteira.arquivo</u>"]
    fs[("<u>carteira/<br/>transacoes.csv</u>")]

    inv -->|"1: carteira lancar compra XPTO3 100 --preco 10"| cli
    cli -->|"1.1: carregar_settings()"| cfg
    cli -->|"1.2: nova_transacao(data, ticker, tipo, ...)"| tr
    cli -->|"1.3: acrescentar(caminho, csv, [t], hoje)"| arq
    arq -->|"1.3.1: carregar(caminho)"| fs
    arq -->|"1.3.2: validar_historico(existentes + t)"| tr
    arq -->|"1.3.3: acrescentar ao fim"| fs
    cli -->|"2: Gravado: compra XPTO3 x 100 em AAAA-MM-DD"| inv

    classDef obj fill:#fff8e1,stroke:#f08c00,color:#1a1a1a
    classDef ator fill:#dbe4ff,stroke:#3b5bdb,color:#1a1a1a
    class cli,cfg,tr,arq,fs obj
    class inv ator
```

Em erro (`ErroCarteira`), a mensagem `2` vira uma linha por erro e a saída é 1; o arquivo permanece como estava.
