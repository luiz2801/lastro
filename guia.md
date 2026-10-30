# guia.md — Mapa do código para quem vai modificá-lo

**Versão 1.5 — 2026-10-30**

> Complementa o `CLAUDE.md` (especificação e roadmap). Este arquivo descreve **o que existe hoje**
> (Fases 0 a 6 implementadas) para que você não precise reler os módulos. Para o que ainda
> **não** existe, veja a seção 12.
> Política de commits, que documento atualizar em cada mudança e ADRs: `CONTRIBUTING.md` e
> `docs/decisoes/README.md`.

> ## Regra de manutenção (obrigatória)
>
> **Antes de modificar:** leia deste guia a seção do módulo que vai mexer (e as seções 13 e 16,
> convenções e armadilhas). Só abra o código-fonte para o que o guia não responder. Planeje a
> alteração a partir daqui.
>
> **Ao modificar:** toda alteração de lógica, contrato, parâmetro, arquivo ou comando precisa ser
> refletida neste guia **na mesma entrega (mesmo commit)**: função nova/removida/renomeada,
> fórmula ou critério trocado, parâmetro de `settings.yaml` que passou a ser lido (tire o ⏳),
> fase concluída (atualize as seções 1 e 12), armadilha descoberta (seção 16).
>
> **Versão (no topo):** typo sem mudança de comportamento → não muda; mudança de comportamento,
> contrato ou arquivo → *minor* (1.1, 1.2…); mudança que invalida dados já gravados em `data/` ou
> o esquema dos parquets → *major* (2.0…).
>
> **Este guia é uma foto do estado atual, não guarda história.** O que mudou, quando e por quê vai
> para o `CHANGELOG.md`, nunca para aqui.
>
> **Se código e guia discordarem, o código é a verdade e o guia está com defeito:** conserte-o no
> mesmo commit em que perceber.

## 1. Estado em uma olhada

| Camada | Pacote | Estado |
|---|---|---|
| Config | `config.py` | ✅ pronto |
| Dados | `data/{http,cvm,cadastro,validacao,precos,macro}.py` | ✅ prontos |
| Contábil | `contabil/{padronizacao,periodos,moeda,qa,nao_financeiras}.py` + `config/mapeamento_contas.yaml` | ✅ prontos (só plano `nao_financeira`) |
| Perfil | `perfil/{questionario,pontuacao,registro,parametros}.py` | ✅ prontos (seção 17) |
| Projeção | `projecao/{premissas,sugestor,projetor,escrita}.py` + `config/empresas/*.yaml` + `config/setores.yaml` | ✅ prontos (seção 18) |
| Custo de capital | `custo_capital/{beta,capm,kd,wacc}.py` | ✅ prontos (seção 19); beta por comparáveis e estrutura do setor esperam os pares (Fase 8) |
| Saída | `saida/csv.py` | só a gravação de CSV (seção 19); gráficos e demais arquivos na Fase 9 |
| CLI | `cli.py` | `versao`, `cadastro buscar`, `atualizar`, `mercado`, `qa`, `historico`, `cobertura`, `perfil`, `premissas sugerir`, `wacc` |
| `modelos`, `analise` | `__init__.py` de 1 linha | ❌ vazios (Fases 7–10) |

~5.900 linhas de código, 368 testes (11 golden pulados por motivo declarado), mypy `strict`,
ruff (linha 100).

Comandos: `make lint tipos testes` (tudo passa), `make cobertura`, `uv run valuation --help`.
Teste focado: `uv run pytest tests/test_cvm.py -k escala -q`.

## 2. Fluxo de dados

```
settings.yaml ──► config.carregar_settings() ──► Settings (pydantic, frozen, extra=forbid)
                                                     │
cad_cia_aberta.csv ┐                                 │
FCA (ano, ano-1)   ├─► cadastro.atualizar_cadastro ──┼─► data/processed/cadastro.parquet
cadastro_manual.csv┘        (1 linha por TICKER)     │        │
                                                     │        ▼
                                                     │   cadastro.empresa_por_ticker ► Empresa
DFP {ano-10..ano}  ┐                                 │        │
ITR {ano-1, ano}   ├─► cvm.coletar ──────────────────┘        │ (cnpj, cd_cvm, escala_acoes)
                   ┘   data/processed/cvm/{cd_cvm}/            │
                       ├ demonstracoes.parquet  (tabela longa, valor em UNIDADES)
                       └ composicao_capital.parquet (qtd. ações, escala corrigida)
                                                              │
yfinance ─► YFinanceProvider ┐                                │
brapi ────► BrapiProvider    ├─► precos.preco_validado ──► Validado (preço por classe, ^BVSP)
                             ┘                                │
SGS/Focus/Tesouro ─► macro.carregar_macro ──► Macro (Selic, IPCA12m, dólar, Rf, Focus)
                                                              │
composicao_capital.parquet + preços ─► precos.market_cap ──► MarketCap

demonstracoes.parquet ─► padronizacao.selecionar_reapresentacoes (1 documento por período)
                     ─► padronizacao.padronizar(plano de mapeamento_contas.yaml)
                     ─► contas_padronizadas.parquet (tabela longa por conta padrão)
                          ├─► periodos.{anual, acumulado_no_ano, trimestral, ltm, saldos} (largas)
                          │      └─► nao_financeiras.metricas / metricas_ltm ► EBITDA, FCFF, ROIC…
                          └─► qa.verificar ► ResultadoQA ► data/processed/qa/qa_{TICKER}.json

config/empresas/{TICKER}.yaml ─► premissas.carregar_premissas ► PremissasEmpresa (ajustes → métricas)
métricas anuais (exercícios < data-base) ─► sugestor.sugerir ► Sugestoes (valor + origem)
PremissasEmpresa + Sugestoes + horizonte ─► projetor.resolver ► PremissasResolvidas
                                         ─► projetor.aplicar_cenario (deltas) ─► projetor.projetar
                                            ► DataFrame ano a ano (receita … FCFF, fração do ano)

preços adj_close (classe mais líquida, ^BVSP) ─► beta.regressao ► ResultadoBeta
Macro.rf_brl + ERP (+ CRP, Fisher) ─► capm.custo_capital_proprio ► CustoCapitalProprio
DRE despesas_financeiras + métricas divida_bruta ─► kd.historico ► ResultadoKd
MarketCap + divida_bruta do último balanço ─► wacc.estrutura ─► wacc.montar ► CustoCapital
                                                            └─► wacc.tabela ─► saida/{T}/{data}/wacc.csv
```

Todo download passa por `http.baixar` (cache em `data/raw/` + `.meta.json`). Camada superior nunca
é importada por inferior: `data` não importa `cli`; `macro` não conhece provedores de preço
(o câmbio alternativo entra por parâmetro); `precos` importa `cadastro.Empresa` e `validacao`.
`contabil` não importa nada de `data`: lê `demonstracoes.parquet` pelo caminho
(`padronizacao.ler_demonstracoes`) e só importa `config`.

## 3. Comandos da CLI (`cli.py`)

Callback global: `-v/--verbose` → logging DEBUG. Erros: `_erro()` imprime em vermelho e devolve
`typer.Exit(1)`. Funções auxiliares: `_carregar_cadastro(settings, data_base, forcar)` (chama
`cad.atualizar_cadastro` com TTL de `cache_ttl_horas.cvm`), `_tickers_do_universo(caminho)`,
`_linha_validada(v, formato)` (cor por status), `_padronizar(ticker, settings) -> _Padronizada`
(cadastro → YAML da empresa em `DIR_EMPRESAS`, se existir, conferido contra o cadastro; senão
`premissas_padrao` → `carregar_mapeamento(extra=mapeamento_extra)` → `ler_demonstracoes` →
`selecionar_reapresentacoes(consolidado=…)` → `detectar_moeda(…, moeda_relatorio)` → `padronizar`
→ grava `contas_padronizadas.parquet`; só `nao_financeira`, outro tipo ⇒ `ErroContabil`).
`_Padronizada.ajustes` = `AjustesContabeis` do YAML (usado por `historico` e `premissas`).
`_setor(chave)` (chave ausente de `setores.yaml` ⇒ `ErroConfiguracao`), `_horizonte(premissas,
settings, hoje, override)` (inteiro do YAML ou horizonte do perfil via `resolver_perfil`).
`_mercado(ticker, settings, base, agora, forcar) -> _Mercado(empresa, precos, ibov, macro, cap, yf)`
(coleta comum a `mercado` e `wacc`; `.avisos`). `_custo_capital(p, m, settings, base) ->
wc.CustoCapital` (seção 19; reaproveitar no `rodar`), com `_beta` (precedência YAML > settings) e
`_data_balanco` (última data ≤ data-base com YTD e balanço; aviso acima de
`DEFASAGEM_AVISO_DIAS = 140`).

