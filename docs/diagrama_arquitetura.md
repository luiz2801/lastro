# Arquitetura — Lastro

Decisões estruturais do sistema em três visões, da lógica à física (Aula 10): **pacotes** (arquitetura lógica), **componentes** (arquitetura física do software) e **implantação** (ambiente de hardware). Índice em [`diagramas.md`](diagramas.md); as regras por camada estão em [`docs/regras/`](regras/README.md) e o detalhe de cada módulo no [`guia.md`](../guia.md).

> **Notação.** O Mermaid não tem diagramas de pacotes, componentes nem implantação; todos são `flowchart`. Pacote = caixa com o nome do pacote; componente = caixa marcada com `«componente»`; interface = círculo; nó de hardware = grupo `«nó»`; artefato = caixa dentro do nó. Seta cheia = dependência (`importa` ou `usa`); tracejada = realização, ou leitura/gravação de dados.

## 1. Arquitetura lógica — diagrama de pacotes

Estilo: **camadas em pipeline, com uma fachada de orquestração**. O grafo abaixo é o **real**, extraído dos `import` de `src/valuation/` (não o desejado): cada seta é "importa". Não há ciclos.

```mermaid
flowchart BT
    subgraph ORQ["Orquestração e interface"]
        cli["cli<br/>(typer, rich)"]
        servicos["servicos<br/>empresa"]
    end

    subgraph APL["Aplicação (camadas de cálculo e saída)"]
        saida["saida<br/>csv, graficos, arquivos,<br/>real, glossario, favoritos"]
        analise["analise<br/>cenarios, sensibilidade,<br/>indicadores"]
        modelos["modelos<br/>dcf, ddm, ponte, multiplos"]
        projecao["projecao<br/>premissas, sugestor,<br/>projetor, financeira, escrita"]
        custo["custo_capital<br/>beta, capm, kd, wacc,<br/>erp_implicito"]
    end

    subgraph DOM["Domínio e dados"]
        contabil["contabil<br/>padronizacao, periodos, moeda,<br/>qa, nao_financeiras, financeiras"]
        perfil["perfil<br/>questionario, pontuacao,<br/>registro, parametros"]
        data["data<br/>http, cadastro, cvm,<br/>precos, macro, validacao"]
        carteira["carteira<br/>transacoes, arquivo"]
        universo["universo<br/>SetorCVM, EmpresaUniverso"]
    end

    config["config<br/>Settings, Setor, ler_yaml"]

    cli --> servicos
    servicos --> contabil & data & projecao & config
    cli --> saida & analise & modelos & projecao & custo & contabil & perfil & data & carteira & universo & config
    analise --> modelos & projecao & custo & perfil
    saida --> modelos & config
    modelos --> projecao
    projecao --> contabil & config
    contabil --> config
    perfil --> config
    data --> config
    carteira --> config
    universo --> config

    classDef pacote fill:#eef2ff,stroke:#5c7cfa,color:#1a1a1a
    classDef base fill:#e9ecef,stroke:#868e96,color:#1a1a1a
    classDef topo fill:#fff8e1,stroke:#f08c00,color:#1a1a1a
    class saida,analise,modelos,projecao,custo,contabil,perfil,data,carteira,universo pacote
    class config base
    class cli,servicos topo
    style ORQ fill:#fafafa,stroke:#adb5bd,color:#1a1a1a
    style APL fill:#fafafa,stroke:#adb5bd,color:#1a1a1a
    style DOM fill:#fafafa,stroke:#adb5bd,color:#1a1a1a
```

### Regras que o grafo materializa

| Regra | Como o grafo mostra |
|---|---|
| Camada superior nunca é importada por inferior | Todas as setas apontam para baixo; **só `cli` conhece todo mundo**, e `servicos` fica logo abaixo dela. |
| Trocar de fonte não toca nos modelos (regra 3 do `CLAUDE.md`) | `data` só depende de `config`; nenhum pacote de cálculo importa `data`. A `cli` entrega preços, macro e balanços por parâmetro. |
| O motor é de funções puras | `contabil`, `projecao`, `custo_capital`, `modelos` e `analise` não importam `data`: nada ali faz I/O de rede, e `data_base` e `agora` são parâmetros. |
| Perfil não altera fatos contábeis | `perfil` só depende de `config`; `analise` o consome para ponderar cenários, e `contabil`, `custo_capital` e `modelos` nem o conhecem. |
| Carteira fora do valuation (ADR 0020) | `carteira` só importa `config`; nenhuma camada de valuation a importa. |

Notas sobre desvios da imagem "em linha" do `CLAUDE.md` (seção 3, `data → contabil → projecao → …`):

