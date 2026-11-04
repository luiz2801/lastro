# ADR 0024 — Sprint GUI 2: indicadores, médias em série, cache derivado e perfil na tela

- **Data:** 2026-11-04
- **Status:** aceito

## Contexto

A GUI 1 deixou pendentes indicadores do catálogo, médias de grupo em série, navegação, perfil na tela e
desempenho. O usuário recebeu as opções em uma rodada e delegou: "aplique de acordo com o que você achar
melhor e justifique". As decisões abaixo são portanto as recomendações do agente, com o motivo.

O que a fonte real desmentiu (conferido em 2026-11-04 nas 65 não financeiras do universo):

- **`passivo_total` (conta 2) inclui o PL:** é igual ao ativo. "Passivo total ÷ ativo", como o catálogo
  propunha, daria 100% sempre.
- **Despesas financeiras (3.06.02) zeradas com resultado financeiro diferente de zero:** MOTV3 e USIM5
  desde 2023, SBSP3 desde 2024, TIMS3 e ASAI3 (estas por causa do item seguinte).
- **TIMS3 com o consolidado inteiro zerado em 2024 e 2025;** o individual tem os valores (ativo de R$ 56 bi).
- **ASAI3 com demonstrações só até 2020** (cd_cvm 25372): desde 2021 só há individual, e o sistema só lia o consolidado.
- **Série histórica de quase ninguém em disco:** 68 de 74 tickers sem a composição antiga.
- **IF.data:** metadados e lista de relatórios respondem, os dados deram HTTP 500 em todas as tentativas.

Medição da primeira abertura, só cálculo: PETR4 4,3 s, WEGE3 8,1 s. Normalizar o texto de cada conta 37
vezes, agrupar por período com pandas e pivotar a tabela inteira 137 vezes respondiam pela maior parte.

## Decisão

**E. Desempenho, sem mudar nenhum número** (comparação exata com a referência em 7 empresas e 12 medidas).
Normalização memoizada, soma por período vetorizada, LTM da série só com as datas que usa, e cache em disco
de séries e medidas em `data/processed/cvm/{cd_cvm}/derivados/`. A chave leva arquivos de entrada, settings,
cadastro e o hash do código do cálculo, para uma fórmula nova invalidar o cache sozinha. Motivo: `st.cache_data`
some ao reiniciar o servidor, e a linha do Ibovespa recalcularia 70 empresas.

**A. Indicadores das não financeiras.**
1. Dívida com arrendamento conforme `ajustes.ifrs16`: é a base da ponte e de Dívida líquida/EBITDA. Dois
   conceitos de dívida na mesma tela confundiriam (PETR4: 0,76 com, 0,28 sem).
2. PL total: a dívida é consolidada, e a controladora misturaria bases. PL ≤ 0 = "—" com o motivo.
3. Cobertura de juros = EBIT ajustado ÷ despesas financeiras da DRE: a mesma base de EBIT do EV/EBIT, e a
   mesma despesa do Kd (ADR 0007). A despesa inclui variação cambial e juros de arrendamento, o que fica dito
   no glossário. Os juros pagos da DFC dependem de regex frágil (60 de 65 companhias).
4. Despesa zerada = "—" com o motivo, sem cair no resultado financeiro líquido: líquido não é despesa.
5. Liquidez imediata e caixa/dívida CP com `caixa_e_aplicacoes` e dívida CP com arrendamento CP, os mesmos
   da dívida líquida.
6. Passivos/Ativos = (PC + PNC) ÷ ativo; PL/Ativos = PL total ÷ ativo.
7. Liquidez geral entra, com a conta nova `realizavel_lp` (1.02.01), que só acrescenta linhas.
8. Conversão de caixa entra (CFO ÷ EBITDA ajustado; (CFO - capex) ÷ lucro da controladora). Custo médio da
   dívida fica fora: o Kd é limitado por faixa, e a série mostraria o limite em vez do custo.
9. Classes: Tukey para dívidas/PL, dívidas/EBITDA e EBIT, cobertura e conversão; só marcar para liquidez,
   Passivos/Ativos, PL/Ativos, perfil da dívida, caixa/dívida CP e caixa/ativo; nenhuma para caixa em R$. Nenhum
   corte fixo novo: os dois tratamentos não o usam.
