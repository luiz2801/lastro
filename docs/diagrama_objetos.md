# Diagrama de Objetos — Lastro

"Fotografias" do sistema em execução: instâncias das classes do [diagrama de classes](diagrama_classes.md), com valores de atributos e as ligações entre elas. São estáticos; a evolução no tempo está nos diagramas de [sequência](diagrama_sequencia.md), [interação](diagrama_interacao.md) e [estados](diagrama_estados.md). Índice em [`diagramas.md`](diagramas.md).

> **De onde vêm os números.** Nenhum valor de mercado ou contábil aqui é dado real de empresa. O cenário da seção 1 é o **sintético dos testes** (`tests/test_dcf.py`, `tests/test_cenarios.py`), de uma companhia fictícia `XPTO3`; os valores foram obtidos **instanciando os objetos com o próprio código** (`dcf.avaliar` e `cenarios.analisar`), não digitados à mão. Os da seção 2 vêm do esquema do JSON do perfil no `CLAUDE.md` (seção 8.3), e os da seção 3 são só cadastro (CNPJ, `CD_CVM` e espécies, registrados em `docs/fontes.md`). Os da seção 4 são ilustrativos.

> **Notação.** O Mermaid não tem diagrama de objetos; é desenhado como `flowchart`. Cada caixa é uma instância, com o nome sublinhado no formato `nome : Classe`, os valores dos atributos e as ligações (*links*) rotuladas com o papel. Objetos anônimos aparecem como `: Classe`. Quando a classe tem coleção, os elementos aparecem individualmente (o Mermaid não desenha *MultiObjects* empilhados).

## 1. Resultado de `valuation rodar XPTO3` (DCF, perfil moderado)

Estado ao fim de `cenarios.analisar`, com a data-base em 31/12/2025, preço de mercado R$ 10,00 e Selic de 15%: o `CustoCapital`, os dados da avaliação, os três cenários e o resultado ponderado.

```mermaid
flowchart TB
    perfil["<u><b>efetivo : PerfilEfetivo</b></u><hr/>perfil = moderado<br/>origem = questionario"]
    params["<u><b>moderado : ParametrosPerfil</b></u><hr/>margem_seguranca = 0,20<br/>peso_pessimista = 0,25<br/>peso_base = 0,50<br/>peso_otimista = 0,25<br/>horizonte_anos = 7<br/>hurdle_spread_selic = 0,05"]

    res["<u><b>r : ResultadoCenarios</b></u><hr/>preco = 10,00<br/>hurdle = 0,20<br/>valor_ponderado = 17,34<br/>preco_maximo_compra = 13,87<br/>upside = 0,734<br/>ke_implicito = 0,2027<br/>wacc_implicito = 0,1685"]

    cc["<u><b>cc : CustoCapital</b></u><hr/>data_base = 2025-12-31<br/>aliquota = 0,34<br/>wacc = 0,1065<br/>data_balanco = 2025-12-31"]
    beta["<u><b>: ResultadoBeta</b></u><hr/>metodo = manual<br/>beta = 1,0"]
    ke["<u><b>: CustoCapitalProprio</b></u><hr/>metodo = brl_direto<br/>moeda = BRL<br/>ke = 0,12<br/>beta = 1,0<br/>erp = 0,05<br/>rf = 0,07"]
    kd["<u><b>: ResultadoKd</b></u><hr/>metodo = manual<br/>kd = 0,10"]
    est["<u><b>: Estrutura</b></u><hr/>metodo = manual<br/>divida = 25<br/>equity = 75<br/>peso_divida = 0,25"]

    dados["<u><b>dados : DadosAvaliacao</b></u><hr/>data_base = 2025-12-31<br/>meio_periodo = falso<br/>alerta_tv_sobre_ev = 0,75<br/>cambio = 1"]
    itens["<u><b>itens : ItensPonte</b></u><hr/>divida_bruta = 300<br/>caixa_e_aplicacoes = 100<br/>minoritarios = 50<br/>investimentos = 20<br/>divida_extra = 10<br/>acoes = 100<br/>data_balanco = 2025-12-31"]

    pess["<u><b>pessimista : Avaliacao</b></u><hr/>premissas.cenario = pessimista<br/>valor_por_acao = 12,59<br/>dcf.ev = 1.499,08"]
    base["<u><b>base : Avaliacao</b></u><hr/>premissas.cenario = base<br/>valor_por_acao = 17,27"]
    otim["<u><b>otimista : Avaliacao</b></u><hr/>premissas.cenario = otimista<br/>valor_por_acao = 22,25<br/>dcf.ev = 2.464,58"]

    dcf["<u><b>: ResultadoDCF</b></u> (da base)<hr/>wacc = 0,1065<br/>g = 0,05<br/>ronic = 0,1065<br/>vp_fluxos = 339,06<br/>vp_terminal = 1.627,63<br/>ev = 1.966,70<br/>tv_sobre_ev = 0,828<br/>ev_ebitda_terminal = 5,75"]
    ponte["<u><b>: ResultadoPonte</b></u> (da base)<hr/>ev = 1.966,70<br/>equity = 1.726,70<br/>valor_por_acao = 17,27"]
    prem["<u><b>: PremissasResolvidas</b></u> (da base)<hr/>anos = (2026, 2027)<br/>crescimento = (0,10; 0,05)<br/>margem_ebitda = (0,30; 0,30)<br/>capex_sobre_receita = 0,05<br/>aliquota = 0,30<br/>g_terminal = 0,05"]

    res -->|"perfil"| params
    res -->|"avaliacoes[pessimista]"| pess
    res -->|"avaliacoes[base]"| base
    res -->|"avaliacoes[otimista]"| otim
    perfil -.->|"define"| params
    cc ---|"beta"| beta
    cc ---|"ke"| ke
    cc ---|"kd"| kd
    cc ---|"estrutura"| est
    dados ---|"ponte"| itens
    base ---|"dcf"| dcf
    base ---|"ponte"| ponte
    base ---|"premissas"| prem
    ponte ---|"itens"| itens
    cc -.->|"wacc usado em"| dcf

    classDef obj fill:#fff8e1,stroke:#f08c00,color:#1a1a1a
    class perfil,params,res,cc,beta,ke,kd,est,dados,itens,pess,base,otim,dcf,ponte,prem obj
```

