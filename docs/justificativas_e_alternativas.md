# Justificativas e alternativas do valuation

> Estado em 2026-10-30 (Fases 0 a 10 concluídas). Complementa o [`CLAUDE.md`](../CLAUDE.md)
> (especificação), o [`guia.md`](../guia.md) (mapa do código) e os [ADRs](decisoes/README.md)
> (registro de cada decisão). Aqui o foco é outro: **por que cada escolha foi feita e o que mudar
> para fazer uma análise diferente**. Estudo pessoal; não é recomendação de investimento.

## Como ler

Cada seção tem uma tabela **Decisão → Por quê → Alternativas**. A coluna de alternativas marca o
que custa implementar:

| Marca | Significado |
|---|---|
| **[config]** | Já funciona editando `settings.yaml`, o YAML da empresa ou `setores.yaml`. Sem código |
| **[código]** | Extensão pequena e localizada; segue o `CONTRIBUTING.md` (teste à mão, `guia.md`) |
| **[ADR]** | Muda uma regra de negócio; precisa de decisão sua e de ADR antes |
| **[fase]** | Já está no roadmap ou no [`backlog.md`](backlog.md) |

Origem das decisões: **[U]** = você decidiu, **[P]** = premissa que adotei e que você pode rever,
**[D]** = imposto pelos dados (a fonte real desmentiu o guia).

---

## 1. Escopo e arquitetura

| Decisão | Por quê | Alternativas |
|---|---|---|
| **[U]** Uma empresa por execução; a base de dados já cobre o universo | Valuation exige revisar premissas de cada empresa; lote sem revisão gera número sem sentido | Modo em lote/screening **[fase]** (Fase 11, só se pedir). Hoje `atualizar --tudo` baixa as 76 do Ibovespa, mas só `rodar` por ticker avalia |
| **[U]** Duas famílias de modelo: FCFF (não financeiras) e DDM/lucro residual (financeiras) | Em banco, dívida é matéria-prima e FCFF não faz sentido | Tratar banco por múltiplos apenas (P/L, P/VP) **[config]**: já sai no `comparar` se o plano de contas existir (Fase 10) |
| **[U]** Somente fontes gratuitas, sem consenso de analistas | Reprodutível e sem custo; projeção depende do histórico e do seu julgamento | Consenso/estimativas pagas **[ADR]**: o g de curto prazo e a margem poderiam vir de fora, ancorando o 1º ano |
| **[U]** Saída em CSV e PNG, sem Excel | Auditável em Git e abre no LibreOffice | Planilha com fórmulas **[ADR]** (decisão 14: rejeitada) |
| **[P]** Camadas `data → contabil → projecao → custo_capital → modelos → analise → saida`; núcleo em funções puras | Trocar fonte ou modelo sem tocar no resto; milhares de execuções para sensibilidade | — |
| **[P]** Dinheiro em unidades da moeda; `data_base` sempre parâmetro | Evita erro de escala (mil × unidade) e permite reproduzir uma análise passada | `--data-base` com data passada **[config]**: reavalia como se fosse aquele dia (cuidado: reapresentações posteriores da CVM entram nos dados baixados) |
| **[U]** Nominal como resultado principal; real (IPCA) como relatório complementar | Fluxos e taxa nominais são consistentes; real é só leitura | Relatório em valores reais **[fase]** (Fase 9). Valuation todo em termos reais (fluxo real, taxa real) **[ADR]** |

---

## 2. Dados