10. Grade por grupo (Hoje | Histórico) e gráfico anual + LTM com seletor, sem o qual a anomalia não aparece.
11. Financeiras não ganham indicador novo (`REGRAS_CONTABIL.md`). Basileia = "—" com o motivo, até validar a fonte.
12. EV/Receita, EV/FCF e ROA seguem fora: não estavam no escopo pedido.

**B. Médias em série.**
1. Corte transversal por mês, com o LTM vigente de cada empresa e o filtro de hoje (corte fixo com n < 15,
   Log-IQR com n ≥ 15). A estatística segue o seletor da tela. Motivo: mesma regra do valor de hoje.
2. Mês com menos de `multiplos.min_pares` empresas válidas é lacuna, com o n no tooltip: mediana de duas
   empresas não é média de setor.
3. Ibovespa com a carteira de hoje, sem ponderar, rotulado "empresas do Ibovespa de hoje": não há composição
   histórica gratuita, e o viés de sobrevivência fica dito na tela.
4. Dados que faltam só no botão "Baixar séries dos pares", fora de "Atualizar", que seguiria lento para
   sempre. A linha usa quem está em disco e mostra "k de m".
5. Balanço com mais de `multiplos.defasagem_max_meses` (12) sai das médias de grupo, com o motivo: um múltiplo
   com lucro de 2020 não representa a empresa hoje. **Muda a média de hoje** de grupos com ASAI3.

6. Último mês parcial sai: as cotações em disco terminam em datas diferentes (85 de 97 tickers em 30/10, 12 depois), e um
   novembro com 4 de 64 empresas não é o Ibovespa, mesmo acima do mínimo. Vale só para o último mês, se menos da metade
   das empresas do mês anterior já tem cotação nele.
7. Empresas com ON e PN no universo (PETR3 e PETR4, BBDC3 e BBDC4) contam duas vezes no Ibovespa, como já contam no valor de
   hoje. Mudar um sem o outro quebraria a conferência entre os dois.

**C. Navegação.** Barra lateral em todas as páginas (nativa, recolhe no celular) com busca, Início e Perfil.
Busca só no universo, com o nome. ★/☆ no cabeçalho e "remover" no início, mesma validação da CLI, sem confirmação
(é reversível) e sem download ao favoritar.

**D. Perfil.** Questionário sem resposta pré-marcada, grava só com todas respondidas e substitui o JSON, como a
CLI. O override vale na sessão e nunca toca o JSON. O ponderado não é refeito na tela porque o perfil muda o horizonte,
e o horizonte muda o valor de cada cenário: a tela avisa e oferece "Rodar com perfil X", que sobrescreve a pasta do dia.

**F. Dados com defeito.** Família e período com o consolidado zerado ou ausente usam o individual, com aviso. **Muda
os números também no `rodar`** de TIMS3, ASAI3 e SBSP3; comparadas as contas de todo o universo, as outras 71 não mudam.
Na DRE individual não há atribuição, então o lucro da controladora cai no 3.11 (a mesma regra das financeiras).
A proposta original para a ASAI3 era só investigar. A investigação mostrou a mesma causa: desde 2021 a Sendas só publica
o individual, e os dados dela paravam em 2020. A mesma regra resolve os dois casos.

## Consequências

- Pasta nova `derivados/`, apagável a qualquer momento. Conta nova `realizavel_lp` em `contas_padronizadas.parquet`.
- Parâmetro novo `multiplos.defasagem_max_meses`. Comando novo `series-varios`.
- KLBN11 fica fora das médias: nenhuma classe ON/PN com preço (o papel cotado é a unit). Não investigado.
- O Kd histórico das companhias com despesa zerada não foi conferido nem alterado.
- ALOS3 guarda as debêntures em Outras Obrigações: a dívida mapeada é só arrendamento. Os indicadores novos mostram "—";
  o `rodar` e a Dívida líquida/EBITDA seguem como estavam, porque corrigir mudaria o valuation e pede decisão.
- Basileia depende de o IF.data voltar a responder; sem isso, nenhum adaptador.
