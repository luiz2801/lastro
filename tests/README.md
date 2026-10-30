# Guia de Mocks, Fixtures e Testes Rápidos (`tests/`)

> Guia prático de testes, mocks e dados sintéticos para desenvolvedores e agentes de IA no projeto Lastro.  
> **Objetivo**: Garantir feedback rápido no desenvolvimento, determinismo e isolamento absoluto de rede.

---

## 1. Comandos de Feedback Rápido

Durante o desenvolvimento ou refatoração, **nunca execute a suíte de testes completa a cada edição**. A suíte integral valida pipelines contábeis complexos, cálculos multianuais e golden tests; rodá-la repetidamente desperdiça tempo e contexto.

Adote um **fluxo cirúrgico**: teste apenas o módulo ou a função em que está trabalhando.

### Testes Cirúrgicos

```bash
# Rodar apenas um arquivo de teste específico
pytest tests/test_dcf.py

# Rodar um teste específico pelo nome do caso (expressão -k)
pytest tests/test_dcf.py -k "fim_de_periodo"

# Interromper no primeiro erro (-x) com traceback resumido (--tb=short)
pytest tests/test_dcf.py -k "nome_do_caso" -x --tb=short

# Modo detalhado (-v) mostrando nomes de cada teste
pytest tests/test_ddm.py -v -k "test_calculo_ddm_gordon"
```

> **Dica**: Se estiver usando o ambiente virtual gerenciado por `uv`, use o prefixo `uv run pytest ...`.

### Validação Rápida de Tipos e Estilo

Antes de rodar testes de integração, valide estaticamente o arquivo modificado:

```bash
# Linting rápido com Ruff
uv run ruff check tests/test_dcf.py src/valuation/modelos/dcf.py

# Checagem de tipos cirúrgica com MyPy
uv run mypy src/valuation/modelos/dcf.py
```

### Validação Integral (Somente ao Concluir a Tarefa)

Apenas quando a implementação estiver concluída e os testes locais passarem, execute o portão completo antes de realizar o commit:

```bash
make lint tipos testes
```

---

## 2. Política de Isolamento Estrito (Zero Rede)

> [!CAUTION]
> **Nenhum teste dentro de `tests/` deve tocar a internet.**  
> Chamadas HTTP reais tornam os testes lentos, não determinísticos, frágeis a instabilidades externas e violam o sandbox de execução.

### Regras Obrigatórias:

1. **Proibição de Requisições Externas**: É estritamente proibido realizar chamadas HTTP reais a serviços como CVM, Banco Central (BCB/SGS), Tesouro Direto, Yahoo Finance ou Brapi durante o `pytest`.
2. **Mocks e Sessões Falsas**:
   - Utilize a classe `SessaoFalsa` disponível em `tests/conftest.py` para simular respostas HTTP em memória com códigos de status, cabeçalhos (`Last-Modified`, `ETag`) e payloads customizados.
   - Para múltiplos endpoints, use correspondência por prefixo (`SessaoPorPrefixo` em `tests/test_macro.py`).
   - Mocks de bibliotecas externas (ex.: `respx`, `pytest-mock` / `unittest.mock.patch`, ou `monkeypatch`) devem interceptar os adaptadores em `valuation.data.*`.
3. **Fixtures Locais**:
   - Para simular zips da CVM sem download, utilize a fixture `zip_cvm` (de `tests/conftest.py`), que empacota os CSVs de exemplo em `tests/fixtures/cvm/` em arquivos zip temporários.
4. **Isolamento de Disco**:
   - Sempre utilize a fixture `tmp_path` do pytest para qualquer leitura ou escrita de arquivos e diretórios de cache/saída gerados pelos testes.

---

## 3. Como Usar Dados Sintéticos (`tests/sintetico.py`)

Arquivos brutos da CVM contêm dezenas de milhares de linhas e demandam downloads de dezenas de megabytes. Para testar novos modelos, regras contábeis, projeções ou pipelines de padronização, utilize as funções geradoras de `tests/sintetico.py`.