| Comando | Parâmetros | O que faz | Efeito de cada parâmetro |
|---|---|---|---|
| `versao` | — | Imprime versão e Python | — |
| `cadastro buscar TEXTO` | `--forcar` | Busca por ticker/razão/nome/CNPJ no cadastro | `--forcar` ignora TTL e rebaixa cadastro+FCA |
| `atualizar` | `--tickers A,B` ou `--tudo`; `--forcar` | Baixa DFP/ITR/composição e grava parquets por companhia | exatamente um de `--tickers`/`--tudo`. `--tudo` lê `config/universo_ibovespa.csv` (**arquivo ainda não existe**, dá `ErroConfiguracao`). Holding/não suportada: só avisa e baixa |
| `mercado TICKER` | `--data-base AAAA-MM-DD`; `--forcar` | Preço por classe, Ibovespa, dólar, Selic, IPCA, Rf e market cap, cada um em 2 fontes | `--data-base` sobrescreve `settings.data_base`. Exige `atualizar` antes (lê `composicao_capital.parquet`; senão mensagem pedindo o comando) |
| `qa TICKER` | — | Padroniza, roda o QA, imprime verificações, cobertura e contas não mapeadas relevantes; grava `data/processed/qa/qa_{TICKER}.json` | **Sai com 1 se houver erro de QA.** Exige `atualizar` antes |
| `historico TICKER` | `--anos N` (5); `--trimestral` | Métricas anuais (R$ mi) + coluna LTM | `--anos` = quantos exercícios; `--trimestral` mostra os 8 últimos trimestres (receita, EBITDA, lucro, D&A, capex, dividendos) |
| `cobertura` | `--tickers A,B` ou `--tudo` | Matriz conta crítica × ticker com a fração dos exercícios mapeados (verde ≥ 95%) | igual a `atualizar` |
| `premissas sugerir TICKER` | `--escrever`; `--perfil P`; `--data-base AAAA-MM-DD` | Sugere as premissas a partir dos exercícios encerrados antes da data-base e imprime "premissas sugeridas × histórico" (último ano, medianas 5a/10a, sugerido, valor no YAML), CAGR 3/5/10a, deltas dos cenários e a **projeção base** (R$ mi). Avisos: setor de commodity, setor não definido, ano-ponte sem DFP, histórico curto | `--escrever` regenera `config/empresas/{TICKER}.yaml` comentado (anterior em `.yaml.bak`; sem ele, só avisa que o YAML não existe). `--perfil` só define o horizonte quando o YAML usa `horizonte_anos: perfil`; sem perfil válido nem `--perfil`, mostra as sugestões e pula a projeção (sai com 0). `--data-base` corta o histórico e define a fração do ano corrente. Exige `atualizar` antes |
| `wacc TICKER` | `--data-base AAAA-MM-DD`; `--forcar`; `--saida DIR`; `--formato-csv br\|intl` | Beta, Ke, Kd, estrutura e WACC na moeda de reporte; tabela no terminal e `{saida}/{TICKER}/{data-base}/wacc.csv` (`componente;valor;detalhe`, avisos em linhas `aviso`) | `--saida` muda a raiz (padrão `saida/`); `intl` grava `,`/`.`/utf-8. **WACC ≤ g terminal ⇒ sai com 1.** Exige `atualizar` antes; consulta preços e macro como `mercado` |
| `perfil` | `--mostrar` ou `--refazer` | Sem perfil (ou vencido): roda o questionário (resposta = número da alternativa; inválida ⇒ pergunta de novo), grava `CAMINHO_PERFIL` e mostra perfil + parâmetros. Com perfil válido: só mostra | `--mostrar` só mostra (sem perfil ⇒ sai com 1); `--refazer` responde de novo mesmo válido e aceita JSON corrompido (sem ele, JSON inválido ⇒ sai com 1). Os dois juntos ⇒ erro. Validade conferida contra `date.today()`, **não** contra `data_base` |

Observação: `mercado` usa `settings.custo_capital.rf_brl.override` como Rf manual **independentemente
de `rf_brl.fonte`** (a regra `fonte=manual ⇒ override` está só no validador pydantic).

Para adicionar um comando: função `@app.command()` em `cli.py`, capturar
`(ErroConfiguracao, ErroDownload, cad.ErroCadastro, ErroDadosExternos, ErroContabil, ...)` → `raise _erro(str(e)) from e`,
e testar com `typer.testing.CliRunner` em `tests/test_cli.py`.

## 4. `config.py`

Constantes de caminho (relativas à raiz do repo): `DIR_CONFIG`, `CAMINHO_SETTINGS`,
`CAMINHO_CADASTRO_MANUAL`, `CAMINHO_UNIVERSO`, `CAMINHO_SETORES` (`config/setores.yaml`),
`DIR_EMPRESAS` (`config/empresas/`), `DIR_RAW` (`data/raw`), `DIR_PROCESSED` (`data/processed`),
`CAMINHO_PERFIL` (`perfil/perfil_investidor.json`, gitignored), `DIR_SAIDA` (`saida/`, gitignored).

`ler_yaml(caminho)` (mapeamento no topo; ausente, YAML inválido ou outro tipo ⇒
`ErroConfiguracao`) é a leitura comum a settings, setores e YAML da empresa.
`carregar_setores(caminho=CAMINHO_SETORES) -> dict[str, Setor]`; `Setor(descricao, tipo_modelo,
commodity, pares=())`. Hoje: `petroleo_gas` e `mineracao` (commodity) e `maquinas_equipamentos`;
`pares` vazios até a Fase 8.

`Settings` (todos os submodelos herdam `_Modelo`: `extra="forbid"`, `frozen=True` → **campo novo no
YAML exige campo novo na classe, e vice-versa**, senão `ErroConfiguracao`).
`carregar_settings(caminho=CAMINHO_SETTINGS)`; `Settings.resolver_data_base(hoje)` devolve `hoje`
se `data_base: hoje`, senão a data do YAML (**quem chama passa `hoje`**; nunca `date.today()` aqui).

### Parâmetros de `settings.yaml` e impacto

Marcados ⏳ ainda **não são lidos por nenhum código** (reservados para fases futuras), mas já são
validados.

| Chave | Valor atual | Impacto |
|---|---|---|
| `data_base` | `hoje` | Data da avaliação. Define ano dos arquivos CVM/FCA a baixar, data do preço/macro e corte de ações |
| `historico_anos` | 10 | `cvm.anos_a_coletar`: DFP de `ano-10` até `ano` (11 zips). Aumentar ⇒ mais downloads (DFP < 2010 não existe). No QA, janela de `anos_faltantes` |
| `moeda_saida` | BRL | ⏳ |
| `csv.*` | `;` `,` `utf-8-sig` | Formato `br` de `saida.csv.gravar_csv` (`wacc.csv`) |
| `cache_ttl_horas.cvm/precos/macro` | 168 / 12 / 12 | TTL do cache de CVM+cadastro / preços yfinance / macro. Dentro do TTL não há rede |
| `impostos.aliquota_nominal` | 0.34 | Teto da alíquota operacional do NOPAT histórico (`nao_financeiras.metricas`, via `historico`); alíquota usada quando LAIR ≤ 0. Limite da alíquota projetada quando `aliquota_imposto.limite_superior` do YAML é `null` |
| `custo_capital.rf_brl.override` | null | Se numérico, `carregar_macro` não consulta Tesouro e marca Rf como `manual` |
| `custo_capital.metodo` | brl_direto | Método do Ke; empresa que reporta em USD usa `usd_crp` de qualquer forma (aviso) |
| `custo_capital.erp` | 0.05 | Prêmio de risco de mercado no Ke (os dois métodos) |
| `custo_capital.crp`, `rf_usd`, `inflacao_usd_lp` | 0 / 0.04 / 0.02 | Só `usd_crp`: Ke_USD = rf_usd + β × ERP + CRP; Fisher com `inflacao_usd_lp`. `rf_usd` também é a Rf do limite do Kd de quem reporta em USD |
| `custo_capital.beta.metodo` | regressao | Método quando o YAML da empresa **não** declara `custo_capital.beta` |
| `custo_capital.beta.janela_semanas` | 260 | Semanas da regressão e da escolha da classe mais líquida; < 52 disponíveis ⇒ erro |
| `custo_capital.beta.ajuste_blume` | true | Beta do Ke = 0,67 β + 0,33 |
| `custo_capital.beta.min_r2_aviso` | 0.10 | R² abaixo ⇒ aviso |
| `custo_capital.kd.spread_min/spread_max` | 0 / 0.05 | Kd histórico limitado a [Rf + min, Rf + max] (ADR 0007); fora ⇒ limite + aviso |
| `custo_capital.estrutura_alvo.metodo` | mercado_atual | `mercado_atual` = D/(D+E) de hoje; `manual` usa `divida_sobre_capital` e realavanca o beta da regressão; `setor` ⇒ erro até a Fase 8 |
| `custo_capital.estrutura_alvo.divida_sobre_capital` | null | D/(D+E) alvo, obrigatório com `manual` |
| `terminal.g_nominal_max` | 0.045 | g terminal quando o YAML da empresa tem `g_nominal: null`: fim da trajetória de crescimento sugerida (`projetor.g_terminal`). `g_nominal` do YAML acima dele ⇒ `ErroProjecao` |
| `terminal.*` (resto), `dcf.*`, `sensibilidade.*` | — | ⏳ (Fase 7) |
| `validacao_cruzada.preco_rel` | 0.02 | Tolerância relativa de preço (principal × alternativa) |
| `validacao_cruzada.cambio_rel` | 0.015 | Idem dólar (PTAX × `BRL=X`) |
| `validacao_cruzada.market_cap_rel` | 0.10 | ⏳ (declarado, sem uso) |
| `validacao_cruzada.selic_abs` | 0.003 | Diferença absoluta máx. Selic meta × diária anualizada |
| `validacao_cruzada.ipca_abs` | 0.0005 | Idem IPCA 12m (direto × composto) |
| `validacao_cruzada.rf_abs` | 0.025 | Idem Rf (NTN-F × NTN-B+Focus). Apertar gera aviso permanente (spread de inflação ≈ 3 p.p.) |
| `perfil.{conservador,moderado,arrojado}.margem_seguranca` | 0.30 / 0.20 / 0.10 | `parametros_do_perfil` (seção 17); exibido em `valuation perfil`. Uso no preço máximo de compra: Fase 7 |
| `perfil.*.pesos_cenarios.{pessimista,base,otimista}` | 40/50/10, 25/50/25, 15/50/35 % | Idem; validador exige soma 1. Ponderação dos cenários: Fase 7 |
| `perfil.*.horizonte_anos` | 5 / 7 / 10 | Idem; horizonte explícito da projeção quando o YAML tem `horizonte_anos: perfil` (`cli._horizonte`) |
| `perfil.*.hurdle_spread_selic` | 0.03 / 0.05 / 0.07 | `ParametrosPerfil.hurdle(selic)` = Selic + spread. Comparação com o retorno esperado: Fase 7 |

