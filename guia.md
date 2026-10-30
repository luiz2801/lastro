# guia.md — Mapa do código para quem vai modificá-lo

**Versão 1.0 — 2026-10-30**

> Complementa o `CLAUDE.md` (especificação e roadmap). Este arquivo descreve **o que existe hoje**
> (Fases 0, 1 e 3 implementadas) para que você não precise reler os módulos. Para o que ainda
> **não** existe, veja a seção 11.

> ## Regra de manutenção (obrigatória)
>
> **Antes de modificar:** leia deste guia a seção do módulo que vai mexer (e as seções 12 e 15,
> convenções e armadilhas). Só abra o código-fonte para o que o guia não responder. Planeje a
> alteração a partir daqui.
>
> **Ao modificar:** toda alteração de lógica, contrato, parâmetro, arquivo ou comando precisa ser
> refletida neste guia **na mesma entrega (mesmo commit)**: função nova/removida/renomeada,
> fórmula ou critério trocado, parâmetro de `settings.yaml` que passou a ser lido (tire o ⏳),
> fase concluída (atualize as seções 1 e 11), armadilha descoberta (seção 15).
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
| CLI | `cli.py` | `versao`, `cadastro buscar`, `atualizar`, `mercado` |
| `contabil`, `projecao`, `custo_capital`, `modelos`, `analise`, `perfil`, `saida` | `__init__.py` de 1 linha | ❌ vazios (Fases 2, 4–10) |