Conferência dos números (cálculo à mão, igual aos testes):

- `wacc` = Ke × E/(D+E) + Kd × (1 − t) × D/(D+E) = 0,12 × 0,75 + 0,10 × 0,66 × 0,25 = **0,1065**.
- `equity` (base) = EV 1.966,70 − dívida 300 + caixa 100 − minoritários 50 + investimentos 20 − `divida_extra` 10 = **1.726,70**; por ação (100 ações) = **17,27**.
- `valor_ponderado` = 0,25 × 12,59 + 0,50 × 17,27 + 0,25 × 22,25 = **17,34**; `preco_maximo_compra` = 17,34 × (1 − 0,20) = **13,87**; `hurdle` = Selic 0,15 + 0,05 = **0,20**.
- As caixas `: ResultadoDCF`, `: ResultadoPonte` e `: PremissasResolvidas` são anônimas e pertencem à `base`; as dos outros dois cenários têm a mesma forma e foram omitidas.
- Relações do diagrama de classes que aparecem como *links*: `ResultadoCenarios *-- Avaliada` (aqui, três `Avaliacao`), `Avaliacao *-- ResultadoDCF | ResultadoPonte | PremissasResolvidas`, `CustoCapital *-- ...` e a **ponte compartilhada** (`itens` é o mesmo objeto nos dados e no resultado da ponte).

## 2. Perfil gravado em disco

O JSON de `perfil/perfil_investidor.json` e os objetos que `reg.ler` reconstrói. O `RegistroPerfil` guarda o **número da alternativa** escolhida; a pontuação e o perfil são recalculados na leitura e, se não baterem com o arquivo, o arquivo é recusado.

```mermaid
flowchart LR
    json[("perfil_investidor.json<br/>(arquivo)")]
    reg["<u><b>registro : RegistroPerfil</b></u><hr/>versao_questionario = 1<br/>data = 2026-10-30<br/>valido_ate = 2027-10-30<br/>respostas = {q1: 3, q2: 4, ...}<br/>pontuacao = 31<br/>vetos_aplicados = ()<br/>perfil = moderado"]
    cls["<u><b>: Classificacao</b></u><hr/>pontuacao = 31<br/>perfil = moderado<br/>vetos_aplicados = ()"]
    efetivo["<u><b>efetivo : PerfilEfetivo</b></u><hr/>perfil = moderado<br/>origem = questionario"]
    over["<u><b>efetivo_cli : PerfilEfetivo</b></u><hr/>perfil = arrojado<br/>origem = override<br/>registro = nulo"]

    json -->|"reg.ler"| reg
    reg -.->|"recalcula e confere"| cls
    efetivo -->|"registro"| reg
    over -.->|"--perfil arrojado<br/>(sem arquivo)"| json

    classDef obj fill:#fff8e1,stroke:#f08c00,color:#1a1a1a
    classDef arq fill:#e9ecef,stroke:#868e96,color:#1a1a1a
    class reg,cls,efetivo,over obj
    class json arq
```