Todos os números de mercado do YAML são **PLACEHOLDER** (regra do projeto: nunca inventar dado).

## 5. `data/http.py` — download com cache

| Símbolo | Papel |
|---|---|
| `baixar(url, destino, *, ttl, sessao, agora, forcar=False, validar=None) -> ArquivoBaixado` | Ponto único de download. Fluxo: (1) meta existe e `agora - verificado_em < ttl` e não `forcar` ⇒ cache sem rede; (2) senão GET, com `If-Modified-Since` se houver `last_modified` e não `forcar`; (3) 304 ⇒ mantém arquivo, atualiza só `verificado_em`; (4) 200 ⇒ grava em `.parcial`, roda `validar(temp)`, `os.replace`, grava meta; (5) falha de rede/HTTP com cópia antiga e sem `forcar` ⇒ usa a cópia com warning; 404 **sempre** propaga `ArquivoNaoEncontrado` |
| `criar_sessao(tentativas=4)` | `requests.Session` com retry exponencial (429/5xx, só GET) e User-Agent `valuation/<versão>` |
| `MetaDownload` / `ArquivoBaixado(caminho, meta, do_cache)` | Metadados (`url, baixado_em, verificado_em, sha256, tamanho_bytes, last_modified`) |
| `ler_meta`, `caminho_meta` | `<arquivo>.meta.json`; meta corrompido ⇒ `None` (rebaixa) |
| `SessaoHttp` (Protocol) | `get(url, *, headers, timeout, stream)`. Nos testes use `SessaoFalsa` |
| `ErroDownload`, `ArquivoNaoEncontrado` | Exceções |

Parâmetros que mudam o comportamento: `ttl` (frescor), `forcar` (ignora cache **e** desabilita o
fallback para cópia vencida: falha propaga), `validar` (evita gravar HTML de erro como se fosse zip).
`TIMEOUT_SEGUNDOS=60`, bloco de 1 MiB.

## 6. `data/cvm.py` — DFP, ITR, composição do capital

Constantes: `URL_BASE`, `DEMONSTRACOES` (BPA, BPP, DRE, DFC_MD, DFC_MI, DVA, DMPL, DRA),
`FATOR_ESCALA = {MIL: 1000, UNIDADE: 1}`, `COLUNAS_DEMONSTRACOES`, `COLUNAS_ACOES`.

| Função | O que faz | Detalhe que costuma morder |
|---|---|---|
| `url_documento(tipo, ano)`, `url_cadastro()`, `url_fca(ano)` | Montam URLs | — |
| `nome_csv_demonstracao(tipo, dem, consolidado, ano)`, `nome_csv_composicao` | Nome do CSV dentro do zip | sufixo `con`/`ind` |
| `validar_zip(caminho)` | `ErroDownload` se não for zip | usado como `validar=` |
| `ler_csv(origem, membro=None)` | CSV `latin-1`, `;`, tudo `str`, `QUOTE_NONE`, sem NA. `None` se o membro não existe no zip | **Nunca** troque `QUOTE_NONE`: há aspas literais em `DS_CONTA` |
| `normalizar_cd_cvm(serie)` | `"009512"` → `9512` (int64) | cadastro não tem zeros à esquerda, DFP tem |
| `_manter_maior_versao(df, chaves)` | Mantém só a maior `versao` por chave | chaves em DFP/ITR: `cnpj, dt_refer, demonstracao, consolidado` |
| `_converter_demonstracao(...)` | CSV bruto → colunas padrão; `valor = VL_CONTA × FATOR_ESCALA[ESCALA_MOEDA]` | escala desconhecida ⇒ `ErroDadosCVM`. BPA/BPP não têm `DT_INI_EXERC` (`dt_ini = NaT`) |
| `ler_demonstracoes(zip, tipo, ano, cnpjs, demonstracoes=…)` | Lê todas as demonstrações (con e ind) dos `cnpjs` | arquivo ausente ⇒ warning, segue |
| `ler_composicao_capital(zip, tipo, ano, cnpjs)` | Qtd. de ações como publicada (sem escala) | DFP < 2020 não tem o arquivo ⇒ DF vazio |
| `corrigir_escala_acoes(acoes, escala_base)` | Multiplica por `escala_base` (1 ou 1000, do cadastro manual); depois datas com 500×–2000× menos ações que a mais recente ganham ×1000 (com warning). Grava `escala_acoes_aplicada` | Desdobramentos reais (2:1, 10:1) não caem na faixa. Ver ADR 0003 |
| `anos_a_coletar(ano_base, historico_anos)` | `{"DFP": [ano-N..ano], "ITR": [ano-1, ano]}` | — |
| `coletar(alvos, anos, *, dir_raw, dir_processed, ttl, sessao, agora, forcar)` | Orquestra: baixa zips → lê → separa por companhia → grava 2 parquets. 404 só é tolerado no **ano mais recente** de cada tipo (resumo `anos_indisponiveis`) | CD_CVM divergente do cadastro ⇒ `ErroDadosCVM` |
| `AlvoCVM(cnpj, cd_cvm, escala_acoes=1)`, `ResumoColeta` | Entrada/saída de `coletar` | — |

**Esquema de `demonstracoes.parquet`** (tabela longa): `cnpj, cd_cvm, denom_cia, fonte (DFP|ITR),
dt_refer, versao, demonstracao, consolidado (bool), moeda, escala_moeda, ordem_exerc, dt_ini, dt_fim,
coluna_df, cd_conta, ds_conta, valor, st_conta_fixa, arquivo`.
**Nenhuma escolha entre exercícios/reapresentações é feita aqui** — a regra "valor da demonstração
mais recente, inclusive como PENÚLTIMO" é trabalho da Fase 2 (`contabil`).

## 7. `data/cadastro.py` — ticker ↔ CNPJ ↔ CD_CVM

Cadeia: ticker →(FCA `valor_mobiliario`)→ CNPJ →(`cad_cia_aberta.csv`)→ CD_CVM.

| Símbolo | Papel |
|---|---|
| `TipoModelo` = `nao_financeira \| financeira \| holding \| nao_suportada`; `Especie` = `ON \| PN \| UNIT` | Literais |
| `SETORES_FINANCEIROS`, `SETORES_NAO_SUPORTADOS`, `PREFIXO_HOLDING` | Entram em `classificar_tipo_modelo(setor_cvm)`. **Holding não é detectável pelo setor** (WEG é "Emp. Adm. Part."): só via `cadastro_manual.csv` |
| `normalizar_ticker` | upper, tira `.SA` |
| `ler_cadastro_cvm(caminho)` | 1 linha por CNPJ, preferindo `SIT == ATIVO` e `DT_INI_SIT` mais recente |
| `ler_valores_mobiliarios(zips_fca, data_ref)` | Tickers ON/PN/UNIT em Bolsa; só o FCA (data+versão) mais recente por CNPJ; descarta lixo (`NÃO HÁ`, numéricos), regex `RE_TICKER`, e negociação encerrada antes de `data_ref`; duplicados ⇒ warning, fica o primeiro |
| `ler_cadastro_manual(caminho)` | `ticker;cnpj;especie;tipo_modelo;escala_acoes;observacao`; valida valores; `#` comenta; campo vazio não sobrescreve |
| `montar_cadastro(cvm, vm, manual)` | Junta; manual **sobrescreve** `especie`, `tipo_modelo`, `escala_acoes`; ticker só no manual exige `cnpj` e `especie`; CNPJ manual ≠ FCA ⇒ erro; ticker sem CD_CVM ⇒ descartado com warning |
| `buscar(cadastro, texto)` | Contém, sem acento/caixa, em ticker+razão+nome; ≥ 4 dígitos também casam CNPJ |
| `empresa_por_ticker(cadastro, ticker) -> Empresa` | Agrupa as classes do mesmo CNPJ. `tipo_modelo`/`escala_acoes` divergentes entre classes ⇒ `ErroCadastro` (corrija o manual) |
| `atualizar_cadastro(*, ano, data_ref, dir_raw, dir_processed, caminho_manual, ttl, sessao, agora, forcar)` | Baixa cadastro + FCA de `ano-1` e `ano` (FCA do ano corrente pode dar 404 ⇒ ignorado), monta e grava `cadastro.parquet` |