~2.000 linhas de código, 100 testes, mypy `strict`, ruff (linha 100).

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
```

Todo download passa por `http.baixar` (cache em `data/raw/` + `.meta.json`). Camada superior nunca
é importada por inferior: `data` não importa `cli`; `macro` não conhece provedores de preço
(o câmbio alternativo entra por parâmetro); `precos` importa `cadastro.Empresa` e `validacao`.

## 3. Comandos da CLI (`cli.py`)

Callback global: `-v/--verbose` → logging DEBUG. Erros: `_erro()` imprime em vermelho e devolve
`typer.Exit(1)`. Funções auxiliares: `_carregar_cadastro(settings, data_base, forcar)` (chama
`cad.atualizar_cadastro` com TTL de `cache_ttl_horas.cvm`), `_tickers_do_universo(caminho)`,
`_linha_validada(v, formato)` (cor por status).

| Comando | Parâmetros | O que faz | Efeito de cada parâmetro |
|---|---|---|---|
| `versao` | — | Imprime versão e Python | — |
| `cadastro buscar TEXTO` | `--forcar` | Busca por ticker/razão/nome/CNPJ no cadastro | `--forcar` ignora TTL e rebaixa cadastro+FCA |
| `atualizar` | `--tickers A,B` ou `--tudo`; `--forcar` | Baixa DFP/ITR/composição e grava parquets por companhia | exatamente um de `--tickers`/`--tudo`. `--tudo` lê `config/universo_ibovespa.csv` (**arquivo ainda não existe**, dá `ErroConfiguracao`). Holding/não suportada: só avisa e baixa |
| `mercado TICKER` | `--data-base AAAA-MM-DD`; `--forcar` | Preço por classe, Ibovespa, dólar, Selic, IPCA, Rf e market cap, cada um em 2 fontes | `--data-base` sobrescreve `settings.data_base`. Exige `atualizar` antes (lê `composicao_capital.parquet`; senão mensagem pedindo o comando) |

Observação: `mercado` usa `settings.custo_capital.rf_brl.override` como Rf manual **independentemente
de `rf_brl.fonte`** (a regra `fonte=manual ⇒ override` está só no validador pydantic).

Para adicionar um comando: função `@app.command()` em `cli.py`, capturar
`(ErroConfiguracao, ErroDownload, cad.ErroCadastro, ErroDadosExternos, ...)` → `raise _erro(str(e)) from e`,
e testar com `typer.testing.CliRunner` em `tests/test_cli.py`.

## 4. `config.py`

Constantes de caminho (relativas à raiz do repo): `DIR_CONFIG`, `CAMINHO_SETTINGS`,
`CAMINHO_CADASTRO_MANUAL`, `CAMINHO_UNIVERSO`, `DIR_RAW` (`data/raw`), `DIR_PROCESSED`
(`data/processed`).

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
| `historico_anos` | 10 | `cvm.anos_a_coletar`: DFP de `ano-10` até `ano` (11 zips). Aumentar ⇒ mais downloads (DFP < 2010 não existe) |
| `moeda_saida` | BRL | ⏳ |
| `csv.*` | `;` `,` `utf-8-sig` | ⏳ (Fase 9) |
| `cache_ttl_horas.cvm/precos/macro` | 168 / 12 / 12 | TTL do cache de CVM+cadastro / preços yfinance / macro. Dentro do TTL não há rede |
| `impostos.aliquota_nominal` | 0.34 | ⏳ |
| `custo_capital.rf_brl.override` | null | Se numérico, `carregar_macro` não consulta Tesouro e marca Rf como `manual` |
| `custo_capital.*` (resto) | — | ⏳ (Fase 6) |
| `terminal.*`, `dcf.*`, `sensibilidade.*` | — | ⏳ (Fase 7) |
| `validacao_cruzada.preco_rel` | 0.02 | Tolerância relativa de preço (principal × alternativa) |
| `validacao_cruzada.cambio_rel` | 0.015 | Idem dólar (PTAX × `BRL=X`) |
| `validacao_cruzada.market_cap_rel` | 0.10 | ⏳ (declarado, sem uso) |
| `validacao_cruzada.selic_abs` | 0.003 | Diferença absoluta máx. Selic meta × diária anualizada |
| `validacao_cruzada.ipca_abs` | 0.0005 | Idem IPCA 12m (direto × composto) |
| `validacao_cruzada.rf_abs` | 0.025 | Idem Rf (NTN-F × NTN-B+Focus). Apertar gera aviso permanente (spread de inflação ≈ 3 p.p.) |

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

## 11. O que NÃO existe ainda (não procure no código)

| Fase | Falta | Dica de onde conectar |
|---|---|---|
| 2 | `contabil/*`, `config/mapeamento_contas.yaml`, `qa.py`, golden tests | Entrada: `data/processed/cvm/{cd_cvm}/demonstracoes.parquet`. Valores de conferência: `tests/golden/referencias.yaml` (R$ milhões!) |
| 4 | Perfil/questionário | `perfil/perfil_investidor.json` (gitignored) |
| 5–10 | projeção, beta/CAPM/WACC, DCF, DDM, múltiplos, sensibilidade, saídas CSV/PNG | Parâmetros já validados em `Settings` |
| — | `config/universo_ibovespa.csv`, `config/setores.yaml`, `config/empresas/*.yaml` | `--tudo` falha sem o universo |
| — | comandos `perfil`, `qa`, `premissas`, `rodar`, `comparar` | seção 14 do `CLAUDE.md` |

## 12. Convenções que o código já segue (siga também)

- **Funções puras** recebem `agora`/`data_base` por parâmetro; `date.today()`/`datetime.now()` só na
  CLI (`cli.py`).
- **I/O por injeção**: sessão HTTP (`SessaoHttp`), diretórios (`dir_raw`, `dir_processed`) e
  `espera` são parâmetros nomeados (keyword-only `*`), o que torna tudo testável offline.
- **Dinheiro em unidades da moeda** (escala aplicada na ingestão). Ações em unidades (escala
  corrigida). Taxas em **decimal** (0,1375, não 13,75).
- Exceções em português `ErroX` (N818 ignorado no ruff). Hierarquia: `ErroDownload ⊃
  ArquivoNaoEncontrado`; `ErroDadosExternos ⊃ ErroPrecos`; `ErroCadastro`, `ErroDadosCVM`,
  `ErroConfiguracao`.
- Dataclasses `frozen=True` para objetos trocados entre camadas; pydantic só para configuração.
- Identificadores de domínio em português; mensagens ao usuário em PT-BR.
- Dependência opcional pesada (`yfinance`) é importada **dentro** da função (`_baixar`).
- Não usar `QUOTE_NONE` ⇒ quebra; não reordenar `COLUNAS_*` sem revisar parquets existentes
  (apague `data/processed/` e rode `atualizar --forcar` se mudar esquema).

## 13. Testes

| Arquivo | Cobre | Fixtures |
|---|---|---|
| `test_http.py` | cache, TTL, 304, retry, fallback | `sessao_falsa` |
| `test_cvm.py` | parsing, escala, versões, `coletar` | `zip_cvm("dfp_cia_aberta_2025")` etc. |
| `test_cadastro.py` | FCA, manual, classificação, busca | `tests/fixtures/cvm/*` |
| `test_validacao.py`, `test_precos.py`, `test_macro.py` | `cruzar`, providers falsos, market cap, SGS/Focus/Tesouro | respostas sintéticas |
| `test_config.py`, `test_cli.py` | YAML real, `CliRunner` | — |

`conftest.py`: `SessaoFalsa` (rotas URL → `(status, bytes, headers)`; devolve 304 se
`If-Modified-Since == Last-Modified`; 404 para rota ausente), `resposta()`, `montar_zip()`,
fixture `zip_cvm`. Pytest roda com `pythonpath=tests` (importa `conftest` direto).
Fixtures CVM são amostras minúsculas (uma empresa, 2025/2026): ao mudar parsing, atualize-as em
vez de baixar dados reais. Sem rede nos testes.

## 14. Receitas rápidas

| Quero… | Mexa em… |
|---|---|
| Mudar tolerância de divergência | `settings.yaml > validacao_cruzada` |
| Novo campo de configuração | classe em `config.py` **e** `settings.yaml` (extra=forbid) + `test_config.py` |
| Nova série SGS/indicador | constante `SGS_*` + função interna em `carregar_macro` com `cruzar(...)` + campo em `Macro` + linha em `cli.mercado` |
| Nova fonte de preço | classe que satisfaz `PrecosProvider`; passe-a a `preco_validado`; a camada de modelos não muda |
| Mais anos de histórico | `settings.historico_anos` (DFP antes de 2010 não existe; composição de capital só ≥ 2020) |
| Corrigir escala de ações de uma empresa | `cadastro_manual.csv > escala_acoes` (1 ou 1000) |
| Registrar fonte/URL validada | `docs/fontes.md` (obrigatório pelo CLAUDE.md) |
| Decisão que desvia do CLAUDE.md | ADR em `docs/decisoes/NNNN-*.md` |
| Fechar uma fase | atualizar `CHANGELOG.md`, `make lint tipos testes`, resumir ao usuário |

## 15. Armadilhas (resumo)

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
