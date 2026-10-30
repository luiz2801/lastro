# valuation — Valuation de ações da B3

Ferramenta pessoal e educacional para avaliar empresas listadas na B3 (DCF, DDM e múltiplos)
a partir de dados gratuitos (CVM, BCB, yfinance). **Não constitui recomendação de investimento.**

O guia completo do projeto está em [`CLAUDE.md`](CLAUDE.md).

## Setup

Requer [`uv`](https://docs.astral.sh/uv/) (o Python 3.12 é baixado automaticamente).

```bash
make setup                  # cria .venv e instala dependências
uv run valuation versao
make lint tipos testes
```

## Estado

Fase 0 (fundação) concluída. Ver [`CHANGELOG.md`](CHANGELOG.md).

## Riscos e limitações

- **Qualidade dos dados gratuitos**: inconsistências de contas na CVM e instabilidade do yfinance.
  Por isso há QA e adaptadores isolados.
- **DCF é muito sensível** a WACC, g e margens; o resultado é uma faixa, não um número.
  A saída sempre mostra sensibilidade.
- **Empresas de commodity**: o histórico reflete o ciclo de preços; as premissas exigem revisão manual.
- **Beta** de ações pouco líquidas é ruidoso.
- **Financeiras**: sem dados regulatórios (Basileia) e sem lucro gerencial; o DDM é uma simplificação.
- **Sem consenso de analistas**: as projeções dependem só do histórico e do usuário.
- **IFRS 16**: tratar arrendamento como dívida exige proxy para a reposição dos arrendamentos;
  setores com muitos arrendamentos (varejo, aéreas) precisam de atenção.
- **Valor por ação** ignora diluição e diferenças entre classes de ação.
- Os parâmetros de mercado em `config/settings.yaml` são **placeholders** até serem revisados.