- `data` e `contabil` são **independentes**: `contabil` lê `demonstracoes.parquet` pelo caminho (`padronizacao.ler_demonstracoes`), sem importar `data`.
- `custo_capital` **não depende de ninguém** (nem de `config`): recebe preços, taxas e métricas por parâmetro. Quem a consome é `analise` (Ke → WACC) e a `cli`.
- `saida` depende de `modelos` (para serializar `Avaliacao` e `AvaliacaoDDM`), não de `analise`.
- `universo` é só leitura do `config/universo_ibovespa.csv`; não consulta rede nem cadastro.

### Responsabilidades

| Pacote | Responsabilidade | Exceção própria |
|---|---|---|
| `config` | Carrega e valida `settings.yaml`, `setores.yaml` e caminhos; `extra="forbid"` | `ErroConfiguracao` |
| `data` | Único ponto de contato com o mundo externo: download com cache, CVM, cadastro, preços, macro, validação cruzada | `ErroDownload`, `ErroCadastro`, `ErroDadosCVM`, `ErroDadosExternos` |
| `contabil` | Reapresentações, plano de contas padronizado, períodos (anual, YTD, LTM), moeda, QA, métricas | `ErroContabil` |
| `perfil` | Questionário, pontuação, vetos, JSON com validade, parâmetros por perfil | `ErroPerfil` |
| `projecao` | Schema das premissas, sugestor, resolução por cenário, projeção ano a ano (FCFF e DDM) | `ErroProjecao` |
| `custo_capital` | Beta, Ke (CAPM), Kd, WACC, ERP implícito | `ErroCustoCapital` |
| `modelos` | DCF, ponte EV → equity, DDM com lucro residual, múltiplos | `ErroModelo` |
| `analise` | Cenários ponderados pelo perfil, taxas implícitas, matrizes de sensibilidade, indicadores por ativo | (usa `ErroModelo`) |
| `saida` | CSV, `meta.json`, valores reais, gráficos, glossário, favoritos | — |
| `carteira` | Transações da carteira pessoal: validação e importação CSV/XLSX | `ErroCarteira` |
| `universo` | Setores da CVM e empresas do Ibovespa por setor | — |
| `servicos` | Orquestração sem apresentação, comum à CLI e à GUI (ADR 0022); avisos no retorno | exceções de domínio das camadas abaixo |
| `cli` | Comandos `typer`, orquestração, tabelas `rich`, códigos de saída | captura todas as anteriores |

## 2. Arquitetura física — diagrama de componentes

Componentes são as peças físicas e substituíveis; interfaces são os pontos de troca. O sistema é **um só executável** (`valuation`) que usa bibliotecas e lê e grava arquivos locais: não há servidor próprio, banco de dados nem serviço.