| Decisão | Por quê | Alternativas |
|---|---|---|
| **[D]** CVM (DFP/ITR/FCA/composição) como fonte contábil; 10 anos de DFP e 2 de ITR | Única fonte oficial e gratuita com conta a conta | Dados de terceiros (Economatica, Fundamentus) **[ADR]**: mais limpos, porém pagos ou não oficiais |
| **[D]** Reapresentação: por família e período vale o documento mais recente, e todas as contas dele (ADR 0005) | Corrige sinais e reclassificações (ex.: Vale 2022). Misturar versões soma contas incoerentes | Manter a 1ª versão publicada **[código]**: útil para ver o que o mercado viu na época |
| **[D]** Vale avaliada em BRL (`brl_direto`) (ADR 0002) | A CVM publica a Vale em `REAL`; converter para USD distorce moeda funcional e hedge | `usd_crp` já implementado **[config]**, só testado com dados sintéticos. Usar 20-F em USD **[ADR]** |
| **[D]** Ações: `escala_acoes` no cadastro manual + correção automática (ADR 0003) | A composição do capital não tem coluna de escala; 27 companhias publicam em milhares | Checagem automática contra a quantidade teórica da B3 **[código]** (hoje feita à mão, razão ≈ 1–10 certa, ≈ 0,001 em milhares) |
| **[P]** Preço por yfinance, conferido com brapi; macro por SGS/Tesouro/Focus, cada dado numa segunda fonte (ADR 0004) | Fonte gratuita erra e sai do ar; divergência vira **aviso**, não erro nem correção silenciosa | Token da brapi **[config]** (`BRAPI_TOKEN`) amplia a validação além de 4 tickers. Outra fonte de preço **[código]**: basta satisfazer `PrecosProvider` |
| **[P]** Rf = NTN-F de ~10 anos (nominal), conferida com NTN-B + Focus | Prefixado nominal combina com fluxo nominal e já embute o risco soberano | Rf manual **[config]** (`rf_brl.override`); NTN-B real com fluxos reais **[ADR]**; o aviso de divergência dispara hoje por construção (spread de inflação ≈ 3 p.p.) |
| **[P]** Universo = carteira teórica do Ibovespa lida do JSON da B3 (ADR 0010) | Fonte oficial, sem login; renova a cada quadrimestre | Cadastro inteiro da CVM (400+ empresas) **[config]**: trocar o CSV; lista sua colada à mão **[config]** |

---

## 3. Contabilidade padronizada

| Decisão | Por quê | Alternativas |
|---|---|---|
| **[P]** Demonstrações **consolidadas** | O valor da firma inclui as controladas | `ajustes.consolidado: false` **[config]**: individual, útil para holdings ou para ver a controladora isolada |
| **[P]** IFRS 16 como **dívida** + reposição do arrendamento descontada do FCFF | Arrendamento é financiamento; sem a reposição o FCFF fica inflado | `ifrs16: ignorar` **[config]** (EBITDA "pré-IFRS 16" exigiria também tirar o arrendamento do EBITDA **[código]**); `capex_equivalente_arrendamento: false` **[config]** |
| **[P]** EBITDA = EBIT + D&A, a definição das companhias; D&A pela DFC (ADR 0005) | Bate com os releases (83 conferências em `golden`) e é o que volta ao caixa | D&A pela DVA **[config]** via `mapeamento_extra`; EBITDA ajustado por não recorrentes **[config]** (`nao_recorrentes`) |
| **[P]** EBIT ajustado sem equivalência patrimonial; coligadas entram na ponte pelo valor contábil | Evita contar duas vezes o lucro da coligada (no EBIT e no investimento) | `coligadas: manter_no_ebit` **[config]**; coligadas a múltiplo ou a mercado **[código]** |
| **[P]** Alíquota efetiva limitada a [0, nominal 34%]; NOPAT com ela | Alíquota efetiva instável (JCP, incentivos, LAIR negativo) distorce a perpetuidade | `aliquota_imposto: {valor: número}` **[config]**; alíquota marginal por empresa **[config]**; tratar JCP **[ADR]** (dúvida 7, ignorado na v1) |
| **[P]** LTM = exercício + YTD atual − YTD do ano anterior; trimestre = diferença de YTDs | O ITR traz acumulado; ignorar isso é o erro clássico | Anualizar o último trimestre **[código]** (mais reativo, mais ruidoso) |
| **[P]** ΔNWC incremental: (NWC/receita) × Δreceita | Não faz o 1º ano absorver o desvio entre o NWC real e o alvo (ADR 0006) | NWC por nível **[código]**; NWC com prazos médios (PMR/PME/PMP) **[código]** |
| **[P]** Caixa = caixa + aplicações de CP; extras só via YAML | Aplicações de LP, derivativos e títulos variam por empresa | `caixa_extra` / `divida_extra` **[config]** (ex.: títulos da Petrobras, pensão) |

