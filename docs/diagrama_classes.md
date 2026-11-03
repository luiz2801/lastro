# Diagrama de Classes — Lastro

Estrutura estática do código: as classes, os atributos principais e como se relacionam. O comportamento está nos diagramas de [atividades](diagrama_atividades.md), [sequência](diagrama_sequencia.md), [interação](diagrama_interacao.md) e [estados](diagrama_estados.md); as instâncias em [objetos](diagrama_objetos.md). Índice em [`diagramas.md`](diagramas.md). Assinaturas e contratos completos ficam no [`guia.md`](../guia.md).

## Como ler

- **Estilo do código.** O motor de cálculo é de **funções puras** sobre **dataclasses `frozen`**. Por isso as classes têm quase só atributos e as operações (`projetar`, `descontar`, `avaliar`, `ponte`…) são funções de módulo, não métodos. Mostro como operação apenas o que é método de fato (`tickers`, `ev`, `hurdle`…).
- **Pydantic** (`extra="forbid"`, `frozen`) só na configuração: `Settings` e `PremissasEmpresa`.
- **`<<Protocol>>`** é tipagem estrutural do Python (sem herança explícita). A seta de realização tracejada (`..|>`) indica "satisfaz o contrato".
- **Composição** (`*--`): o todo cria e carrega as partes. **Agregação** (`o--`): referência a algo que existe por si. **Dependência** (`..>`): a função que produz ou consome o objeto (ex.: `cruzar` produz `Validado` a partir de duas `Leitura`).
- Cada diagrama mostra os **atributos principais**; a lista completa está no código. Uma classe sem atributos num diagrama é uma referência a outro diagrama.
- Valores `Literal` aparecem como o nome do tipo (`NomePerfil` = `conservador`, `moderado` ou `arrojado`; `NomeCenario` = `pessimista`, `base` ou `otimista`).

## 1. Dados externos e cadastro (`data/`)

```mermaid
classDiagram
    direction LR

    class PrecosProvider {
        <<Protocol>>
        +nome: str
        +historico(simbolo, inicio, fim) DataFrame
        +cotacao(simbolo) Cotacao
    }
    class YFinanceProvider {
        +nome: str
        +historico(simbolo, inicio, fim) DataFrame
        +cotacao(simbolo) Cotacao
    }
    class BrapiProvider {
        +nome: str
        +historico(simbolo, inicio, fim) DataFrame
        +cotacao(simbolo) Cotacao
    }
    class Cotacao {
        +simbolo: str
        +preco: float
        +data: date
        +market_cap: float?
        +fonte: str
    }
    class SessaoHttp {
        <<Protocol>>
        +get(url, headers, timeout, stream) resposta
    }
    class ArquivoBaixado {
        +caminho: Path
        +meta: MetaDownload
        +do_cache: bool
    }
    class MetaDownload {
        +url: str
        +baixado_em: str
        +verificado_em: str
        +sha256: str
        +tamanho_bytes: int
        +last_modified: str?
    }

    class Empresa {
        +cnpj: str
        +cd_cvm: int
        +razao_social: str
        +nome_comercial: str
        +setor_cvm: str
        +tipo_modelo: TipoModelo
        +escala_acoes: int
        +tickers() tuple
    }
    class ClasseAcao {
        +ticker: str
        +especie: Especie
        +acoes_por_unit: int
    }
    class AlvoCVM {
        +cnpj: str
        +cd_cvm: int
        +escala_acoes: int
    }
    class MarketCap {
        +valor: float
        +data_acoes: date
        +avisos: tuple
    }
    class ClasseMarketCap {
        +ticker: str
        +especie: str
        +acoes: int
        +preco: float
    }
    class Macro {
        +data_base: date
        +ipca_esperado: dict
        +pib_esperado: dict
        +data_focus: date?
        +avisos() tuple
    }
    class Validado {
        +nome: str
        +valor: float
        +fonte: str
        +status: Status
        +valor_alt: float?
        +divergencia: float?
        +aviso() str?
    }
    class Leitura {
        +valor: float
        +fonte: str
        +data: date?
    }

    YFinanceProvider ..|> PrecosProvider
    BrapiProvider ..|> PrecosProvider
    BrapiProvider ..> SessaoHttp : usa
    PrecosProvider ..> Cotacao : devolve
    ArquivoBaixado *-- MetaDownload
    Empresa "1" *-- "1..*" ClasseAcao : classes
    AlvoCVM ..> Empresa : montado a partir de
    MarketCap "1" *-- "1..*" ClasseMarketCap : classes
    MarketCap ..> Empresa : market_cap(empresa, ...)
    Macro "1" *-- "4" Validado : selic, ipca_12m, cambio, rf_brl
    Leitura ..> Validado : cruzar(principal, alternativa)
```

