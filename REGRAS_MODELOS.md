# REGRAS_MODELOS.md — Regras para Projeção, Custo de Capital e Avaliação

> Instruções modulares para agentes de IA atuando na projeção de fluxos, estimação de taxas de desconto, modelos de valuation (DCF, DDM, Múltiplos) e análise de cenários.
> Escopo: `src/projecao/*.py`, `src/custo_capital/*.py`, `src/modelos/*.py`, `src/analise/*.py` e `src/perfil/*.py`.

---

## 1. Princípios Inegociáveis

1. **Funções Puras no Motor de Cálculo**:
   - Todo módulo em `modelos/`, `custo_capital/`, `projecao/` e `analise/` deve ser composto de **funções estritamente puras**.
   - **Zero I/O**: Nenhum arquivo em disco ou requisição de rede é permitida dentro dos cálculos.
   - **Sem relógio global oculto**: É terminantemente proibido invocar `datetime.now()` ou `date.today()` dentro de funções de cálculo. A data de referência (`data_base`) deve ser fornecida explicitamente como argumento.
2. **Separação Rígida: Dados ➔ Premissas ➔ Cálculo**:
   - O motor de cálculo não sabe qual empresa está sendo processada; ele opera exclusivamente sobre dataclasses tipados (`Premissas`, `DemonstracaoContabil`, `CustoCapital`, etc.).
   - As premissas são sugeridas pelo histórico (`sugestor.py`) e podem ser sobrescritas manualmente em `config/empresas/<TICKER>.yaml`.
3. **Modelos Adequados ao Tipo de Negócio**:
   - **Não Financeiras**: Fluxo de Caixa Livre para a Firma (FCFF) descontado pelo WACC. Ponte entre Enterprise Value (EV) e Equity Value detalhada (dívida líquida, participações minoritárias, passivos judiciais, IFRS 16). Múltiplos de referência: EV/EBITDA e P/L.
   - **Financeiras (ADR 0012, 0013, 0014)**: Dividend Discount Model (DDM) com modelo de Gordon / Lucro Residual descontado pelo Custo do Capital Próprio ($K_e$). Múltiplos de referência: P/VP justificado e P/L.
4. **Ponderação pelo Perfil do Investidor**:
   - Margens de segurança, horizontes temporais, taxa de retorno mínima e ponderação de probabilidades para os cenários (otimista, base, pessimista) devem derivar do perfil configurado em `perfil/parametros.py`.
5. **Reprodutibilidade Total**:
   - Cada rodada de cálculo deve registrar e retornar todas as premissas efetivamente adotadas, parâmetros de WACC/Ke e metadados de execução.

---

## 2. Limites de Sanidade Econômica

- **Taxa de Crescimento na Perpetuidade ($g$)**:
  - $g$ **nunca** pode exceder a taxa esperada de crescimento do PIB nominal de longo prazo da economia brasileira (em regra, $g \le 5\%$ nominal).
- **Condição de Convergência**:
  - A taxa de desconto deve ser estritamente superior ao crescimento na perpetuidade ($WACC > g$ no DCF; $K_e > g$ no DDM). Cálculos que violem essa premissa devem falhar com erro de modelo inconsistente.
- **Estrutura de Capital e Beta**:
  - Utilizar a fórmula de Hamada para desalavancagem e realavancagem de betas setoriais quando aplicável. Para instituições financeiras, considerar o beta direto sem desalavancagem por dívida.

---

## 3. Checklist para o Agente ao Modificar Modelos

- [ ] A função adicionada ou modificada é 100% pura e determinística?
- [ ] Os dataclasses de entrada e saída mantiveram compatibilidade e tipos estritos?
- [ ] As validações matemáticas impedem divisão por zero ou raízes de valores negativos?
- [ ] Testes unitários foram adicionados ou atualizados em `tests/test_dcf.py`, `tests/test_ddm.py`, `tests/test_wacc.py` ou `tests/test_cenarios.py`?
- [ ] O `guia.md` e o `docs/diagrama_atividades.md` foram atualizados se etapas de cálculo ou saídas mudaram?