`Empresa(cnpj, cd_cvm, razao_social, nome_comercial, setor_cvm, tipo_modelo, escala_acoes, classes)`
com `.tickers`. `ClasseAcao(ticker, especie)`.

**Receitas de modificação**
- Reclassificar uma empresa (holding, financeira, escala de ações) ⇒ **editar
  `config/cadastro_manual.csv`**, não o código.
- Novo setor financeiro/não suportado ⇒ frozenset no topo de `cadastro.py` + teste em `test_cadastro.py`.

## 8. `data/validacao.py` — validação cruzada

`Leitura(valor, fonte, data)` → `cruzar(nome, principal, alternativa, *, tolerancia, relativa=False)
-> Validado`.

| Situação | `status` | Valor usado |
|---|---|---|
| Ambas respondem, divergência ≤ tolerância | `ok` | principal |
| Ambas respondem, divergência > tolerância | `divergente` (+ warning, `Validado.aviso`) | **principal** (alternativa só confere) |
| Só uma responde | `sem_validacao` (+ warning) | a que respondeu |
| Nenhuma | `ErroDadosExternos` | — |
| `manual(nome, valor)` | `manual` | valor do settings |

`relativa=True` ⇒ `|a−b|/|a|` (preço, câmbio); senão diferença absoluta (taxas em decimal).
Divergência **não interrompe**; sobe como aviso. A decisão de política está no
`docs/decisoes/0004-validacao-cruzada-de-apis.md`.

## 9. `data/precos.py` — preços e market cap

| Símbolo | Papel |
|---|---|
| `PrecosProvider` (Protocol) | `nome`, `historico(simbolo, inicio, fim)` (índice data, colunas `close, adj_close, volume`), `cotacao(simbolo)` |
| `simbolo_yahoo(ticker)` | `PETR4`→`PETR4.SA`; `^BVSP`, `BRL=X` ficam |
| `YFinanceProvider(dir_cache, ttl, agora, *, forcar, tentativas=3, espera=time.sleep)` | `auto_adjust=False`; remove fuso; 3 tentativas com espera `2**n`; cache parquet `yf_<símbolo>_<ini>_<fim>.parquet` + meta em `data/raw/precos/`; falha ⇒ cópia vencida (se não `forcar`). **Injete `espera=lambda s: None` nos testes** |
| `BrapiProvider(sessao, token=None)` | Token de `BRAPI_TOKEN`. Sem token só PETR4/VALE3/MGLU3/ITUB4 (401 nos demais ⇒ `ErroPrecos`). Histórico via `range=Ny` (não validado sem token) |
| `fechamento_ate(hist, data_base)` | Último `close` (**não ajustado**) ≤ data_base |
| `preco_validado(ticker, data_base, principal, alternativo, *, tolerancia_rel, janela_dias=15)` | Fecha pelo principal; compara com `alternativo.cotacao` **apenas se** a data dela estiver a ≤ `TOLERANCIA_DIAS_COTACAO=4` dias do fechamento. Falha do alternativo = warning, não erro |
| `market_cap(empresa, composicao, precos, data_base) -> MarketCap` | Última composição com `dt_refer ≤ data_base`. Qtd ON = `ordin_cap_integr − ordin_tesouro`; PN análogo. Preço = ticker cotado da espécie; se faltar, usa o da outra espécie com aviso. **UNITs são ignoradas** (a CVM só separa ON/PN). Soma `ações × preço` |

Regra de projeto: `Close` para market cap; `Adj Close` para retornos (beta, Fase 6).

⚠️ **Pendência conhecida** (de `docs/fontes.md`): o significado de `QT_ACAO_TOTAL_CAP_INTEGR` varia
por companhia (na Vale já exclui tesouraria). `market_cap` usa as colunas ON/PN, não a total, mas
**a subtração da tesouraria por espécie na Vale não foi conferida** contra a composição acionária
da empresa. Verifique antes de confiar no market cap da VALE3.

## 10. `data/macro.py` — macro

Códigos SGS: `SGS_SELIC_META=432`, `SGS_SELIC_DIARIA=11`, `SGS_CDI=12`, `SGS_IPCA_MENSAL=433`,
`SGS_IPCA_12M=13522`, `SGS_DOLAR=1`. Rf: `TITULO_NTNF`, `TITULO_NTNB`, prazo-alvo 10 anos,
aceito 7–13 (`PRAZO_RF_*`), `DIAS_UTEIS_ANO=252`.

| Função | O que faz | Cuidado |
|---|---|---|
| `serie_sgs(codigo, inicio, fim, *, dir_raw, ttl, sessao, agora, forcar)` | `pd.Series` float por data; cache `data/raw/macro/sgs_<cod>_<ini>_<fim>.json` | Resposta vazia ⇒ `ErroDadosExternos` |
| `_ultimo_ate(serie, data_base)` | Último valor ≤ data_base | A Selic meta (432) traz **datas futuras** |
| `focus_anual(indicador, data_base, ...)` | Mediana das expectativas anuais da última reunião ≤ data_base → `(data, {ano: valor})`; `Câmbio` em R$/US$, demais ÷100 | Filtro OData `baseCalculo eq 0`, `$top=40` |
| `carregar_taxas_tesouro(...)` | CSV do Tesouro (`;`, `,`, latin-1) filtrado a NTN-F e NTN-B | CSV de 14 MB **não ordenado por data** |
| `titulo_longo(taxas, tipo, data_base)` | Título mais próximo de 10 anos na última `Data Base` ≤ data_base; fora de 7–13 anos ⇒ erro | usa `Taxa Compra Manha` |
| `carregar_macro(data_base, *, tolerancias, rf_override, cambio_alternativo, dir_raw, ttl, sessao, agora, forcar) -> Macro` | Monta Selic (432×11), IPCA12m (13522×433), dólar (SGS 1 × `cambio_alternativo`), Rf (NTN-F × NTN-B+Focus) e Focus de IPCA. Janela SGS: `data_base − 430 dias` | `_tentar` converte falha de uma fonte em `None` (vira `sem_validacao`); `rf_override` ⇒ Rf `manual` sem tocar no Tesouro |

`Macro(data_base, selic, ipca_12m, cambio, rf_brl, ipca_esperado, data_focus)` + `.avisos`.
`rf_brl` é a **fonte principal para Ke** na Fase 6 (NTN-F, nominal; não somar risco-país por cima).

## 11. `contabil/` — padronização, períodos, QA e métricas

Decisões e porquês: ADR 0005. Exceção da camada: `ErroContabil` (em `contabil/__init__.py`).

### `config/mapeamento_contas.yaml` + `padronizacao.py`

YAML: `nao_financeira: {conta_padrao: [regras]}` e `contas_criticas: {nao_financeira: [...]}`.
Regra (`RegraMapeamento`, pydantic `extra=forbid`): `dem` (`BPA|BPP|DRE|DFC|DVA`; `DFC` casa
`DFC_MI` e `DFC_MD`), `cd` (exato), `cd_prefixo` (só **descendentes**, texto ou lista),
`cd_excluir` (o código e descendentes), `ds_regex`/`ds_excluir` (sobre `DS_CONTA` **minúscula e sem
acento**: escreva `aplicacoes`, não `aplicações`), `sinal` (1/-1). Exige `cd` ou `ds_regex`.