- `Status` de `Validado`: `ok`, `divergente`, `sem_validacao` ou `manual`. Divergência **não interrompe**: vira aviso, e o valor usado é o da fonte principal (ADR 0004).
- `TipoModelo`: `nao_financeira`, `financeira`, `holding` ou `nao_suportada`. `Especie`: `ON`, `PN` ou `UNIT`.
- `PrecosProvider` e `SessaoHttp` são os **pontos de troca**: nova fonte de preço ou sessão falsa nos testes entram sem tocar nos modelos (regra 3 do `CLAUDE.md`).

## 2. Configuração (`config.py`)

```mermaid
classDiagram
    direction LR

    class Settings {
        <<pydantic frozen>>
        +versao: int
        +data_base: hoje ou date
        +historico_anos: int
        +moeda_saida: BRL ou USD
        +resolver_data_base(hoje) date
    }
    class ConfigCsv {
        +separador: str
        +decimal: str
        +encoding: str
    }
    class CacheTtlHoras {
        +cvm: float
        +precos: float
        +macro: float
    }
    class Impostos {
        +aliquota_nominal: float
    }
    class ConfigCustoCapital {
        +metodo: brl_direto ou usd_crp
        +crp: float
        +rf_usd: float
        +inflacao_usd_lp: float
    }
    class RfBrl {
        +fonte: str
        +override: float?
    }
    class ConfigErp {
        +fonte: manual ou implicito_ibovespa
        +valor: float
        +validade_dias: int
    }
    class ConfigBeta {
        +metodo: str
        +janela_semanas: int
        +ajuste_blume: bool
        +min_r2_aviso: float
    }
    class LimitesKd {
        +spread_min: float
        +spread_max: float
    }
    class EstruturaAlvo {
        +metodo: mercado_atual, setor ou manual
        +divida_sobre_capital: float?
    }
    class ConfigTerminal {
        +g_nominal_max: float
        +ronic: wacc, roic_historico ou float
        +checagem_multiplo_saida: bool
    }
    class ConfigDcf {
        +convencao_meio_periodo: bool
        +alerta_tv_sobre_ev: float
    }
    class ConfigSensibilidade {
        +wacc_passo: float
        +wacc_faixa: float
        +g_passo: float
        +g_faixa: float
    }
    class ConfigMultiplos {
        +min_pares: int
    }
    class Winsorizacao {
        +inferior: float
        +superior: float
    }
    class ValidacaoCruzada {
        +preco_rel: float
        +cambio_rel: float
        +selic_abs: float
        +rf_abs: float
    }
    class ConfigPerfil
    class ParametrosPerfilConfig {
        +margem_seguranca: float
        +horizonte_anos: int
        +hurdle_spread_selic: float
    }
    class PesosCenarios {
        +pessimista: float
        +base: float
        +otimista: float
    }
    class Setor {
        <<pydantic frozen>>
        +descricao: str
        +tipo_modelo: str
        +commodity: bool
        +pares: tuple
    }

    Settings *-- ConfigCsv : csv
    Settings *-- CacheTtlHoras : cache_ttl_horas
    Settings *-- Impostos : impostos
    Settings *-- ConfigCustoCapital : custo_capital
    Settings *-- ConfigTerminal : terminal
    Settings *-- ConfigDcf : dcf
    Settings *-- ConfigSensibilidade : sensibilidade
    Settings *-- ConfigMultiplos : multiplos
    Settings *-- ValidacaoCruzada : validacao_cruzada
    Settings *-- ConfigPerfil : perfil
    ConfigCustoCapital *-- RfBrl : rf_brl
    ConfigCustoCapital *-- ConfigErp : erp
    ConfigCustoCapital *-- ConfigBeta : beta
    ConfigCustoCapital *-- LimitesKd : kd
    ConfigCustoCapital *-- EstruturaAlvo : estrutura_alvo
    ConfigMultiplos *-- Winsorizacao : winsorizar
    ConfigPerfil "1" *-- "3" ParametrosPerfilConfig : conservador, moderado, arrojado
    ParametrosPerfilConfig *-- PesosCenarios : pesos_cenarios
```