```mermaid
flowchart LR
    subgraph EXE["«executable» valuation (uv run valuation)"]
        direction TB
        cmd["«componente»<br/>cli (typer, rich)<br/>entry point valuation.cli:app"]
        subgraph LIB["«library» pacote valuation (src/valuation)"]
            direction TB
            c_data["«componente»<br/>data"]
            c_motor["«componente»<br/>motor de cálculo<br/>contabil, projecao, custo_capital,<br/>modelos, analise"]
            c_perfil["«componente»<br/>perfil"]
            c_saida["«componente»<br/>saida"]
            c_cart["«componente»<br/>carteira"]
            c_cfg["«componente»<br/>config"]
        end
    end

    iprecos(("PrecosProvider"))
    isessao(("SessaoHttp"))
    c_yf["YFinanceProvider"]
    c_br["BrapiProvider"]
    c_req["requests.Session<br/>(retry, User-Agent)"]

    subgraph TERC["«library» bibliotecas de terceiros"]
        direction TB
        l_dados["pandas · numpy · pyarrow"]
        l_cfg["pydantic · pyyaml"]
        l_cli["typer · rich"]
        l_calc["statsmodels · scipy"]
        l_graf["matplotlib"]
        l_net["requests · yfinance"]
        l_xls["openpyxl (só importação XLSX)"]
    end

    subgraph ARQ["Arquivos locais"]
        direction TB
        f_cfg[/"«file» config/<br/>settings.yaml, setores.yaml,<br/>mapeamento_contas.yaml,<br/>empresas/*.yaml, universo, cadastro_manual"/]
        f_raw[("«database» data/raw<br/>zip, csv, json, parquet de preços<br/>+ .meta.json")]
        f_proc[("«database» data/processed<br/>parquets por companhia, cadastro,<br/>qa, erp_implicito.json")]
        f_perfil[/"«file» perfil/perfil_investidor.json"/]
        f_saida[/"«file» saida/TICKER/AAAA-MM-DD/<br/>CSV, JSON, YAML, PNG"/]
        f_cart[/"«file» carteira/transacoes.csv"/]
        f_fav[/"«file» config/favoritos.yaml"/]
    end

    cmd --> c_data & c_motor & c_perfil & c_saida & c_cart & c_cfg

    c_yf -.->|"«realiza»"| iprecos
    c_br -.->|"«realiza»"| iprecos
    c_req -.->|"«realiza»"| isessao
    c_data -->|"«usa»"| iprecos
    c_data -->|"«usa»"| isessao
    c_data --- c_yf
    c_data --- c_br

    c_cfg -.->|"lê"| f_cfg
    c_data -.->|"lê e grava"| f_raw
    c_data -.->|"grava"| f_proc
    c_motor -.->|"lê (via cli)"| f_proc
    c_perfil -.->|"lê e grava"| f_perfil
    c_saida -.->|"grava"| f_saida
    c_saida -.->|"lê e grava"| f_fav
    c_cart -.->|"lê e acrescenta"| f_cart

    c_cfg --> l_cfg
    cmd --> l_cli
    c_data --> l_net & l_dados
    c_motor --> l_dados & l_calc
    c_saida --> l_graf
    c_cart --> l_xls

    classDef comp fill:#eef2ff,stroke:#5c7cfa,color:#1a1a1a
    classDef ext fill:#e9ecef,stroke:#868e96,color:#1a1a1a
    classDef arq fill:#fff8e1,stroke:#f08c00,color:#1a1a1a
    class cmd,c_data,c_motor,c_perfil,c_saida,c_cart,c_cfg,c_yf,c_br,c_req comp
    class l_dados,l_cfg,l_cli,l_calc,l_graf,l_net,l_xls ext
    class f_cfg,f_raw,f_proc,f_perfil,f_saida,f_cart,f_fav arq
    style EXE fill:#fafafa,stroke:#adb5bd,color:#1a1a1a
    style LIB fill:#ffffff,stroke:#adb5bd,color:#1a1a1a
    style TERC fill:#fafafa,stroke:#adb5bd,color:#1a1a1a
    style ARQ fill:#fafafa,stroke:#adb5bd,color:#1a1a1a
```

### Interfaces

| Interface | Quem a oferece | Quem a usa | Para que serve |
|---|---|---|---|
| `PrecosProvider` (Protocol) | `YFinanceProvider` (principal), `BrapiProvider` (alternativa) | `precos.preco_validado`; a `cli` também o usa para entregar o câmbio alternativo a `macro`, por parâmetro | Trocar ou acrescentar fonte de preço sem tocar nos modelos |
| `SessaoHttp` (Protocol) | `requests.Session` (`criar_sessao`) e `SessaoFalsa` (testes) | `http.baixar`, `BrapiProvider`, `macro` | Testar tudo **sem rede** |
| Linha de comando `valuation` | `cli` | O investidor | Única interface com o usuário (sem GUI nem servidor) |

### Notas

- **Dependências de terceiros** conforme `pyproject.toml` (Python 3.11 a 3.13, fixado em 3.12 por `.python-version`; gerenciador `uv`). `python-bcb` está declarada, mas a SGS e a Focus são consultadas por REST direto (`data/macro.py`). `yfinance` é importada **dentro** da função (`_baixar`); `openpyxl`, só na importação de XLSX.
- **Substituibilidade**: os parquets de `data/processed/` são derivados e podem ser apagados (`atualizar --forcar` os recria); `data/raw/` é cache. O que **não** se recria sozinho: `perfil/perfil_investidor.json` (refazer o questionário), `config/` (versionado) e `carteira/transacoes.csv` (histórico pessoal, fora do git).
- **Sem segredos**: nenhuma chave é necessária. `BRAPI_TOKEN` (variável de ambiente, opcional) amplia só a fonte alternativa de preço.
- Pastas `data/`, `saida/`, `perfil/` e `carteira/` ficam no `.gitignore`.

## 3. Ambiente de hardware — diagrama de implantação

Uso **pessoal e local**: um único nó, a máquina Linux do investidor, que faz requisições HTTPS de saída para fontes públicas e gratuitas. Nada é exposto, e nenhum sistema externo chama o Lastro.