---

## 4. Premissas e projeção

| Decisão | Por quê | Alternativas |
|---|---|---|
| **[U]** `sugerido` (histórico) e sobrescrita manual convivem; o valor sugerido fica em comentário e é recalculado (ADR 0006) | Você revisa antes de confiar; a sugestão nunca é cega | Fixar número ou lista por ano **[config]**; mudar as regras do sugestor **[código + ADR]** (constantes no topo de `sugestor.py`) |
| **[P]** Crescimento inicial = mediana de 5 anos limitada a [−5%, +20%], caindo linearmente ao g terminal | Mediana resiste a outliers; fade linear evita salto na perpetuidade | Curva não linear ou lista **[config]**; crescimento ancorado no LTM/YTD do ano corrente **[código]** (hoje o 1º ano ignora o YTD já divulgado) |
| **[P]** Margem EBITDA ajustada: mediana 5a → média entre mediana 5a e 10a (reversão de metade) | Margens tendem a reverter à média, sem assumir reversão total | Reversão total ou nenhuma **[config]** (`inicio`/`fim` manuais) |
| **[P]** D&A, capex, NWC, arrendamento sobre receita = mediana de 5 anos | Razões simples e estáveis | Capex ligado à expansão (capex > D&A em crescimento) **[config]**; razão sobre ativo imobilizado **[código]** |
| **[P]** Cenários = ±1 desvio-padrão (10a) de crescimento e margem, com piso/teto; capex ±0,5 | Dá amplitude proporcional à volatilidade da própria empresa | Deltas manuais **[config]**; cenários por driver (preço da commodity, câmbio) **[código]** |
| **[P]** Commodity: aviso de que o histórico reflete o ciclo | Mediana de 5 anos de petróleo ou minério não é "normal" | Premissa de preço da commodity e margem normalizada **[config]** (margens manuais) ou módulo de deck de commodities **[fase]** (Fase 11) |
| **[P]** Ano corrente parcial (stub): fluxo restante = dias / 365; ano-ponte sem DFP com fração 0 | A data-base cai no meio do ano; o fluxo já ocorrido está no caixa do balanço | Não usar o stub (data-base em 31/12) **[config]** `--data-base` |
| **[P]** Horizonte = o do perfil (5, 7 ou 10 anos) | Quem tem prazo curto não confia na perpetuidade | `horizonte_anos: N` fixo **[config]**. Observação: o conservador (5 anos) acaba com mais peso no valor terminal |

---

## 5. Custo de capital

| Decisão | Por quê | Alternativas |
|---|---|---|
| **[P]** CAPM `brl_direto`: Ke = Rf (NTN-F) + β × ERP, sem risco-país | A NTN-F já embute o risco soberano; somar de novo conta duas vezes | `usd_crp` **[config]** (Rf USD + β × ERP maduro + CRP, convertido por Fisher); modelo de construção (build-up) com prêmios de tamanho/liquidez **[ADR]** |
| **[U]** ERP = 5,0%, premissa sua, sem fonte externa | Decisão de manter e documentar; ±1 p.p. muda o valor entre 4% e 6,5% (PETR4: +6,5%/−6,0%; VALE3: +4,1%/−3,9%; WEGE3: +4,0%/−3,8%) | ERP de fonte pública (ex.: implícito maduro do Damodaran) **[config]**; **ERP implícito do Ibovespa** **[fase]** (backlog, exige ADR e premissa de g do índice); yield spread do índice só como termômetro (hoje −5,5 p.p., não utilizável como ERP) |
| **[P]** Beta: regressão OLS semanal, 260 semanas, `adj_close`, contra o Ibovespa, classe mais líquida, com Blume (0,67β + 0,33) | Semanal reduz ruído de pregão; Blume puxa o beta à média | Beta de comparáveis (mediana desalavancada pelos pares, realavancada) **[config]** `custo_capital.beta.metodo: comparaveis`; beta manual **[config]**; janela e Blume em `settings`; índice diferente (IBX, S&P) **[código]** |
| **[P]** Kd histórico = mediana de 3 exercícios de despesas financeiras / dívida bruta média, **limitado a Rf + [0, 5 p.p.]** (ADR 0007) | A DRE só tem despesas financeiras totais, que incluem câmbio e correção; sem a faixa saem 7,8% (PETR4) e 44% (WEGE3) | `kd: {metodo: manual, valor}` **[config]**; faixa em `settings.custo_capital.kd`; spread sobre CDI/DI por emissão **[código]**. **Impacto medido:** tirar o piso muda a PETR4 em +17,7% (dívida ≈ 1/3 do capital, Kd cru de 7,8%); VALE3 e WEGE3 variam menos de 3% |
| **[P]** Benefício fiscal pela alíquota **nominal** | O benefício é marginal; a efetiva é distorcida por JCP | Alíquota efetiva **[código]**; JCP explícito **[ADR]** |
| **[P]** Pesos: equity a mercado, dívida bruta contábil do último balanço; `mercado_atual` | Proxy usual; o valor de mercado da dívida não está disponível | `estrutura_alvo: manual` (D/(D+E) fixo, com realavancagem do beta) ou `setor` (mediana dos pares) **[config]**; dívida líquida nos pesos **[código]** |
| **[P]** Erro se WACC ≤ g | A perpetuidade deixa de convergir | — (é regra de consistência, não de preferência) |

