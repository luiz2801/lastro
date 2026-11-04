# Guia Metodológico: Tratamento de Anomalias no P/L em Valuation por Múltiplos

Este documento estabelece o protocolo padronizado para identificação, tratamento e eliminação de anomalias (*outliers*) no múltiplo Preço/Lucro ($P/L$ ou $P/E$) em análises de valuation relativas por empresas comparáveis (*peer group*).

---

## 1. Regra Fundamental: Separação de Etapas

O tratamento de anomalias não deve ser feito em um único filtro. A metodologia correta exige **duas etapas distintas**:

$$\text{Amostra Bruta} \xrightarrow[\text{Qualitativo/Financeiro}]{\text{Etapa 1: Regra de Negócio}} \text{Amostra Válida ($P/L > 0$)} \xrightarrow[\text{Estatístico}]{\text{Etapa 2: Filtro IQR}} \text{Amostra Final}$$

---

## 2. Etapa 1: Filtro de Negócio (Corte do P/L Negativo)

### Ação Recomendada
**Remover imediatamente todas as empresas com $P/L \le 0$** antes de realizar qualquer cálculo estatístico.

### Justificativa Financeira
* **Ausência de Sentido Econômico:** O P/L mede quantos anos o investidor leva para recuperar o capital investido com base nos lucros atuais. Um $P/L = -10\text{x}$ não significa recuperação em $-10$ anos.
* **Quebra de Monotonicidade:** Em múltiplos positivos, quanto menor o $P/L$, "mais barata" é a ação. Em múltiplos negativos, essa ordem se inverte: um $P/L$ de $-5\text{x}$ representa um prejuízo proporcionalmente **maior** do que um de $-50\text{x}$.
* **Distorção Estatística:** Incluir valores negativos puxa a média e a mediana para baixo, falsificando a avaliação do setor.

---

## 3. Etapa 2: Filtro Estatístico de Outliers Positivos

Após remover os valores negativos, aplica-se a filtragem das empresas com múltiplos desproporcionalmente altos.

### Comparativo de Métodos

| Critério | Corte Fixo ($P/L > 100\text{x}$) | Distância Interquartil ($\text{IQR}$) |
| :--- | :--- | :--- |
| **Mecânica** | Define um teto arbitrário (ex: $100\text{x}$ ou $150\text{x}$). | Calcula a dispersão dos quartis da amostra. |
| **Vantagem** | Simples de explicar para leigos e rápido. | **Objetivo, dinâmico e adaptável** à realidade do setor. |
| **Desvantagem** | Ignora a dinâmica setorial (ex: $80\text{x}$ é anomalia em Utilidades Públicas, mas comum em *SaaS*). | Exige um tamanho mínimo de amostra ($n \ge 15$). |

### Como aplicar o Filtro por Distância Interquartil ($\text{IQR}$)

1. Ordene os dados válidos ($P/L > 0$) em ordem crescente.
2. Calcule o Primeiro Quartil ($Q_1$, percentil 25) e o Terceiro Quartil ($Q_3$, percentil 75).
3. Calcule o Intervalo Interquartil:
   $$\text{IQR} = Q_3 - Q_1$$
4. Determine o Limite Superior de corte:
   $$\text{Limite Superior} = Q_3 + 1{,}5 \times \text{IQR}$$
5. **Remova ou ajuste (Winsorize)** qualquer empresa com $P/L > \text{Limite Superior}$.

---

## 4. Técnica Avançada: Ajuste por Assimetria Logarítmica

Múltiplos de valuation costumam apresentar **assimetria acentuada à direita** (muitos valores entre $10\text{x}$ e $25\text{x}$, e alguns valores muito altos de $80\text{x}$ a $200\text{x}$). O IQR simples pode cortar empresas legítimas de alto crescimento nesse cenário.

### Procedimento Recomendado (Log-IQR)

1. Converta os múltiplos válidos para escala logarítmica: $y_i = \ln(P/L_i)$.
2. Aplique a regra do $\text{IQR}$ sobre a variável transformadora $y_i$:
   $$\text{Limite Superior}_{\ln} = Q_{1,y} + 1{,}5 \times \text{IQR}_y$$
3. Retorne o valor para a escala original aplicando a função exponencial:
   $$\text{Corte Final} = e^{\text{Limite Superior}_{\ln}}$$

---

## 5. Escolha da Métrica de Tendência Central

Mesmo após a eliminação de *outliers*, a escolha da métrica final de valuation do setor deve priorizar a **resistência estatística**:

* **Mediana (Recomendada):** É a métrica padrão no mercado de M&A e Investment Banking. Imune a pequenas distorções remanescentes nas pontas da distribuição.
* **Média Winsorizada:** Substitui os valores discrepantes das pontas pelos valores dos limites inferior e superior. Indicada quando a base de dados é pequena e não se quer perder pontos de informação.
* **Média Simples (Evitar):** Muito sensível a resíduos extremos, devendo ser evitada em múltiplos de avaliação.

---

## 6. Resumo / Checklist de Execução

```
[ Início ]
   │
   ▼
[ Passo 1: Filtrar P/L <= 0 ] ──► Armazenar empresas em prejuízo para análise alternativa (ex: EV/Sales)
   │
   ▼
[ Passo 2: Avaliar tamanho da amostra (n) ]
   ├── Se n < 15  ──► Usar Corte Fixo pré-definido pelo setor (ex: 80x ou 100x) + Mediana
   └── Se n >= 15 ──► Aplicar Filtro IQR (ou Log-IQR)
   │
   ▼
[ Passo 3: Calcular Mediana do Setor ]
   │
   ▼
[ Fim: Aplicar Múltiplo ao Ativo Alvo ]
```

---

## 7. O que fazer com as empresas removidas?

As empresas cortadas da análise de P/L não devem ser descartadas do relatório global de valuation:

* **Empresas com $P/L \le 0$:** Avaliar utilizando **$EV/EBITDA$** (se a operação for lucrativa), **$EV/\text{Vendas}$** ($P/S$), ou utilizar o **Forward P/E** ($N+1$ ou $N+2$) com lucro projetado futuro.
* **Empresas com $P/L$ Anômalo Positivo:** Verificar se o múltiplo alto reflete um lucro não recorrentemente baixo no período (efeito contábil temporário) ou se a empresa possui taxa de crescimento de lucros desproporcionalmente alta (neste caso, utilizar o múltiplo **PEG Ratio** — $P/L \div \text{Crescimento}$).