31 pontos cai na faixa 25 a 37 (moderado) e não há veto. `valido_ate` = `data` + 12 meses. O segundo `PerfilEfetivo` mostra o caso em que o investidor passa `--perfil arrojado`: o arquivo nem é lido, o `registro` é nulo e a origem é `override` (registrada no `meta.json`).

## 3. Cadastro de uma empresa com duas classes de ação

Exemplo do que a aula chama de *MultiObjects*: uma `Empresa` com vários `ClasseAcao`. Só dados de cadastro (nenhum valor financeiro).

```mermaid
flowchart TB
    emp["<u><b>petrobras : Empresa</b></u><hr/>cnpj = 33.000.167/0001-01<br/>cd_cvm = 9512<br/>tipo_modelo = nao_financeira"]
    on["<u><b>: ClasseAcao</b></u><hr/>ticker = PETR3<br/>especie = ON"]
    pn["<u><b>: ClasseAcao</b></u><hr/>ticker = PETR4<br/>especie = PN"]
    cap["<u><b>cap : MarketCap</b></u><hr/>valor = soma de acoes x preco<br/>das duas classes"]
    cm_on["<u><b>: ClasseMarketCap</b></u><hr/>ticker = PETR3<br/>especie = ON"]
    cm_pn["<u><b>: ClasseMarketCap</b></u><hr/>ticker = PETR4<br/>especie = PN"]

    emp -->|"classes[0]"| on
    emp -->|"classes[1]"| pn
    cap -->|"classes[0]"| cm_on
    cap -->|"classes[1]"| cm_pn
    cap -.->|"market_cap(empresa, ...)"| emp
    cm_on -.->|"mesmo ticker"| on
    cm_pn -.->|"mesmo ticker"| pn

    classDef obj fill:#fff8e1,stroke:#f08c00,color:#1a1a1a
    class emp,on,pn,cap,cm_on,cm_pn obj
```

`empresa_por_ticker` agrupa por CNPJ: pedir `PETR3` ou `PETR4` devolve a mesma empresa. O valor por ação do `rodar` vale para todas as classes (aproximação documentada no `CLAUDE.md`, seção 11.2). Este cadastro vem do FCA da CVM, ajustado por `config/cadastro_manual.csv`.

## 4. Carteira: histórico de transações

Três transações sucessivas de `XPTO3` (valores ilustrativos), como `carteira/transacoes.csv` as guarda. A quantidade em carteira **não é um objeto persistido**: `validar_historico` a reproduz por data, e é por ela que uma venda acima da posição é recusada.

```mermaid
flowchart LR
    t1["<u><b>t1 : Transacao</b></u><hr/>data = 2026-01-15<br/>ticker = XPTO3<br/>tipo = compra<br/>quantidade = 100<br/>preco = 10,00<br/>valor = 1.000,00<br/>taxas = 5,00"]
    t2["<u><b>t2 : Transacao</b></u><hr/>data = 2026-03-02<br/>ticker = XPTO3<br/>tipo = desdobramento<br/>quantidade = 2 (fator)<br/>preco = nulo<br/>valor = 0"]
    t3["<u><b>t3 : Transacao</b></u><hr/>data = 2026-05-20<br/>ticker = XPTO3<br/>tipo = venda<br/>quantidade = 50<br/>preco = 6,00<br/>valor = 300,00"]
    p1(["posição após t1<br/>100 ações"])
    p2(["posição após t2<br/>200 ações"])
    p3(["posição após t3<br/>150 ações"])

    t1 -->|"precede"| t2
    t2 -->|"precede"| t3
    t1 -.-> p1
    t2 -.-> p2
    t3 -.-> p3
    p1 --> p2 --> p3

    classDef obj fill:#fff8e1,stroke:#f08c00,color:#1a1a1a
    classDef calc fill:#e9ecef,stroke:#868e96,color:#1a1a1a
    class t1,t2,t3 obj
    class p1,p2,p3 calc
```

Se `t3` pedisse 250 ações, a posição de 200 não bastaria e `acrescentar` recusaria tudo, sem gravar nada, citando a linha. O desdobramento 2:1 dobra a posição; `valor` e `taxas` não se aplicam a eventos.