---

## 6. DCF, ponte e cenários

| Decisão | Por quê | Alternativas |
|---|---|---|
| **[P]** FCFF = NOPAT + D&A − capex − ΔNWC − reposição de arrendamento | Fluxo da firma, independente da estrutura de capital | FCFE (fluxo ao acionista, descontado a Ke) **[código]**; APV **[ADR]** |
| **[P]** Convenção de meio período, valor terminal descontado no meio do último ano (ADR 0008) | Fluxos entram ao longo do ano; coerente com perpetuidade no meio de cada ano | `dcf.convencao_meio_periodo: false` **[config]** (desconto no fim do ano; valor menor) |
| **[P]** Valor terminal por *value driver*: FCFF = NOPAT × (1 − g/RONIC), **RONIC = WACC** | Crescer sem retorno acima do custo de capital não cria valor; é o conservador | `terminal.ronic: roic_historico` ou número **[config]**; Gordon simples (FCFF × (1+g)) **[código]**; **múltiplo de saída** (EV/EBITDA dos pares) como terminal **[código]**. O g implícito no múltiplo já é calculado no `rodar` |
| **[U]** Teto do g perpétuo nominal = 5,0% | Limite de sanidade (PIB + inflação de longo prazo) | `terminal.g_nominal_max` e `g_nominal` por empresa **[config]**. Com RONIC = WACC o g quase não mexe no valor (é teoria, não bug) |
| **[P]** Ponte EV → equity: dívida bruta (com arrendamento), caixa e aplicações, minoritários contábeis, coligadas pelo contábil, `divida_extra` | Balanço do mesmo dia dos pesos do WACC; tudo auditável | `minoritarios: multiplo_pvp` **[config]** (PL deles × P/VP mediano dos pares); coligadas a valor de mercado **[código]**; pensões e contingências em `divida_extra` **[config]** |
| **[P]** Valor por ação = equity / ações em circulação (ON + PN sem tesouraria), igual para todas as classes | Simples e consistente com o market cap | Diluição (opções, bônus) **[fase]**; prêmio ON × PN (tag along, direitos) **[código + ADR]** |
| **[U]** Três cenários (pessimista/base/otimista) ponderados pelo perfil | Mostra faixa em vez de ponto | `--cenario X` avalia um só **[config]**; mais cenários ou Monte Carlo **[fase]** (Fase 11) |
| **[U]** Retorno esperado em duas leituras: Ke implícito no preço (compara com o hurdle) e WACC implícito | O preço de mercado "paga" que taxa? Sem prever o futuro | TIR do investidor com preço de entrada e saída explícita **[código]** |
| **[P]** Sensibilidades: WACC × g e margem × crescimento (deltas somados a todos os anos) | São os dois vetores que mais movem o DCF | Ke × g, ROE × Ke (financeiras) **[fase]** (Fase 10); eixos em `settings.sensibilidade` **[config]**; tornado por premissa **[código]** |