| Símbolo | O que faz | Detalhe que costuma morder |
|---|---|---|
| `carregar_mapeamento(caminho, tipo="nao_financeira", extra=None) -> PlanoContas` | Lê e valida; `extra` (= `mapeamento_extra` da empresa) entra **antes** das regras padrão e pode criar conta | Conta que mistura saldo e fluxo, crítica sem regra, regex inválida ⇒ `ErroConfiguracao` |
| `PlanoContas(tipo, contas, criticas)`, `.eh_saldo(conta)` | — | — |
| `selecionar_reapresentacoes(demonstracoes, *, consolidado=True)` | Filtra consolidado e BPA/BPP/DRE/DFC/DVA; por (`familia`, `dt_ini`, `dt_fim`) fica **um** documento: maior (`dt_refer`, `versao`). DFC_MD sai se o mesmo período tem DFC_MI. Acrescenta a coluna `familia` | É o que corrige o sinal da Vale 2022 (vale o `PENÚLTIMO` da DFP 2023). DMPL/DRA são descartadas |
| `avaliar_regra(selecionadas, regra)` | Valor da regra por período: soma das contas casadas **de nível mais alto** (subconta de outra casada é ignorada), × `sinal` | Usado também pelo QA para comparar regras |
| `padronizar(selecionadas, plano, *, ticker)` | Por conta e período, vence a **primeira regra que casa**. Saída `COLUNAS_PADRONIZADAS` | Conta sem casamento num período simplesmente não aparece (sem NaN) |
| `periodicidade(dt_ini, dt_fim)` | `S` saldo, `A` 12 meses, `T` 3 meses, `YTD` 6/9 meses | 1T (jan–mar) é `T` mas também é o YTD de março |
| `cobertura(contas, criticas)` | Fração dos exercícios (31/12) com cada conta | — |
| `ler_demonstracoes(dir_processed, cd_cvm)`, `caminho_padronizadas(...)` | Caminhos `data/processed/cvm/{cd_cvm}/…` | Arquivo ausente ⇒ `FileNotFoundError` |

**Esquema de `contas_padronizadas.parquet`**: `cd_cvm, ticker, dt_refer, dt_ini, dt_fim,
periodicidade, demonstracao, conta_padrao, valor, moeda, escala_aplicada, versao, fonte_arquivo,
regra` (índice da regra usada), `cd_contas` (códigos somados, `;`). Valores em unidades, sinal da
fonte principal (DRE/DFC como na CVM: despesa e saída negativas; D&A positiva).

Contas padrão hoje (nao_financeira): DRE `receita_liquida, custo_vendas, resultado_bruto,
despesas_operacionais, impairment, equivalencia_patrimonial, ebit, resultado_financeiro,
receitas_financeiras, despesas_financeiras, lair, ir_csll, lucro_operacoes_continuadas,
lucro_liquido, lucro_liquido_controladora, lucro_liquido_minoritarios`; DFC/DVA `da, cfo, capex,
pagamento_arrendamento, dividendos_pagos`; BPA `ativo_total, ativo_circulante, caixa,
aplicacoes_financeiras, contas_a_receber, estoques, ativo_nao_circulante, aplicacoes_financeiras_lp,
investimentos, imobilizado, intangivel`; BPP `passivo_total, passivo_circulante, fornecedores,
emprestimos_cp, arrendamento_cp_em_emprestimos, arrendamento_cp_outros, passivo_nao_circulante,
emprestimos_lp, arrendamento_lp_em_emprestimos, arrendamento_lp_outros, provisoes_lp,
patrimonio_liquido_total, minoritarios`.

### `periodos.py` (visões largas, índice = data ou ano)

Tudo parte do **acumulado no ano** (fluxo com `dt_ini` = 1º/jan do ano de `dt_fim`); o trimestre
isolado da DRE é ignorado. Exercício social jan–dez suposto.

| Função | Saída |
|---|---|
| `saldos(contas)` | Saldos por `dt_fim` |
| `acumulado_no_ano(contas)` | YTD por `dt_fim` (dezembro = exercício) |
| `anual(contas)` | Fluxos jan–dez + saldos 31/12; índice `ano` (int) |
| `trimestral(contas)` | Fluxo do trimestre = YTD − YTD do trimestre anterior do mesmo ano (sem o anterior ⇒ NaN) + saldos |
| `data_mais_recente(contas)` | Última data com YTD **e** balanço |
| `ltm(contas, dt_fim=None) -> Series` | Exercício anterior + YTD − YTD de 1 ano antes (dezembro ⇒ o próprio exercício) + saldos na data; `name` = data. Componente ausente ⇒ `ErroContabil` |

### `moeda.py`

`detectar_moeda(demonstracoes, moeda_relatorio="auto") -> "BRL"|"USD"`: `MOEDAS_CVM` (`REAL→BRL`,
`DOLAR→USD`); mais de uma moeda ou moeda desconhecida ⇒ `ErroContabil`; override ≠ `auto` vence.
`converter_para_brl(valor, moeda, cambio)`: só para o valor final (fluxos e taxa ficam na moeda de
reporte).

### `nao_financeiras.py`

`metricas(largo, *, aliquota_nominal, ajustes=None) -> DataFrame` (linhas consecutivas a 12 meses;
ΔNWC/ROIC da 1ª linha = NaN) e `metricas_ltm(contas, *, aliquota_nominal, dt_fim=None, ajustes=None)
-> Series` (ΔNWC/ROIC contra o balanço de 12 meses antes; sem ele ⇒ `ErroContabil`).
`AjustesContabeis(ifrs16="divida", capex_equivalente_arrendamento=True,
coligadas="somar_investimento_contabil", nao_recorrentes=(), caixa_extra=(), divida_extra=())`,
`NaoRecorrente(ano, valor, descricao)` (ganho positivo, perda negativa; só casa índice inteiro =
visão anual). `caixa_extra`/`divida_extra` são nomes de **contas padrão** (crie a conta com
`mapeamento_extra` se preciso); conta que não existe na tabela ⇒ `ErroContabil`, período sem ela =
0. Contas em `OPCIONAIS` ausentes = 0; demais ausentes ⇒ `ErroContabil`.

| Métrica | Fórmula |
|---|---|
| `ebitda` | EBIT contábil + D&A (= releases) |
| `ebit_ajustado` | EBIT − não recorrentes [− equivalência se `coligadas=somar_investimento_contabil`]; `ebitda_ajustado` = + D&A |
| `aliquota_efetiva` / `aliquota_operacional` | −IR/LAIR (NaN se LAIR ≤ 0) / limitada a [0, nominal], nominal se NaN |
| `nopat` | `ebit_ajustado × (1 − aliquota_operacional)` |
| `capex`, `pagamento_arrendamento`, `dividendos_pagos` | Sinal trocado (positivos = saída) |
| `divida_financeira` | empréstimos CP + LP − arrendamento dentro de empréstimos |
| `arrendamento` (`arrendamento_cp`) | dentro + fora de empréstimos |
| `divida_bruta` | financeira [+ arrendamento se `ifrs16=divida`] |
| `caixa_e_aplicacoes`, `divida_liquida` | caixa + aplicações CP + `caixa_extra`; bruta − caixa |
| `divida_extra` | soma das contas de `divida_extra` (fora da dívida bruta; a ponte subtrai) |
| `nwc`, `delta_nwc` | (AC − caixa − aplic. CP) − (PC − dívida financeira CP − arrendamento CP); `caixa_extra` **não** sai do AC |
| `fcff` | NOPAT + D&A − capex − ΔNWC [− pagamento de arrendamento se `ifrs16=divida` e `capex_equivalente_arrendamento`] |
| `fcf_caixa` | CFO − capex |
| `capital_investido`, `roic` | PL total + dívida líquida; NOPAT / média do capital (NaN se ≤ 0) |

### `qa.py`

`verificar(selecionadas, contas, plano, *, ticker, moeda, historico_anos) -> ResultadoQA`
(`.erros`, `.avisos`, `.para_dict()`, `cobertura`, `nao_mapeadas`), ordenado erro → aviso → info;
`gravar(resultado, caminho)`. Tolerâncias são constantes no topo do módulo (`TOL_*`, `SALTO_ANUAL`,
`LIMIAR_*`).

| Código | Severidade | Regra |
|---|---|---|
| `balanco_fecha` | erro | ativo × (PC + PNC + PL) e × passivo total, > 0,1% |
| `subcontas` | aviso | `1, 1.01, 1.02, 2, 2.01, 2.02` × soma das filhas diretas, > 0,5% |
| `receita_positiva` | erro | receita anual ≤ 0 |
| `ebit_consistente` | erro | EBIT × receita + custo + despesas operacionais, > 0,5% da receita, em todo período de fluxo (pega sinal invertido) |
| `lair_consistente` / `lucro_atribuido` | aviso | LAIR × EBIT + financeiro; LL × controladora + minoritários |
| `da_ausente` | aviso | D&A nula com imobilizado > 20% do ativo |
| `fontes_divergentes` | aviso | Regras alternativas da mesma conta divergem > 5% (hoje: D&A DFC × DVA da Petrobras 2019–2022) |
| `salto_anual` | aviso | receita, ativo, PL ou imobilizado variam > 50% a/a |
| `anos_faltantes` | aviso (erro se nenhum) | exercícios ausentes nos últimos `historico_anos` |
| `conta_critica_ausente` | aviso | crítica sem valor num exercício |
| `escala_varia` | info | `MIL` e `UNIDADE` misturadas (já normalizado) |

`contas_nao_mapeadas`: contas x.yy.zz do último exercício fora do mapeamento (nem ancestral nem
descendente de conta usada com ≥ 2 pontos) com |valor| ≥ 5% do ativo (BPA/BPP, sem PL) ou da
receita (só `3.04.03–05`, candidatas a não recorrente).

## 12. O que NÃO existe ainda (não procure no código)