`Setor` é lido de `config/setores.yaml` por `carregar_setores` (não faz parte de `Settings`). Todos os modelos herdam de `_Modelo` (`extra="forbid"`, `frozen=True`): campo novo no YAML exige campo novo na classe e vice-versa.

## 3. Perfil do investidor e universo (`perfil/`, `universo.py`)

```mermaid
classDiagram
    direction LR

    class Pergunta {
        +chave: str
        +tema: str
        +enunciado: str
    }
    class Alternativa {
        +texto: str
        +pontos: int
        +veto: str?
    }
    class Classificacao {
        +pontuacao: int
        +perfil: NomePerfil
        +vetos_aplicados: tuple
    }
    class RegistroPerfil {
        +versao_questionario: int
        +data: date
        +valido_ate: date
        +respostas: Mapping
        +pontuacao: int
        +vetos_aplicados: tuple
        +perfil: NomePerfil
        +vencido(hoje) bool
        +para_dict() dict
    }
    class PerfilEfetivo {
        +perfil: NomePerfil
        +origem: questionario ou override
    }
    class ParametrosPerfil {
        +perfil: NomePerfil
        +margem_seguranca: float
        +peso_pessimista: float
        +peso_base: float
        +peso_otimista: float
        +horizonte_anos: int
        +hurdle_spread_selic: float
        +hurdle(selic) float
    }
    class ConfigPerfil {
        <<settings.perfil>>
    }
    class SetorCVM {
        <<enumeration>>
        BANCOS
        ALIMENTOS
        ...33 setores
    }
    class EmpresaUniverso {
        +ticker: str
        +setor: SetorCVM
        +tipo_modelo: str
    }

    Pergunta "1" *-- "1..*" Alternativa : alternativas
    Pergunta ..> Classificacao : classificar(respostas)
    RegistroPerfil ..> Classificacao : recalcula ao ler
    PerfilEfetivo o-- "0..1" RegistroPerfil : registro
    ParametrosPerfil ..> ConfigPerfil : parametros_do_perfil(perfil, settings.perfil)
    PerfilEfetivo ..> ParametrosPerfil : define
    EmpresaUniverso --> SetorCVM : setor
```

- O JSON gravado guarda o **número da alternativa** escolhida, não os pontos; `registro.ler` recalcula pontuação, vetos e perfil e recusa o arquivo se algo não bater.
- `PerfilEfetivo.origem = override` quando vem de `--perfil`; nesse caso `registro` é `None`.
- `ParametrosPerfil` não altera fatos contábeis nem o custo de capital: só margem, pesos, horizonte e hurdle.

## 4. Premissas, contabilidade e projeção (`contabil/`, `projecao/`)

