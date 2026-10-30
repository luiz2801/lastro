# Playbooks de Tarefas Frequentes para Agentes (`docs/recipes_agentes.md`)

> **Guia Operacional Passo a Passo**: Este documento contém fluxos de trabalho determinísticos ("receitas de bolo") para orientar agentes de IA e desenvolvedores na execução das tarefas mais recorrentes no **Lastro**.

---

## Índice de Playbooks

1. [Playbook 1: Adicionar Suporte a uma Nova Empresa](#playbook-1-adicionar-suporte-a-uma-nova-empresa)
2. [Playbook 2: Adicionar uma Nova Métrica Contábil ou Mapeamento de Conta](#playbook-2-adicionar-uma-nova-métrica-contábil-ou-mapeamento-de-conta)
3. [Playbook 3: Adicionar ou Alterar um Parâmetro de Configuração](#playbook-3-adicionar-ou-alterar-um-parâmetro-de-configuração)
4. [Playbook 4: Adicionar ou Atualizar Testes Golden de Conciliação](#playbook-4-adicionar-ou-atualizar-testes-golden-de-conciliação)
5. [Playbook 5: Adicionar um Novo Múltiplo de Mercado](#playbook-5-adicionar-um-novo-múltiplo-de-mercado)
6. [Playbook 6: Diagnóstico e Resolução de Problemas Comuns](#playbook-6-diagnóstico-e-resolução-de-problemas-comuns)
7. [Playbook 7: Checklist de Finalização de Tarefa](#playbook-7-checklist-de-finalização-de-tarefa)

---

## Playbook 1: Adicionar Suporte a uma Nova Empresa

Execute este fluxo quando o usuário solicitar suporte a um novo ticker da B3.

### Passo 1: Identificar Metadados Básicos
Descubra a razão social, CNPJ e código CVM da empresa:
```bash
uv run valuation cadastro buscar "Nome da Empresa ou Ticker"
```

### Passo 2: Registrar no Cadastro Manual (`config/cadastro_manual.csv`)
Abra `config/cadastro_manual.csv` e adicione a linha com o delimitador `;`:
- `ticker`: Ticker principal da ação (ex: `RENT3`).
- `cnpj`: CNPJ formatado ou apenas números conforme o padrão do arquivo.
- `cd_cvm`: Código CVM obtido no Passo 1.
- `escala_acoes`: `1` (se a CVM reportar unidades) ou `1000` (se reportar em milhares). *Dica: confira o market cap após ingestão; se ficar na casa de bilhões ou centenas de milhões de forma condizente, está correto; se der trilhões ou poucos milhares, inverta a escala.*
- `tipo_modelo`: `nao_financeira` ou `financeira` (bancos e seguradoras).

### Passo 3: Configurar Setor e Pares (`config/setores.yaml`)
Verifique se a empresa pertence a um setor existente em `config/setores.yaml`.
- Se o setor já existir, adicione o ticker à lista `pares:` do setor (ou defina pares específicos em `config/empresas/<TICKER>.yaml`).
- Se for um setor novo, crie a chave do setor definindo `descricao`, `tipo_modelo` e a lista inicial de `pares`.

### Passo 4: Baixar e Padronizar os Dados
Baixe os demonstrativos da CVM e preços de mercado:
```bash
uv run valuation atualizar --tickers <TICKER> --com-pares
```

### Passo 5: Validar Cobertura e QA Contábil
Execute as ferramentas de diagnóstico contábil:
```bash
# Verificar se as contas obrigatórias foram capturadas
uv run valuation cobertura --tickers <TICKER>

# Validar se o balanço fecha e se há discrepâncias
uv run valuation qa <TICKER>
```

### Passo 6: Gerar o Arquivo de Premissas
Gere o arquivo `config/empresas/<TICKER>.yaml` com base nas medianas históricas sugeridas:
```bash
uv run valuation premissas sugerir <TICKER> --escrever
```
Revise o arquivo gerado em `config/empresas/<TICKER>.yaml` para ajustar premissas que exijam intervenção humana.

### Passo 7: Rodada Piloto de Valuation
Execute a avaliação completa e valide a geração de saídas em `saida/<TICKER>/`:
```bash
uv run valuation rodar <TICKER>
```

---

## Playbook 2: Adicionar uma Nova Métrica Contábil ou Mapeamento de Conta

### Passo 1: Mapear a Conta em `config/mapeamento_contas.yaml`
1. Localize a seção apropriada (`nao_financeira` ou `financeira`).
2. Adicione ou edite a conta padrão:
   ```yaml
   nome_da_conta_padrao:
     cd_conta: ["3.01", "3.01.01"]  # Códigos estruturados CVM
     descricao_regex: "(?i)termo_chave|outro_sinonimo"
   ```
3. Se a conta for indispensável, inclua-a na lista `contas_criticas`.

### Passo 2: Estender a Camada de Padronização Contábil
- Para não-financeiras: Edite `src/contabil/nao_financeiras.py`.
- Para financeiras: Edite `src/contabil/financeiras.py`.
- Se for apenas um campo direto da DFP/ITR, certifique-se de que o extrator repasse a conta para a visão padronizada.
- Se for uma métrica derivada (ex: razão de margem, giro ou retorno), implemente o cálculo respeitando valores nulos/divisão por zero e tipagem com dataclasses `frozen=True`.

### Passo 3: Atualizar Validações e Testes
1. Adicione testes com dados sintéticos em `tests/test_padronizacao.py` ou `tests/test_nao_financeiras.py`/`tests/test_financeiras.py`.
2. Se a métrica deve ser exibida no histórico da CLI, adicione-a em `_LINHAS_HISTORICO` dentro de `src/cli.py`.
3. Valide o impacto:
   ```bash
   uv run pytest tests/test_padronizacao.py tests/test_nao_financeiras.py
   ```

### Passo 4: Documentar no `guia.md`
Atualize a seção 11 do `guia.md` com a nova métrica ou conta adicionada e incremente a versão no topo.

---

## Playbook 3: Adicionar ou Alterar um Parâmetro de Configuração

### Passo 1: Declarar o Padrão em `config/settings.yaml`
Adicione a chave sob a seção hierárquica correspondente:
```yaml
minha_secao:
  novo_parametro: 0.05
```

### Passo 2: Tipar no Modelo Pydantic (`src/config.py`)
No `src/config.py`, localize a classe correspondente (decorada ou configurada com `extra="forbid"`):
```python
class ConfiguracaoMinhaSecao(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # ... outros campos
    novo_parametro: float = 0.05
```
*Atenção: como o Lastro utiliza `extra="forbid"`, se um parâmetro existir no YAML e não na classe Pydantic, o sistema falhará imediatamente.*

### Passo 3: Consumir o Parâmetro
Injete o parâmetro via configuração nos módulos onde ele deve ser utilizado:
```python
settings.minha_secao.novo_parametro
```

### Passo 4: Atualizar Testes de Configuração
Adicione asserções em `tests/test_config.py` validando parsing e valores padrão:
```bash
uv run pytest tests/test_config.py
```

---

## Playbook 4: Adicionar ou Atualizar Testes Golden de Conciliação

Testes golden garantem que o Lastro reproduz com precisão as demonstrações oficiais publicadas nos releases das companhias.

### Passo 1: Obter Documento Fonte
1. Baixe o release de resultados oficial da companhia (PDF/demonstração).
2. Registre o documento no índice de fontes arquivadas em `referencias/README.md`.

### Passo 2: Adicionar Valores Reais em `tests/golden/referencias.yaml`
Insira os dados sob o ticker e período correspondente (sempre em **R$ milhões**):
```yaml
PETR4:
  2025:
    receita_liquida: 489234.0
    ebitda: 215430.0
    lucro_liquido: 102340.0
```

### Passo 3: Atualizar Mapeamentos em `tests/test_golden.py`
Se uma nova métrica foi adicionada à conciliação, mapeie-a no dicionário `FLUXOS` ou `SALDOS` dentro de `tests/test_golden.py`.

### Passo 4: Executar e Ajustar Tolerâncias
Rode o teste de conciliação:
```bash
uv run pytest tests/test_golden.py -k "TICKER"
```
Se houver divergência:
- Não force a referência a bater.
- Investigue se a divergência decorre de definições próprias da companhia (ex: "EBITDA ajustado" vs "EBITDA CVM"). Se for definição customizada da companhia, adicione a chave em `NAO_COMPARAVEIS` com justificativa explícita.

---

## Playbook 5: Adicionar um Novo Múltiplo de Mercado

### Passo 1: Atualizar Constantes em `src/modelos/multiplos.py`
1. Adicione o identificador no tipo literal `NomeMultiplo`.
2. Adicione o rótulo amigável em `ROTULOS`.
3. Adicione a fórmula textual explicativa em `DEFINICOES`.

### Passo 2: Extrair a Métrica dos Fundamentos
- Se for não-financeira: atualize a função `fundamentos(...)` em `multiplos.py` para calcular o denominador/numerador a partir de `DemonstracaoContabil`.
- Se for financeira: atualize `fundamentos_financeira(...)`.

### Passo 3: Testar e Validar na CLI
1. Adicione o teste unitário correspondente em `tests/test_multiplos.py`.
2. Execute a comparação de múltiplos pela CLI:
   ```bash
   uv run valuation comparar <TICKER>
   ```

---

## Playbook 6: Diagnóstico e Resolução de Problemas Comuns

| Sintoma / Erro | Causa Mais Provável | Ação de Resolução |
|---|---|---|
| `pydantic_core._pydantic_core.ValidationError: Extra inputs are not permitted` | Foi adicionado um campo em `settings.yaml` sem tipá-lo na classe equivalente em `src/config.py`. | Adicione o atributo com tipo e default no modelo Pydantic em `src/config.py`. |
| `ErroModelo: Crescimento na perpetuidade g >= WACC` | Parâmetro `g_nominal` configurado acima do custo de capital ou taxa Selic/WACC anômala. | Reduza `g_nominal` (limite recomendado $\le 0.05$) ou verifique premissas de custo de capital. |
| Market Cap ou Múltiplos P/L absurdamente altos ou baixos | Escala de ações da CVM incorreta (unidades vs milhares). | Altere a coluna `escala_acoes` da empresa em `config/cadastro_manual.csv` (troque `1` por `1000` ou vice-versa) e reexecute. |
| Balanço patrimonial não fecha no `valuation qa` | Subcontas da CVM com dupla contagem ou ausência de mapeamento de contas críticas. | Inspecione `config/mapeamento_contas.yaml` e utilize `valuation cobertura --tickers <TICKER>` para ver contas zeradas. |
| Testes unitários falhando por tentativa de conexão | Código de teste chamando função de rede sem mock. | Isole o teste com mocks locais ou fixtures sintéticas (`tests/sintetico.py`). Proibido I/O externo em testes. |

---

## Playbook 7: Checklist de Finalização de Tarefa

Antes de considerar qualquer entrega como pronta ou solicitar aprovação do usuário:

1. **Portão de Qualidade:**
   ```bash
   make lint tipos testes
   ```
   *Deve passar com 100% de sucesso sem warnings de linting ou erros de tipagem.*
2. **Atualização da Documentação:**
   - [ ] [`guia.md`](../guia.md): atualizado na mesma entrega com novas funções, contratos, parâmetros ou armadilhas? Versão no topo incrementada?
   - [ ] [`docs/diagrama_atividades.md`](diagrama_atividades.md): atualizado caso o fluxo de execução, etapas ou saídas tenham mudado?
   - [ ] [`CHANGELOG.md`](../CHANGELOG.md): registrado resumo da entrega sob `[Não lançado]`?
   - [ ] [ADRs](../docs/decisoes/README.md): nova decisão de negócio ou divergência do `CLAUDE.md` foi formalizada em um ADR?
3. **Mensagem de Commit:**
   - Commit atômico seguindo o padrão: `area: o quê` (ex: `docs: adicionar playbooks frequentes para agentes`).