---

## 7. Múltiplos e comparáveis (Fase 8, ADR 0009 e 0010)

| Decisão | Por quê | Alternativas |
|---|---|---|
| **[U]** Pares por setor: petróleo só E&P; mineração separada da siderurgia (CSNA3 entra na mineração para a VALE3 ter 3 pares); máquinas em lista ampla | Mesmo negócio, mesma dinâmica de margem; a WEG não tem comparável perfeito, então a mediana dilui | `setores.yaml > pares` e `pares.incluir/excluir` por empresa **[config]**; pares internacionais **[ADR]** (sem fonte gratuita) |
| **[P]** Alvo e pares pelo **mesmo pipeline** (LTM do último balanço, market cap na data-base) | Comparar números contábeis diferentes mascara a diferença que se quer medir | — |
| **[P]** EV = market cap + dívida bruta − caixa + minoritários − coligadas + `divida_extra` (inverso da ponte); EBITDA e EBIT ajustados | O valor implícito volta pela mesma ponte; sem inconsistência com o DCF | EV simples (sem coligadas) **[código]**; EBITDA contábil **[config]** (`coligadas: manter_no_ebit`) |
| **[U]** Descartar indefinidos; winsorizar nos percentis 10/90; valor pela **mediana** com faixa P25–P75 | Mediana e quartis resistem aos outliers (P/L de 157x da BRAV3, EV/EBITDA de 207x da TUPY3) | `multiplos.winsorizar` 0/1 desliga **[config]**; média ou média harmônica **[código]** |
| **[P]** Mínimo de 3 pares válidos; abaixo disso, "baixa confiança" (aviso) | Mediana de 2 não é estatística | `multiplos.min_pares` **[config]** |
| **[D]** P/VP abaixo de 0,05 exclui o par (provável erro de escala das ações) | 7 dos 13 pares novos estavam em milhares e distorciam tudo | Corrigir `escala_acoes` **[config]** (aviso aponta o caso) |
| **[P]** Alvo fora da lista de pares do próprio cálculo | Evita circularidade | — |
| **[P]** Os pares também alimentam beta, estrutura de capital e minoritários (opcional) | Um único conjunto de comparáveis, em vez de três listas | Cada uso com lista própria **[código]** |

---

## 8. Perfil do investidor

| Decisão | Por quê | Alternativas |
|---|---|---|
| **[U]** Questionário de 10 perguntas, vetos, JSON válido por 12 meses | Suitability bancário padrão; força revisão periódica | Perguntas ou faixas diferentes **[código]** (`VERSAO_QUESTIONARIO` invalida perfis antigos); `--perfil` como override explícito **[config]** |
| **[U]** O perfil **não** altera fatos contábeis nem o custo de capital da empresa | O valor intrínseco por cenário é o mesmo para todos; o perfil define só o desconto exigido, a ponderação, o horizonte e o hurdle | Ligar o perfil ao ERP ou ao Ke **[ADR]** (não recomendado: o perfil mede tolerância pessoal, não o risco do mercado) |
| **[U]** Margem de segurança 30/20/10%; pesos 40-50-10 / 25-50-25 / 15-50-35; horizonte 5/7/10 anos; hurdle Selic + 3/5/7 p.p. | Valores iniciais aceitos por você em 2026-10-30 | `settings.perfil` **[config]**. Observação: com Selic em 15% o hurdle fica em 18–22%, exigente (PETR4: Ke implícito 16,9% < hurdle moderado 18,75%) |
| **[U]** Saída neutra: "preço de mercado X; acima/abaixo do preço máximo do perfil Y" | Ferramenta de estudo, sem recomendação | Recomendação compra/venda com critérios explícitos **[ADR]** (backlog; conflita com o `CLAUDE.md` hoje) |

---

## 9. Financeiras (Fase 10, ainda não implementado)