```mermaid
classDiagram
    direction LR

    class PremissasEmpresa {
        <<pydantic frozen>>
        +ticker: str
        +tipo_modelo: nao_financeira ou financeira
        +classes_acao: tuple
        +moeda_relatorio: auto, BRL ou USD
        +projecao_dcf() ConfigProjecao
        +cenarios_dcf() Cenarios
        +projecao_ddm() ProjecaoFinanceira
        +cenarios_ddm() CenariosFinanceira
    }
    class Ajustes {
        +consolidado: bool
        +ifrs16: divida ou ignorar
        +capex_equivalente_arrendamento: bool
        +minoritarios: contabil ou multiplo_pvp
        +coligadas: str
        +caixa_extra: tuple
        +divida_extra: tuple
        +mapeamento_extra: dict
    }
    class NaoRecorrenteConfig {
        +ano: int
        +conta: ebit
        +valor: float
        +descricao: str
    }
    class ConfigProjecao {
        +horizonte_anos: perfil ou int
        +da_sobre_receita: float ou sugerido
        +capex_sobre_receita: float ou sugerido
        +nwc_sobre_receita: float ou sugerido
        +arrendamento_sobre_receita: float ou sugerido
    }
    class ProjecaoFinanceira {
        +horizonte_anos: perfil ou int
        +payout_inicio: float ou sugerido
    }
    class Cenarios {
        +pessimista: DeltaCenario
        +otimista: DeltaCenario
    }
    class CenariosFinanceira {
        +pessimista: DeltaCenarioFinanceira
        +otimista: DeltaCenarioFinanceira
    }
    class Pares {
        +setor: str?
        +incluir: tuple
        +excluir: tuple
    }
    class CustoCapitalEmpresa {
        +beta: MetodoBeta
        +kd: MetodoKd
    }

    class AjustesContabeis {
        +ifrs16: str
        +capex_equivalente_arrendamento: bool
        +coligadas: str
        +caixa_extra: Sequence
        +divida_extra: Sequence
    }
    class NaoRecorrente {
        +ano: int
        +valor: float
        +descricao: str
    }
    class PlanoContas {
        +tipo: nao_financeira ou financeira
        +criticas: tuple
        +eh_saldo(conta) bool
    }
    class RegraMapeamento {
        <<pydantic>>
        +dem: Familia
        +cd: str?
        +cd_prefixo: tuple
        +ds_regex: str?
        +sinal: 1 ou -1
        +casar(contas) mascara
    }
    class ResultadoQA {
        +ticker: str
        +cd_cvm: int
        +moeda: str
        +cobertura: dict
        +erros() tuple
        +avisos() tuple
        +para_dict() dict
    }
    class Verificacao {
        +codigo: str
        +severidade: Severidade
        +mensagem: str
        +periodos: tuple
    }

    class Sugestoes {
        +ano_base: int
        +estatisticas: DataFrame
        +avisos: tuple
    }
    class SugestoesFinanceira {
        +ano_base: int
        +estatisticas: DataFrame
        +avisos: tuple
    }
    class Sugestao {
        +valor: float
        +origem: str
    }
    class PremissasResolvidas {
        +anos: tuple
        +crescimento: tuple
        +margem_ebitda: tuple
        +da_sobre_receita: float
        +capex_sobre_receita: float
        +nwc_sobre_receita: float
        +arrendamento_sobre_receita: float
        +aliquota: float
        +descontar_arrendamento: bool
        +g_terminal: float
        +cenario: NomeCenario
    }
    class PremissasFinanceiras {
        +anos: tuple
        +roe: tuple
        +payout_inicio: float
        +g_terminal: float
        +cenario: NomeCenario
        +roe_longo_prazo() float
        +payout() tuple
    }

    PremissasEmpresa *-- Ajustes : ajustes
    PremissasEmpresa *-- ConfigProjecao : projecao, se nao_financeira
    PremissasEmpresa *-- ProjecaoFinanceira : projecao, se financeira
    PremissasEmpresa *-- Cenarios : cenarios, se nao_financeira
    PremissasEmpresa *-- CenariosFinanceira : cenarios, se financeira
    PremissasEmpresa *-- Pares : pares
    PremissasEmpresa *-- CustoCapitalEmpresa : custo_capital
    Ajustes "1" o-- "0..*" NaoRecorrenteConfig : nao_recorrentes
    Ajustes ..> AjustesContabeis : ajustes_contabeis()
    AjustesContabeis "1" o-- "0..*" NaoRecorrente : nao_recorrentes
    Ajustes ..> RegraMapeamento : mapeamento_extra
    PlanoContas "1" *-- "1..*" RegraMapeamento : por conta padrão
    ResultadoQA "1" *-- "0..*" Verificacao : verificacoes
    ResultadoQA ..> PlanoContas : qa.verificar(..., plano)
    Sugestoes "1" *-- "12" Sugestao
    SugestoesFinanceira "1" *-- "5" Sugestao
    Sugestoes ..> PremissasResolvidas : projetor.resolver()
    SugestoesFinanceira ..> PremissasFinanceiras : financeira.resolver()
    ConfigProjecao ..> PremissasResolvidas : projetor.resolver()
    ProjecaoFinanceira ..> PremissasFinanceiras : financeira.resolver()
```