```mermaid
flowchart LR
    subgraph PC["«nó: dispositivo» Máquina do investidor (Linux)"]
        direction TB
        subgraph PY["«ambiente de execução» Python 3.12 (.venv gerenciado pelo uv)"]
            a_exe["«artefato»<br/>valuation<br/>(pacote src/valuation + entry point)"]
            a_dep["«artefato»<br/>bibliotecas de terceiros<br/>(uv.lock)"]
        end
        subgraph FSL["«ambiente de execução» Sistema de arquivos do projeto"]
            a_cfg["«artefato»<br/>config/*.yaml, *.csv<br/>(versionado no git)"]
            a_data["«artefato»<br/>data/raw e data/processed<br/>(cache e parquets; fora do git)"]
            a_priv["«artefato»<br/>perfil/ e carteira/<br/>(dados pessoais; fora do git)"]
            a_out["«artefato»<br/>saida/TICKER/AAAA-MM-DD/<br/>(resultados; fora do git)"]
        end
        term["«artefato»<br/>terminal<br/>(zsh, bash...)"]
    end

    subgraph NET["Internet (somente HTTPS de saída, GET)"]
        direction TB
        n_cvm["«nó: servidor»<br/>dados.cvm.gov.br<br/>cadastro, DFP, ITR, FCA"]
        n_bcb["«nó: servidor»<br/>api.bcb.gov.br<br/>olinda.bcb.gov.br<br/>SGS e Expectativas Focus"]
        n_tes["«nó: servidor»<br/>www.tesourotransparente.gov.br<br/>taxas do Tesouro"]
        n_yf["«nó: servidor»<br/>Yahoo Finance<br/>(via biblioteca yfinance)"]
        n_br["«nó: servidor»<br/>brapi.dev<br/>(fonte alternativa de preço)"]
    end

    term -->|"valuation ..."| a_exe
    a_exe --- a_dep
    a_exe -.->|"lê"| a_cfg
    a_exe -.->|"lê e grava"| a_data
    a_exe -.->|"lê e grava"| a_priv
    a_exe -.->|"grava"| a_out

    a_exe -->|"HTTPS GET, cache e TTL"| n_cvm
    a_exe -->|"HTTPS GET"| n_bcb
    a_exe -->|"HTTPS GET"| n_tes
    a_exe -->|"HTTPS"| n_yf
    a_exe -->|"HTTPS GET, token opcional"| n_br

    classDef art fill:#eef2ff,stroke:#5c7cfa,color:#1a1a1a
    classDef srv fill:#e9ecef,stroke:#868e96,color:#1a1a1a
    class a_exe,a_dep,a_cfg,a_data,a_priv,a_out,term art
    class n_cvm,n_bcb,n_tes,n_yf,n_br srv
    style PC fill:#fafafa,stroke:#adb5bd,color:#1a1a1a
    style PY fill:#ffffff,stroke:#adb5bd,color:#1a1a1a
    style FSL fill:#ffffff,stroke:#adb5bd,color:#1a1a1a
    style NET fill:#fafafa,stroke:#adb5bd,color:#1a1a1a
```

Efeitos da implantação sobre o projeto:

- **Disponibilidade das fontes**: toda chamada passa por `http.baixar` ou por um provedor, com cache, retry e *fallback* para a cópia vencida; sem rede, o que está no TTL continua funcionando. A validação cruzada de preço e macro (ADR 0004) usa duas fontes independentes quando existem.
- **Frescor**: TTL padrão de 168 h para CVM e cadastro, e de 12 h para preços e macro (`settings.cache_ttl_horas`).
- **Privacidade**: o perfil e a carteira nunca saem da máquina, e nenhum dado pessoal é enviado às fontes (só tickers e datas nas requisições).
- **Reprodutibilidade**: o `meta.json` de cada execução guarda commit do código, perfil, moeda e sha256 e data de cada fonte da CVM, então a rodada pode ser reconstruída a partir de `data/raw/` e `premissas_usadas.yaml`.

## 4. Arquitetura e casos de uso

Os [casos de uso](diagrama_casos_de_uso.md) dizem **o que** o sistema faz; esta arquitetura diz **com que forma**. Os requisitos não funcionais que mais moldaram a estrutura:

| Requisito | Decisão de arquitetura |
|---|---|
| Fontes gratuitas e instáveis | Adaptadores em `data/` com `PrecosProvider`, cache em disco, `.meta.json`, retry e validação cruzada |
| Resultado reproduzível e testável | Motor de funções puras sobre dataclasses `frozen`; `data_base` e `agora` por parâmetro; sessão HTTP injetável |
| Uma empresa por execução, base para todas | `rodar` orquestra uma empresa; `rodar-setor` e `favoritos atualizar` só repetem o `rodar` |
| Dois tipos de empresa (não financeira e financeira) | Mesmo esqueleto (contábil → projeção → modelo → cenários), com `dcf` ou `ddm` plugado por `tipo_modelo` |
| Perfil não muda fatos | `perfil` isolado, consumido só em `analise` (pesos e margem) e na escolha do horizonte |
| Uso pessoal, local, sem segredos | Um executável, arquivos locais, nenhuma chave obrigatória |