| Fase | Falta | Dica de onde conectar |
|---|---|---|
| 2 | `contabil/financeiras.py` e seção `financeira:` do mapeamento | Fase 10, após inspecionar ITUB4/BBAS3. `_padronizar` da CLI recusa tipo ≠ `nao_financeira` |
| 7–10 | DCF, DDM, múltiplos, sensibilidade, saídas CSV/PNG (exceto `wacc.csv`) | Parâmetros já validados em `Settings`. O WACC sai de `cli._custo_capital` (`wc.CustoCapital.wacc`, moeda de reporte). Cenários prontos: `resolver_cenarios` + `aplicar_cenario` + `projetar` dão a projeção de cada cenário; a coluna `fracao` diz quanto do FCFF do ano entra no DCF |
| 8 | beta por `comparaveis` e `estrutura_alvo: setor` | `beta.comparaveis(pares, ...)` pronto; falta montar `{ticker: (beta, D/E)}` dos pares em `cli._beta` |
| 7 | uso de `ajustes.minoritarios`, `divida_extra` na ponte, `terminal.ronic` do YAML | métrica `divida_extra` já calculada |
| 8 | `pares` de `setores.yaml` e `pares.incluir/excluir` | listas vazias hoje |
| 9 | `premissas_usadas.yaml` | serializar `PremissasResolvidas` de cada cenário |
| — | `config/universo_ibovespa.csv` | `--tudo` falha sem o universo |
| — | comandos `rodar`, `comparar` | seção 14 do `CLAUDE.md`. `rodar --perfil` ⇒ `cli._horizonte` / `registro.resolver_perfil` e gravar `PerfilEfetivo.origem` no `meta.json` |
| 7 | uso dos parâmetros do perfil (valor ponderado, preço máximo de compra, TIR × hurdle) | `ParametrosPerfil` já pronto (seção 17) |

## 13. Convenções que o código já segue (siga também)

- **Funções puras** recebem `agora`/`data_base` por parâmetro; `date.today()`/`datetime.now()` só na
  CLI (`cli.py`).
- **I/O por injeção**: sessão HTTP (`SessaoHttp`), diretórios (`dir_raw`, `dir_processed`) e
  `espera` são parâmetros nomeados (keyword-only `*`), o que torna tudo testável offline.
- **Dinheiro em unidades da moeda** (escala aplicada na ingestão). Ações em unidades (escala
  corrigida). Taxas em **decimal** (0,1375, não 13,75).
- Exceções em português `ErroX` (N818 ignorado no ruff). Hierarquia: `ErroDownload ⊃
  ArquivoNaoEncontrado`; `ErroDadosExternos ⊃ ErroPrecos`; `ErroCadastro`, `ErroDadosCVM`,
  `ErroConfiguracao`, `ErroContabil`, `ErroPerfil`, `ErroProjecao`, `ErroCustoCapital`.
- Strings e docstrings do código em ASCII para símbolos (`x`, `-`, "desvio-padrão"): o ruff
  (RUF001–003) recusa `×`, `−`, `–` e `σ`. Acentos do português são normais.
- Dataclasses `frozen=True` para objetos trocados entre camadas; pydantic só para configuração.
- Identificadores de domínio em português; mensagens ao usuário em PT-BR.
- Dependência opcional pesada (`yfinance`) é importada **dentro** da função (`_baixar`).
- Não usar `QUOTE_NONE` ⇒ quebra; não reordenar `COLUNAS_*` sem revisar parquets existentes
  (apague `data/processed/` e rode `atualizar --forcar` se mudar esquema).

## 14. Testes

| Arquivo | Cobre | Fixtures |
|---|---|---|
| `test_http.py` | cache, TTL, 304, retry, fallback | `sessao_falsa` |
| `test_cvm.py` | parsing, escala, versões, `coletar` | `zip_cvm("dfp_cia_aberta_2025")` etc. |
| `test_cadastro.py` | FCA, manual, classificação, busca | `tests/fixtures/cvm/*` |
| `test_validacao.py`, `test_precos.py`, `test_macro.py` | `cruzar`, providers falsos, market cap, SGS/Focus/Tesouro | respostas sintéticas |
| `test_config.py`, `test_cli.py` | YAML real, `CliRunner` (`qa`/`historico`/`cobertura`/`premissas sugerir` sobre DFP sintética; `perfil` com `input=`; `wacc` com `_mercado` trocado por `mercado_falso`). `ambiente_offline` aponta `DIR_EMPRESAS` para `tmp_path` | `ambiente_offline`, `weg_sintetica`, `caminho_perfil` |
| `test_perfil.py` | questionário (10 perguntas, 1–5 pontos, vetos), faixas, vetos, validade, JSON ida e volta e adulterado, `resolver_perfil`, parâmetros do settings | `respostas(padrao, **trocas)` |
| `test_premissas.py` | esquema do YAML (padrões, manual, listas, inválidos), carga e ticker, conferência com o cadastro, conversão dos ajustes, YAMLs do repositório, escrita ida e volta | `MINIMO`, `historico_anual` |
| `test_sugestor.py` | sugestões calculadas à mão (medianas, reversão da margem, desvios e limites), resumo, histórico curto e com buraco, commodity | `historico_anual` |
| `test_projetor.py` | projeção de 3 anos calculada à mão, anos projetados, fração do ano, `resolver` (sugerido, manual, listas, erros), cenários, g terminal | `PREMISSAS`, `historico_anual` |
| `test_beta.py`, `test_capm.py`, `test_kd.py`, `test_wacc.py` | regressão em série sintética com beta exato, Blume, Hamada, comparáveis, classe mais líquida; Ke dos dois métodos e coerência por Fisher; Kd com dívida média, buracos e limites; WACC à mão, estrutura, realavancagem, `validar_g`, tabela e CSV br/intl | `precos(retornos)` (sextas) |
| `test_padronizacao.py`, `test_periodos.py`, `test_moeda.py`, `test_nao_financeiras.py`, `test_qa.py` | regras, reapresentação, LTM/trimestre, métricas calculadas à mão, cada verificação do QA | `tests/sintetico.py` |
| `test_golden.py` | 94 valores de `tests/golden/referencias.yaml` contra o pipeline | **dados reais** em `data/processed/cvm/`; pulado se ausentes |

`conftest.py`: `SessaoFalsa` (rotas URL → `(status, bytes, headers)`; devolve 304 se
`If-Modified-Since == Last-Modified`; 404 para rota ausente), `resposta()`, `montar_zip()`,
fixture `zip_cvm`. Pytest roda com `pythonpath=tests` (importa `conftest` direto).
`sintetico.py`: `documento(contas, dem=, dt_fim=, dt_ini=, dt_refer=, fonte=, versao=, ordem=, …)`
(linhas no formato de `demonstracoes.parquet`), `dfp_completa(ano, **trocas)` (DFP consistente com
todas as críticas; `trocas={"DRE": {"3.02": 60}}`, `None` remove), `contas_padronizadas(registros)`
com `ano()`, `ytd()`, `saldo()`.
`historico_anual(crescimento, margem, *, inicio, da, capex, nwc, arrendamento, aliquota)`:
métricas anuais mínimas para o sugestor/projetor (razões sobre a receita viram valores).
`test_golden.py`: chaves da referência → métrica em `FLUXOS`/`SALDOS`; definições próprias das
companhias em `NAO_COMPARAVEIS`; período ainda não publicado na CVM é pulado.
Fixtures CVM são amostras minúsculas (uma empresa, 2025/2026): ao mudar parsing, atualize-as em
vez de baixar dados reais. Sem rede nos testes.

## 15. Receitas rápidas