- `PremissasEmpresa` aceita **um** dos pares (`ConfigProjecao` + `Cenarios`) ou (`ProjecaoFinanceira` + `CenariosFinanceira`), conforme `tipo_modelo`. O acesso tipado por `projecao_dcf` e outros levanta `ErroConfiguracao` se o tipo estiver errado.
- `PremissasResolvidas` é o **cenário base**; `aplicar_cenario(base, delta, nome)` gera as variantes pessimista e otimista sem alterar o original (`frozen`).
- `Sugestoes` guarda 12 `Sugestao` (crescimento, margem, razões sobre a receita, alíquota e deltas dos cenários); a financeira guarda 5 (ROE de início e fim, payout, g e delta do ROE).

## 5. Custo de capital, modelos e análise (`custo_capital/`, `modelos/`, `analise/`)

```mermaid
classDiagram
    direction LR

    class CustoCapital {
        +data_base: date
        +beta_regressao: float?
        +aliquota: float
        +wacc: float
        +data_balanco: date
        +avisos: tuple
        +kd_liquido() float
    }
    class CustoCapitalFinanceira {
        +data_base: date
        +data_balanco: date
        +avisos: tuple
    }
    class ResultadoBeta {
        +metodo: MetodoBeta
        +beta: float
        +beta_bruto: float?
        +r2: float?
        +n_obs: int?
        +erro_padrao: float?
        +avisos: tuple
    }
    class CustoCapitalProprio {
        +metodo: brl_direto ou usd_crp
        +moeda: BRL ou USD
        +ke: float
        +beta: float
        +erp: float
        +rf: float
        +crp: float
        +ke_usd: float?
    }
    class ResultadoKd {
        +metodo: historico ou manual
        +kd: float
        +kd_bruto: float?
        +anos: tuple
        +piso: float?
        +teto: float?
    }
    class Estrutura {
        +metodo: MetodoEstrutura
        +divida: float
        +equity: float
        +peso_divida: float
        +peso_equity() float
        +divida_sobre_equity() float
    }

    class ItensPonte {
        +divida_bruta: float
        +caixa_e_aplicacoes: float
        +minoritarios: float
        +investimentos: float
        +divida_extra: float
        +acoes: int
        +data_balanco: date
    }
    class ResultadoPonte {
        +ev: float
        +equity: float
        +valor_por_acao: float
    }
    class DadosAvaliacao {
        +historico: DataFrame
        +data_base: date
        +meio_periodo: bool
        +alerta_tv_sobre_ev: float
        +cambio: float
    }
    class ResultadoDCF {
        +fluxos: DataFrame
        +wacc: float
        +g: float
        +ronic: float
        +valor_terminal: float
        +vp_fluxos: float
        +vp_terminal: float
        +ev_ebitda_terminal: float
        +avisos: tuple
        +ev() float
        +tv_sobre_ev() float
    }
    class Avaliacao {
        +projecao: DataFrame
        +cambio: float
        +valor_por_acao() float
        +avisos() tuple
    }

    class DadosDDM {
        +pl_inicial: float
        +acoes: float
        +data_balanco: date
        +data_base: date
    }
    class ResultadoDDM {
        +fluxos: DataFrame
        +ke: float
        +g: float
        +roe_longo_prazo: float
        +pvp_justificado: float
        +vp_dividendos: float
        +vp_terminal: float
        +vp_lucro_residual: float
        +valor() float
        +valor_lucro_residual() float
        +divergencia() float
    }
    class AvaliacaoDDM {
        +projecao: DataFrame
        +acoes: float
        +valor_por_acao() float
        +avisos() tuple
    }

    class Fundamentos {
        +ticker: str
        +market_cap: float
        +lucro_liquido: float
        +ebitda: float
        +ebit: float
        +receita_liquida: float
        +patrimonio_liquido: float
        +fcff: float
        +dividendos: float
        +roe: float
        +ev() float
        +metrica(nome) float
    }
    class ResultadoMultiplos {
        +pares: DataFrame
        +estatisticas: DataFrame
        +implicitos: DataFrame
        +avisos: tuple
        +mediana(nome) float
    }
    class RegressaoPVP

    class Avaliada {
        <<Protocol>>
        +valor_por_acao: float
        +avisos: tuple
    }
    class ResultadoCenarios~A~ {
        +pesos: dict
        +preco: float
        +hurdle: float
        +valor_ponderado: float
        +ke_implicito: float?
        +wacc_implicito: float?
        +preco_maximo_compra() float
        +upside() float
        +avisos() tuple
    }
    class ParametrosPerfil
    class PremissasResolvidas
    class PremissasFinanceiras

    CustoCapital *-- ResultadoBeta : beta
    CustoCapital *-- CustoCapitalProprio : ke
    CustoCapital *-- ResultadoKd : kd
    CustoCapital *-- Estrutura : estrutura
    CustoCapitalFinanceira *-- ResultadoBeta : beta
    CustoCapitalFinanceira *-- CustoCapitalProprio : ke

    DadosAvaliacao *-- ItensPonte : ponte
    ResultadoPonte *-- ItensPonte : itens
    Avaliacao *-- PremissasResolvidas : premissas
    Avaliacao *-- ResultadoDCF : dcf
    Avaliacao *-- ResultadoPonte : ponte
    AvaliacaoDDM *-- PremissasFinanceiras : premissas
    AvaliacaoDDM *-- ResultadoDDM : ddm
    DadosDDM ..> AvaliacaoDDM : ddm.avaliar(premissas, dados, ke)
    DadosAvaliacao ..> Avaliacao : dcf.avaliar(premissas, dados, wacc, ronic)

    Fundamentos *-- ItensPonte : itens
    ResultadoMultiplos *-- Fundamentos : alvo
    ResultadoMultiplos o-- "0..1" RegressaoPVP : regressao

    Avaliacao ..|> Avaliada
    AvaliacaoDDM ..|> Avaliada
    ResultadoCenarios "1" o-- "1..3" Avaliada : avaliacoes por cenario
    ResultadoCenarios o-- ParametrosPerfil : perfil
```

