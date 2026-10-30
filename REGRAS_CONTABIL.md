# REGRAS_CONTABIL.md — Regras para Padronização e QA Contábil

> Instruções modulares para agentes de IA atuando na normalização contábil, reconciliação de demonstrações (DFP/ITR) e planos de contas.
> Escopo: `src/contabil/*.py`, `config/mapeamento_contas.yaml`, `config/setores.yaml` e `config/empresas/*.yaml`.

---

## 1. Princípios Inegociáveis

1. **Dois Pipelines Independentes**:
   - `nao_financeiras`: DFP padrão comercial/industrial (Balanço Patrimonial, DRE, DFC). Métricas-chave: Receita Líquida, Lucro Bruto, EBITDA, EBIT, NOPAT, Dívida Líquida, ROIC, Capital de Giro e CAPEX.
   - `financeiras`: Bancos e seguradoras (ADR 0011). Métricas-chave: Margem Financeira Bruta, Receitas de Prestação de Serviços, PDD (Provisão para Perdas), Resultado Operacional, Lucro Líquido, Patrimônio Líquido, ROE e Índice de Basileia.
   - **Atenção**: **Nunca** tente calcular EBITDA, Dívida Líquida ou ROIC para instituições financeiras; utilize o pipeline financeiro dedicado.
2. **Plano de Contas Declarativo**:
   - Mapeamentos contábeis residem exclusivamente em `config/mapeamento_contas.yaml`.
   - Utilize códigos `CD_CONTA` da CVM (ex: `3.01` para Receita Líquida, `1.01` para Ativo Circulante).
   - Se uma empresa específica utiliza uma conta customizada para ajustes (ex: IFRS 16 ou itens não recorrentes), configure a exceção em `config/empresas/<TICKER>.yaml`, nunca com *hardcode* em `src/contabil/`.
3. **IFRS 16 (Arrendamentos Mercantis)**:
   - Passivos de arrendamento operacional/leasing pós-2019 devem ser tratados como passivo oneroso e integrados à dívida bruta (com opção de desativação configurável).
4. **Demonstrações Consolidadas**:
   - Sempre utilize dados consolidados (`DFP/ITR Consolidado`). Utilize demonstrações individuais apenas para empresas que não publicam consolidadas ou caso explicitamente configurado.
5. **QA Contábil e Falha Ruidosa**:
   - O módulo `qa.py` deve validar a equação patrimonial fundamental ($Ativo = Passivo + PL$) e a coerência lógica da DRE.
   - Discrepâncias relevantes devem gerar `warning` nos logs ou exceções claras, jamais coerção forçada ou silenciamento de erros.

---

## 2. Tratamento de Períodos e LTM

- **DFP Anual**: Valores reportados na DRE e DFC são acumulados dos 12 meses do exercício social encerrado.
- **ITR Trimestral**: Os dados de DRE e DFC no ITR são acumulados desde o início do ano fiscal corrente até o trimestre em questão (ex: 2T reflete 6 meses, 3T reflete 9 meses).
- **Cálculo de LTM (Last Twelve Months)**:
  - Utilize as rotinas em `src/contabil/periodos.py` para isolar os trimestres individuais por subtração aritmética antes de compor a soma móvel de 4 trimestres.

---

## 3. Checklist para o Agente ao Modificar `src/contabil/`

- [ ] A alteração respeita a separação entre `nao_financeiras` e `financeiras`?
- [ ] O arquivo `config/mapeamento_contas.yaml` foi atualizado caso novas contas ou sinônimos tenham sido mapeados?
- [ ] Caso uma empresa-piloto (PETR4, VALE3, WEGE3, ITUB4, BBAS3) tenha sofrido alteração de classificação, os testes em `tests/test_padronizacao.py` e `tests/test_golden.py` continuam válidos?
- [ ] A documentação no `guia.md` (seções de contabilidade e tabelas de campos) foi sincronizada?