| Quero… | Mexa em… |
|---|---|
| Mudar tolerância de divergência | `settings.yaml > validacao_cruzada` |
| Novo campo de configuração | classe em `config.py` **e** `settings.yaml` (extra=forbid) + `test_config.py` |
| Nova série SGS/indicador | constante `SGS_*` + função interna em `carregar_macro` com `cruzar(...)` + campo em `Macro` + linha em `cli.mercado` |
| Nova fonte de preço | classe que satisfaz `PrecosProvider`; passe-a a `preco_validado`; a camada de modelos não muda |
| Mais anos de histórico | `settings.historico_anos` (DFP antes de 2010 não existe; composição de capital só ≥ 2020) |
| Corrigir escala de ações de uma empresa | `cadastro_manual.csv > escala_acoes` (1 ou 1000) |
| Mapear conta nova ou corrigir regra | `config/mapeamento_contas.yaml` (+ crítica em `contas_criticas` se for o caso); confira com `valuation cobertura --tickers …` e `valuation qa` |
| Caso particular de uma empresa | `config/empresas/{TICKER}.yaml > ajustes.mapeamento_extra` (cria ou sobrepõe conta; entra antes das regras padrão) |
| Somar uma conta ao caixa / subtrair na ponte | `ajustes.caixa_extra` / `divida_extra` com o nome da **conta padrão** (crie-a com `mapeamento_extra` se não existir) |
| Fixar uma premissa | troque `sugerido` por número (ou lista em crescimento/margem) no YAML da empresa; `valuation premissas sugerir TICKER` mostra a sugestão ao lado |
| Mudar a regra de sugestão (janelas, limites, reversão, deltas) | constantes no topo de `projecao/sugestor.py` + teste à mão em `test_sugestor.py` (decisão de negócio: ADR) |
| Novo campo de premissa | classe em `projecao/premissas.py` + uso em `projetor.resolver` + linha em `escrita.renderizar` (o teste de ida e volta pega o esquecimento) |
| Fixar beta ou Kd de uma empresa | `config/empresas/{TICKER}.yaml > custo_capital.beta` / `kd: {metodo: manual, valor: ...}` (beta declarado no YAML vence o `settings`) |
| Mudar ERP, faixa do Kd, Blume, janela do beta | `settings.yaml > custo_capital` (sem código) |
| Novo componente no `wacc.csv` | linha em `wacc.tabela` (valor numérico; texto em `detalhe`) |
| Novo setor | `config/setores.yaml` (`descricao`, `tipo_modelo`, `commodity`, `pares`) |
| Nova métrica histórica | `nao_financeiras.metricas` (+ `OPCIONAIS` se a conta pode faltar) + linha em `cli._LINHAS_HISTORICO` + teste à mão |
| Nova verificação de QA | gerador `_x(...) -> Iterable[Verificacao]` em `qa.py`, chamado em `verificar`; colunas lidas em `_*_USADOS` |
| Novo valor de conciliação | `tests/golden/referencias.yaml` (R$ mi) + chave em `FLUXOS`/`SALDOS` de `test_golden.py` |
| Mudar pergunta, pontos ou veto do questionário | `perfil/questionario.py`; se a classificação puder mudar, **suba `VERSAO_QUESTIONARIO`** (perfis antigos passam a ser recusados) |
| Mudar faixas de pontuação | `LIMITE_CONSERVADOR`/`LIMITE_MODERADO` em `perfil/pontuacao.py` + subir `VERSAO_QUESTIONARIO` |
| Mudar margem, pesos, horizonte ou hurdle de um perfil | `settings.yaml > perfil` (sem código) |
| Registrar fonte/URL validada | `docs/fontes.md` (obrigatório pelo CLAUDE.md) |
| Decisão que desvia do CLAUDE.md | ADR em `docs/decisoes/NNNN-*.md` + linha no índice `docs/decisoes/README.md` + item em "Decisões" do `README.md` |
| Fechar uma fase | atualizar `CHANGELOG.md`, `README.md` (Estado atual), seções 1 e 12 deste guia e o ✅ na seção 17 do `CLAUDE.md`; `make lint tipos testes`; resumir ao usuário |

## 16. Armadilhas (resumo)

1. `CD_CVM` com zero à esquerda na DFP/ITR, sem no cadastro ⇒ sempre `normalizar_cd_cvm`.
2. `MOEDA` na CVM é `REAL` até para a Vale (ADR 0002): detecção de moeda não vem do campo hoje.
3. Composição do capital: sem escala e semântica do "total" varia (seção 9).
4. Códigos de conta mudam entre períodos da mesma empresa (D&A da Vale: `6.01.01.05` × `.06`) ⇒
   mapear por `cd_conta` **e** regex de `ds_conta`. Arrendamento da WEG está fora de empréstimos.
5. ITR: DRE traz acumulado e trimestre (distinguir por `dt_ini`); DFC só acumulado; não há ITR do 4º
   tri. LTM = anual + YTD atual − YTD anterior.
6. Selic meta do SGS traz datas futuras; Tesouro CSV não é ordenado.
7. Aviso de Rf (NTN-F × NTN-B+Focus) divergente é **esperado** hoje; não é bug.
8. brapi sem token: só 4 tickers; `marketCap` da brapi não bate com ações × preço (não usar).
9. `golden/referencias.yaml` está em **R$ milhões**; os parquets estão em **unidades**.
10. `data/`, `perfil/perfil_investidor.json`, `saida/`, `referencias/**` estão no `.gitignore`.
11. Regex do mapeamento roda sobre `DS_CONTA` **sem acento e minúscula**: regex com acento nunca casa.
12. `cd_prefixo` casa só descendentes (`"2.01"` não casa `2.01`). Regex sem prefixo pega a conta em
    qualquer seção (ex.: "amortiza" casaria "Amortizações de principal" em `6.03`).
13. Na tabela padronizada a conta some do período sem regra que case; nas métricas, conta fora de
    `OPCIONAIS` ausente é erro. Concatenar DataFrame vazio de `documento()` vira coluna `object` e
    quebra `.dt` (nos testes, não gere documento sem contas).
14. Sinais: DRE/DFC como na CVM (despesa/saída negativa), D&A positiva; nas **métricas** capex,
    dividendos e pagamento de arrendamento ficam positivos. IR do `golden` é positivo.
15. Dividendos YTD da WEG nem sempre crescem ao longo do ano (dado da companhia): trimestre pode
    sair estranho sem ser bug.
16. `perfil_investidor.json` guarda o **número da alternativa** escolhida (1 = primeira), não os
    pontos. `registro.ler` recalcula tudo e recusa o arquivo se pontuação, perfil, vetos ou validade
    não baterem (editar o JSON à mão não funciona: refaça o questionário).
17. A validade do perfil (12 meses, `VALIDADE_MESES`) é conferida contra a data real passada por
    quem chama (`date.today()` na CLI), não contra `data_base`.
18. `--escrever` **regenera** o YAML da empresa inteiro: comentários próprios se perdem (o
    anterior fica em `.yaml.bak`, gitignored). Anotações duráveis vão em `descricao` dos campos ou
    num ADR.
19. Lista explícita de crescimento/margem começa no exercício **seguinte ao último histórico**, não
    no ano corrente: em fevereiro, sem a DFP do ano anterior, o 1º valor é o do ano-ponte.
20. O 1º ano projetado parte do último exercício completo e ignora o YTD já divulgado (ADR 0006): a
    trajetória sugerida pode contradizer o acumulado do ano. Confira com `valuation historico`.
21. A margem sugerida é a **ajustada** (sem equivalência e não recorrentes); o `historico` mostra a
    margem contábil (`margem_ebitda`), que pode ser maior.
22. `caixa_extra` reduz a dívida líquida mas não sai do capital de giro: use contas fora do ativo
    circulante.
23. `despesas_financeiras` (DRE `3.06.02`) inclui variação cambial e monetária: o Kd histórico bruto
    dos pilotos vai de 7,8% (PETR4) a 44% (WEGE3). O valor usado costuma ser o limite da faixa;
    confira `kd_bruto` × `kd` no `wacc.csv`.
24. Na tabela do custo de capital, `valor` é sempre `float64`: texto em `valor` quebraria o decimal
    `,` do CSV pt-BR.

## 17. `perfil/` — perfil do investidor

Seção 8 do `CLAUDE.md`. Não importa `data`, `contabil` nem camadas de cálculo; só `config`
(`ConfigPerfil`). Exceção: `ErroPerfil`; literal `NomePerfil` (`conservador|moderado|arrojado`),
ambos em `perfil/__init__.py`.

| Módulo | Símbolos | Detalhe |
|---|---|---|
| `questionario.py` | `QUESTIONARIO` (10 `Pergunta(chave, tema, enunciado, alternativas)`), `Alternativa(texto, pontos, veto=None)`, `VERSAO_QUESTIONARIO=1`, `VETO_HORIZONTE_CURTO`, `VETO_NAO_ACEITA_PERDAS` | Só dados. Chaves `q1`–`q10`; cada pergunta vai de 1 a 5 pontos (testado). Vetos: q2 "Menos de 2 anos", q9 "Não aceito perdas" |
| `pontuacao.py` | `classificar(respostas, questionario=QUESTIONARIO) -> Classificacao(pontuacao, perfil, vetos_aplicados)`, `perfil_da_pontuacao` | Faixas 10–24 / 25–37 / 38–50 (`LIMITE_*`). Qualquer veto ⇒ conservador. Resposta faltando, sobrando ou fora de 1..n ⇒ `ErroPerfil` |
| `registro.py` | `RegistroPerfil` (esquema da seção 8.3, `.vencido(hoje)`, `.para_dict()`), `criar_registro(respostas, data)`, `gravar`, `ler`, `somar_meses`, `resolver_perfil(caminho, hoje, override) -> PerfilEfetivo(perfil, origem, registro)` | `valido_ate = data + 12 meses` (29/02 ⇒ 28/02). `ler`: ausente ⇒ `FileNotFoundError`; versão diferente, JSON inválido ou classificação inconsistente ⇒ `ErroPerfil`. `resolver_perfil`: override vence (origem `override`); sem arquivo ou vencido ⇒ `ErroPerfil` pedindo `valuation perfil` |
| `parametros.py` | `parametros_do_perfil(perfil, settings.perfil) -> ParametrosPerfil(perfil, margem_seguranca, peso_{pessimista,base,otimista}, horizonte_anos, hurdle_spread_selic)`, `.hurdle(selic)` | Valores no `settings.yaml` (seção 4), todos PLACEHOLDER |

O perfil **não** altera fatos contábeis nem o custo de capital: o valor intrínseco por cenário é o
mesmo para todos os perfis.