- `ResultadoCenarios` é **genérico** no tipo da avaliação (`Avaliada`): o mesmo código pondera cenários de DCF e de DDM. Com os três cenários os pesos são os do perfil; com um só (`--cenario X`), 1.
- `ItensPonte` é compartilhado pela ponte do DCF e pelos múltiplos: o EV dos múltiplos é o **inverso** da ponte (`Fundamentos.ev`).
- Moeda: tudo fica na moeda de reporte até `valor_por_acao`, que sai em BRL (`cambio`). `CustoCapitalFinanceira` não tem Kd nem estrutura: financeiras só têm Ke.

## 6. Saídas, carteira e orquestração (`saida/`, `carteira/`, `cli.py`)

```mermaid
classDiagram
    direction LR

    class CenarioSaida {
        +valor_por_acao: float
        +fluxos: DataFrame
        +projecao: DataFrame
        +vp_fluxos: float
        +vp_terminal: float
        +valor_terminal: float
        +taxa: float
        +g: float
        +ponte: DataFrame?
        +para_real(...) DataFrame
    }
    class FluxosCenario {
        +fluxos: DataFrame
        +valor_terminal: float
        +taxa_desconto: float
        +g: float
        +valor_por_acao: float
    }
    class IpcaProjetado {
        +por_ano: Mapping
        +ipca_12m: float
        +taxa(ano) float
    }
    class Faixa {
        +rotulo: str
        +minimo: float
        +maximo: float
        +ponto: float?
        +aviso: bool
    }
    class ResumoFavorito {
        +ticker: str
        +data_base: date
        +perfil: str
        +preco: float?
        +valor_ponderado: float?
        +preco_maximo_compra: float?
        +upside: float?
        +n_avisos: int
        +idade_dias(hoje) int
    }
    class Termo {
        +chave: str
        +sigla: str
        +nome: str
        +grupo: str
        +definicao: str
        +formula: str
        +interpretacao: str
    }

    class Transacao {
        +data: date
        +ticker: str
        +tipo: TipoTransacao
        +quantidade: float
        +preco: float?
        +valor: float
        +taxas: float
        +observacao: str
    }
    class TipoTransacao {
        <<enumeration>>
        compra
        venda
        provento
        agrupamento
        desdobramento
        bonificacao
    }

    class _Execucao {
        <<cli>>
        +base: date
        +hoje: date
        +agora: datetime
        +cenarios: tuple
        +referencia: NomeCenario
        +forcar: bool
        +graficos: bool
        +explicar: bool
    }
    class _Padronizada {
        <<cli>>
        +moeda: str
        +caminho_premissas: Path
        +ajustes: AjustesContabeis
    }
    class _Mercado {
        <<cli>>
        +precos: dict
        +avisos: list
    }
    class _Par {
        <<cli>>
    }
    class _Comparaveis {
        <<cli>>
        +avisos: tuple
    }

    class Avaliacao
    class AvaliacaoDDM
    class YFinanceProvider
    class Empresa
    class PlanoContas
    class PremissasEmpresa
    class MarketCap
    class Macro
    class Validado
    class Fundamentos
    class PerfilEfetivo

    Transacao *-- TipoTransacao : tipo
    CenarioSaida ..> Avaliacao : cenario_dcf(av)
    CenarioSaida ..> AvaliacaoDDM : cenario_ddm(av)
    CenarioSaida ..> FluxosCenario : real.tabela
    FluxosCenario ..> IpcaProjetado : deflaciona com

    _Padronizada o-- Empresa : empresa
    _Padronizada o-- PlanoContas : plano
    _Padronizada o-- PremissasEmpresa : premissas
    _Mercado o-- Empresa : empresa
    _Mercado o-- MarketCap : cap
    _Mercado o-- Macro : macro
    _Mercado o-- "1..*" Validado : precos e ibov
    _Mercado o-- YFinanceProvider : yf
    _Par *-- _Padronizada : padronizada
    _Par o-- MarketCap : cap
    _Par o-- Fundamentos : fundamentos
    _Comparaveis "1" *-- "0..*" _Par : pares
    _Execucao o-- PerfilEfetivo : efetivo
```