| Decisão prevista | Por quê | Alternativas |
|---|---|---|
| DDM em dois estágios (ROE → ROE_LP, payout → 1 − g/ROE_LP), P/VP justificado e checagem pelo lucro residual | Em banco, o patrimônio e o retorno sobre ele são o que importa; dois métodos se auditam | Só múltiplos (P/L, P/VP, regressão P/VP × ROE entre pares) **[config]**; DDM com 3 estágios **[código]** |
| Só Ke (sem WACC), mesma lógica de beta e CAPM | Dívida é operação | — |
| Limitações declaradas: sem Basileia (payout pode violar capital regulatório), lucro contábil em vez do gerencial | Não estão na DFP | Informar o índice de Basileia manualmente no YAML **[código]** |

---

## 10. Análises diferentes: por onde começar

| Quero analisar… | Como |
|---|---|
| O valor se o ciclo da commodity normalizar | Margens e crescimento manuais no YAML **[config]**, ou `--cenario pessimista`/`otimista` |
| Quanto o resultado depende do WACC e de g | Matrizes de `sensibilidade_wacc_g.csv`; mexer em `erp`, `kd` e `terminal.g_nominal_max` em `settings` e reexecutar **[config]** |
| A empresa sem a dívida em arrendamento | `ajustes.ifrs16: ignorar` **[config]** |
| Um terminal mais agressivo ou mais conservador | `terminal.ronic: roic_historico` (mais valor), `g_nominal` menor, ou `convencao_meio_periodo: false` **[config]** |
| Valor relativo (barato ou caro contra os pares) | `valuation comparar TICKER`; ajustar `pares` **[config]** |
| Outro setor de pares ou mais pares | `setores.yaml` + `atualizar --com-pares` **[config]** |
| Outra empresa do Ibovespa | Criar o YAML (`premissas sugerir --escrever`) e um setor em `setores.yaml` **[config]** |
| Beta mais estável | `beta.metodo: comparaveis` ou `manual` **[config]** |
| Foto histórica: o valuation de meses atrás | `--data-base AAAA-MM-DD` **[config]** (ver ressalva na seção 1) |
| Valor em termos reais | Relatório real **[fase]** (Fase 9) |
| Distribuição de resultados, não três cenários | Monte Carlo **[fase]** (Fase 11) |
| Holdings (ITSA4, BRAP4) | SOTP/NAV **[fase]** (Fase 11) |
| Preço teto de dividendos (Bazin) | Backlog ("Métrica de preço teto") **[fase]** |
| Bancos e seguradoras | Fase 10 |
| Tributação de JCP ou diluição | **[ADR]** (dúvida 7; ignorados na v1) |
| Rankear várias empresas | Modo em lote **[fase]** (Fase 11) |

---

## 11. Limitações que afetam a leitura de qualquer resultado

- **O DCF é uma faixa, não um número.** Sempre olhe a sensibilidade WACC × g e os três cenários.
- **Parâmetros de mercado seguem sendo premissas:** ERP (5%) e faixa do Kd (0 a 5 p.p.) são
  escolhas, não medidas. A faixa do Kd não tem decisão final: no PETR4 o piso na Rf sozinho vale
  cerca de 18% do valor.
- **Lucro de ciclo alto:** em commodities (PETR4, VALE3) a mediana de 5 anos pode embutir um ciclo
  favorável. Revise margens à mão.
- **WEGE3 sem comparável próximo:** os múltiplos dos pares (EV/EBITDA ≈ 5x contra 23x da WEG)
  implicam valores muito abaixo do preço; serve de referência, não de âncora.
- **Valor terminal pesa 32% a 50% do EV;** o aviso dispara acima de 75%.
- **Sem diluição, sem diferença entre classes de ação, sem JCP.**
- **Dados gratuitos erram:** a validação cruzada avisa, mas não corrige. As conferências do
  `tests/golden` cobrem os três pilotos, não todo o universo.
- **MBRF3** foi mapeada para a Marfrig pós-incorporação da BRF sem confirmar que a DFP já
  consolida a BRF.
- **Companhias cadastradas só como unit (BPAC11, KLBN11, SANB11)** não têm market cap: o cálculo
  ignora units e não encontra classe ON/PN com preço.