## 18. `projecao/` — premissas, sugestor e projetor

Seções 9.1–9.3 do `CLAUDE.md` e ADR 0006. Importa `config` e `contabil.nao_financeiras` (ajustes);
não importa `data`, `perfil` nem a CLI. Exceção: `ErroProjecao` (`projecao/__init__.py`).

| Módulo | Símbolos | Detalhe |
|---|---|---|
| `premissas.py` | `PremissasEmpresa` (pydantic, `extra=forbid`, frozen) com `Ajustes`, `ConfigProjecao`, `Cenarios`/`DeltaCenario`, `Pares`, `CustoCapitalEmpresa`; `Trajetoria(inicio, fim, curva=linear)`; `SUGERIDO`; `caminho_premissas(ticker, dir)`, `carregar_premissas(caminho)`, `premissas_padrao(ticker, tipo, classes)`, `conferir_cadastro(premissas, tickers, tipo)`, `ajustes_contabeis(ajustes) -> AjustesContabeis` | Todo campo de premissa aceita `sugerido` ou número; crescimento e margem aceitam também lista. Limites: frações em [0, 1] (NWC e trajetórias em [−1, 1]), deltas em [−0,5; 0,5], horizonte 1–30. Ticker ≠ nome do arquivo, `tipo_modelo` fora de `nao_financeira`/`financeira`, `metodo: manual` sem `valor`, alíquota acima de `limite_superior` ⇒ erro. `nao_recorrentes.valor` em **unidades** da moeda |
| `sugestor.py` | `sugerir(historico, *, g_terminal, aliquota_limite, commodity, setor=None) -> Sugestoes`; `Sugestao(valor, origem)`; `razoes(historico)`; `cagr`; `pct`, `pp` (formatação pt-BR) | Janelas por ano: 5a = 5 últimos exercícios, 10a = 10. Anos faltantes viram NaN (sem crescimento atravessando o buraco). Mínimo de 2 exercícios. Constantes `JANELA_*`, `CRESCIMENTO_MIN/MAX`, `REVERSAO_MARGEM`, `DELTA_*`, `FATOR_DELTA_CAPEX`. `Sugestoes.estatisticas` = linhas `ultimo`, `mediana_5a`, `mediana_10a`, `cagr_{3,5,10}a` × colunas de `razoes` |
| `projetor.py` | `primeiro_ano_aberto`, `anos_projetados(ano_base, data_base, horizonte)`, `fracao_restante(ano, data_base)`, `g_terminal(terminal, config) -> Sugestao`, `resolver(config, sugestoes, *, anos, aliquota_limite, descontar_arrendamento) -> PremissasResolvidas`, `resolver_cenarios(cenarios, sugestoes)`, `aplicar_cenario(base, delta, nome)`, `projetar(historico, premissas, *, data_base) -> DataFrame`; `COLUNAS_PROJECAO` | Funções puras. Histórico que inclui o exercício da data-base ⇒ erro (a CLI corta antes). Lista mais curta que os anos ⇒ erro; mais longa é cortada |
| `escrita.py` | `renderizar(premissas, sugestoes, *, data_base) -> str` | YAML inteiro com comentários (`sugerido: X (origem)` ou `manual; sugerido seria X`), linhas de comentário ≤ 100 colunas. `carregar_premissas` do texto devolve as mesmas premissas (testado) |

| Sugestão | Regra |
|---|---|
| Crescimento | início = mediana do crescimento de 5a limitada a [−5%, 20%]; fim = g terminal (`g_nominal` do YAML ou `settings.terminal.g_nominal_max`); linear |
| Margem EBITDA | **ajustada** (`ebitda_ajustado / receita`): início = mediana 5a; fim = média das medianas de 5a e 10a; linear |
| D&A, capex, NWC, arrendamento / receita | mediana 5a (arrendamento = pagamento da DFC; sem dado ⇒ 0) |
| Alíquota | mediana da efetiva de 5a limitada a [0, limite]; sem LAIR positivo ⇒ limite |
| Deltas dos cenários | crescimento e margem: 1 desvio-padrão de 10a em [1, 5] p.p.; capex: 0,5 desvio em [0,25; 2] p.p.; histórico curto ⇒ piso. Pessimista −, −, +; otimista +, +, − |

| Coluna da projeção | Fórmula |
|---|---|
| `fracao` | 0 se o exercício já encerrou; (31/12 − data-base) / 365 no ano corrente; 1 depois |
| `receita_liquida` | receita do ano anterior × (1 + `crescimento`); o 1º ano parte do último exercício |
| `ebitda`, `da`, `ebit` | margem × receita; (D&A/receita) × receita; EBITDA − D&A (EBIT ajustado) |
| `imposto`, `nopat` | alíquota × EBIT (também com EBIT negativo); EBIT − imposto |
| `capex`, `arrendamento` | razão × receita |
| `delta_nwc` | (NWC/receita) × (receita − receita anterior) |
| `fcff` | NOPAT + D&A − capex − ΔNWC [− arrendamento se `ifrs16: divida` e `capex_equivalente_arrendamento`]. Ano inteiro: o DCF multiplica por `fracao` |

Horizonte: `projecao.horizonte_anos` inteiro ou `perfil` (5/7/10 do `settings.perfil`); conta só os
anos com fluxo por vir. Os anos projetados vão do exercício seguinte ao último histórico até o fim
do horizonte, e o ano-ponte sem DFP tem `fracao` 0.

## 19. `custo_capital/` e `saida/csv.py`

Seção 10 do `CLAUDE.md` e ADR 0007. Funções puras: preços, Rf e métricas entram por parâmetro;
nada consulta rede. Importa `config` (não importa `data`, `projecao` nem a CLI). Exceção:
`ErroCustoCapital` (`custo_capital/__init__.py`). Taxas em decimal, valores na moeda de reporte.

| Módulo | Símbolos | Detalhe |
|---|---|---|
| `beta.py` | `regressao(acao, indice, *, data_base, janela_semanas, ajuste_blume, min_r2_aviso, ticker=None) -> ResultadoBeta`, `precos_semanais`, `classe_mais_liquida(historicos, data_base, janela)`, `blume`, `desalavancar`, `realavancar`, `comparaveis(pares, *, divida_sobre_equity_alvo, aliquota)`, `manual(valor)` | Preço de sexta (`W-FRI`) até a data-base, retornos simples, últimas N semanas, OLS com constante (`statsmodels`). `MIN_SEMANAS = 52` (menos ⇒ erro). Avisos: R² < mínimo, janela incompleta, > `LIMIAR_SEMANAS_PARADAS` (10%) de semanas sem variação. `ResultadoBeta.beta` é o usado (Blume aplicado); `beta_bruto` é o da OLS (nos comparáveis, a mediana desalavancada) |
| `capm.py` | `custo_capital_proprio(*, metodo, moeda, beta, erp, rf_brl, rf_usd, crp, inflacao_usd, inflacao_brl) -> CustoCapitalProprio`, `metodo_efetivo(metodo, moeda)`, `converter_taxa(taxa, pi_destino, pi_origem)` | `brl_direto` só com moeda BRL. `usd_crp` em BRL exige `inflacao_brl` (a CLI usa o Focus do ano mais distante) |
| `kd.py` | `historico(despesas_financeiras, divida_bruta, *, piso, teto, janela=3) -> ResultadoKd`, `taxas_anuais`, `manual(valor)` | Despesas no sinal da DRE (negativas); dívida média de anos consecutivos; mediana dos últimos `JANELA_KD_ANOS`; sem nenhum ano ⇒ erro pedindo Kd manual |
| `wacc.py` | `estrutura(*, metodo, divida, equity, divida_sobre_capital_alvo=None) -> Estrutura`, `beta_na_estrutura(beta, estrutura, aliquota)`, `wacc(ke, kd, aliquota, peso_divida)`, `montar(...) -> CustoCapital`, `validar_g(taxa, g, nome="WACC")`, `tabela(cc) -> DataFrame` | Só o beta da **regressão** é realavancado (comparáveis já saem no alvo; manual é tomado como dado). `CustoCapital(data_base, beta, beta_regressao, ke, kd, aliquota, estrutura, wacc, data_balanco, avisos)`, `.kd_liquido` |
| `saida/csv.py` | `gravar_csv(df, caminho, config_csv, formato="br")`, `INTERNACIONAL` | `br` = `settings.csv`; `intl` = `,` `.` utf-8. Cria os diretórios; sem índice |

Montagem na CLI (`_custo_capital`): moeda da padronização → `metodo_efetivo`; balanço =
`_data_balanco` → `metricas_ltm(dt_fim=…)["divida_bruta"]`; equity = `MarketCap.valor` (÷ dólar se
USD); beta (`_beta`) → `beta_na_estrutura`; Ke com `Macro.rf_brl`; Kd do YAML manual ou histórico
dos exercícios encerrados com piso/teto = Rf da moeda + `kd.spread_*`; alíquota =
`impostos.aliquota_nominal`; por fim `validar_g` contra `projetor.g_terminal`.