- As classes `_Execucao`, `_Padronizada`, `_Mercado`, `_Par` e `_Comparaveis` são **privadas de `cli.py`**: agrupam o que o comando `rodar` carrega entre as etapas. Nenhuma camada inferior as conhece.
- `CenarioSaida` uniformiza DCF e DDM para a camada de saída (`ponte` só existe no DCF).
- `Transacao` é a única classe da carteira; as etapas C2 a C6 (posição, preço médio, proventos, alocação) ainda não existem (ADR 0020).

## 7. Exceções de domínio

Cada camada tem a sua exceção em português, definida no `__init__.py` do pacote (ou no módulo, em `data/` e `config`). Todas derivam de `Exception`, menos `ErroCarteira`, que deriva de `ValueError` e guarda `erros` (uma mensagem por linha inválida).

```mermaid
classDiagram
    direction TB

    class Exception {
        <<builtin>>
    }
    class ValueError {
        <<builtin>>
    }
    class ErroDownload["ErroDownload · data.http"]
    class ArquivoNaoEncontrado["ArquivoNaoEncontrado · data.http"]
    class ErroDadosExternos["ErroDadosExternos · data.validacao"]
    class ErroPrecos["ErroPrecos · data.precos"]
    class ErroCadastro["ErroCadastro · data.cadastro"]
    class ErroDadosCVM["ErroDadosCVM · data.cvm"]
    class ErroConfiguracao["ErroConfiguracao · config"]
    class ErroContabil["ErroContabil · contabil"]
    class ErroPerfil["ErroPerfil · perfil"]
    class ErroProjecao["ErroProjecao · projecao"]
    class ErroCustoCapital["ErroCustoCapital · custo_capital"]
    class ErroModelo["ErroModelo · modelos"]
    class ErroCarteira["ErroCarteira · carteira"] {
        +erros: list
    }

    Exception <|-- ErroDownload
    ErroDownload <|-- ArquivoNaoEncontrado
    Exception <|-- ErroDadosExternos
    ErroDadosExternos <|-- ErroPrecos
    Exception <|-- ErroCadastro
    Exception <|-- ErroDadosCVM
    Exception <|-- ErroConfiguracao
    Exception <|-- ErroContabil
    Exception <|-- ErroPerfil
    Exception <|-- ErroProjecao
    Exception <|-- ErroCustoCapital
    Exception <|-- ErroModelo
    Exception <|-- ValueError
    ValueError <|-- ErroCarteira
```

Os comandos da CLI capturam o conjunto relevante e o transformam em mensagem em PT-BR com saída 1 (`_erro`); `ErroCarteira` usa `_erro_carteira`, que imprime uma linha por erro.