Elas criam `pd.DataFrame` perfeitamente estruturados e consistentes com o esquema oficial da CVM (`COLUNAS_DEMONSTRACOES`), com balanço patrimonial fechado e DRE coerente.

### Exemplo Rápido: Instanciando `criar_empresa_sintetica` (~10 linhas)

```python
import pytest
from sintetico import criar_empresa_sintetica
from valuation.contabil.padronizacao import padronizar_empresa


def test_novo_modelo_com_empresa_sintetica() -> None:
    # 1. Cria 3 anos de demonstrações no padrão CVM sem download
    demonstracoes = criar_empresa_sintetica(anos=(2023, 2024, 2025), cd_cvm=1234)

    # 2. Executa a padronização contábil ou alimenta o modelo diretamente
    df_padronizado = padronizar_empresa(demonstracoes, tipo_modelo="nao_financeira")

    # 3. Valida os cálculos do seu modelo
    assert not df_padronizado.empty
    assert set(df_padronizado["ano"].unique()) == {2023, 2024, 2025}
```

### Customizando Contas com o Parâmetro `trocas`

Se você precisa simular cenários específicos (ex: aumento de receita, prejuízo, variação de dívida):

```python
# Sobrescrevendo a receita líquida (conta 3.01) e o lucro (conta 3.11) na DRE
df_cenario = criar_empresa_sintetica(
    anos=(2024, 2025),
    DRE={"3.01": 500.0, "3.11": 80.0},
    BPP={"2.01.04": 30.0},  # Alterar empréstimos de curto prazo
)
```

### Outros Construtores Úteis em `tests/sintetico.py`

- `criar_empresa_sintetica(..., banco=True)`: Gera histórico para instituições financeiras (plano de contas de bancos, intermediação financeira e DDM).
- `historico_anual(crescimento, margem, ...)`: Gera métricas consolidadas (receita, ebitda, capex, nwc) para testar os módulos `projetor` e `sugestor`.
- `contas_padronizadas(...)`: Gera diretamente a tabela final de contas contábeis padronizadas para testes unitários de KPIs ou modelos de valuation.

---

## 4. Governança de Golden Tests (`tests/golden/`)

Os testes em `tests/test_golden.py` validam o pipeline contra números oficiais divulgados em demonstrações reais das companhias (armazenados em `tests/golden/referencias.yaml`).

> [!IMPORTANT]
> **A Regra de Ouro**:  
> **Nunca altere os valores em `referencias.yaml` simplesmente para fazer um teste quebrado passar.**  
> Se houver discrepância em um golden test:
> 1. Inspecione se houve erro na fórmula do modelo ou projeção.
> 2. Verifique o mapeamento das contas ou escala aplicada (`MIL`, `UNIDADE`).
> 3. Qualquer alteração em `referencias.yaml` é excepcional e deve conter justificativa explícita baseada no documento oficial da companhia divulgado na CVM/RI.

---

## 5. Checklist para Agentes ao Adicionar ou Modificar Testes

- [ ] **Isolamento de Rede**: O teste funciona sem conexão com a internet (sem `requests.get` real, sem sockets externos)?
- [ ] **Feedback Rápido**: O teste executa em milissegundos e pode ser rodado individualmente via `pytest tests/<arquivo>.py -k "<caso>"`?
- [ ] **Uso de Sintéticos**: Em vez de carregar arquivos reais da CVM, foram utilizados `criar_empresa_sintetica` ou `historico_anual`?
- [ ] **Limpeza de Disco**: Qualquer gravação temporária utiliza a fixture `tmp_path`?
- [ ] **Tipagem e Lint**: O código de teste passa por `uv run ruff check tests` e possui anotações de tipo coerentes?
- [ ] **Portão Final**: O comando `make lint tipos testes` passa 100% antes da entrega final?

