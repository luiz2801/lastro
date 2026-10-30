# REGRAS_TESTES.md — Regras para Testes, Mocks e Validação

> Instruções modulares para agentes de IA atuando na suíte de testes, fixtures, dados sintéticos e qualidade de código.  
> Consulte o guia detalhado em [`tests/README.md`](tests/README.md) para exemplos de código e uso de fixtures.  
> Escopo: `tests/*.py`, `tests/fixtures/`, `tests/golden/`, `pyproject.toml` e `Makefile`.

---

## 1. Princípios Inegociáveis

1. **Zero Acesso à Rede em Testes**:
   - É expressamente proibido fazer requisições HTTP para a internet dentro da suíte de testes (`pytest`).
   - Todos os testes de adaptadores devem usar mocks locais (ex: `respx`, monkeypatch ou fixtures em `tests/fixtures/`).
2. **Dados Sintéticos para Novos Cenários**:
   - Para testar lógicas contábeis, projeções ou novos modelos sem depender de arquivos gigantes da CVM, utilize as funções geradoras de `tests/sintetico.py` (`criar_empresa_sintetica`, etc.).
3. **Governança Estrita de Golden Tests (`tests/golden/`)**:
   - Testes golden comparam resultados de cálculos do pipeline contra dados oficiais divulgados nos releases das companhias (armazenados em `tests/golden/referencias.yaml`).
   - **Regra de Ouro**: **Nunca** altere valores de referência em `tests/golden/referencias.yaml` simplesmente para fazer um teste quebrado passar. Se houver divergência, verifique primeiro a fórmula, a escala ou o mapeamento de contas. Qualquer alteração em golden tests exige justificativa baseada no documento da companhia.
4. **Passagem Obrigatória no Portão de Qualidade**:
   - Nenhum commit deve ser realizado se `make lint tipos testes` não passar com 100% de sucesso.

---

## 2. Comandos Rápidos de Iteração para Agentes

Ao invés de rodar a suíte inteira durante o desenvolvimento, execute testes cirúrgicos para obter feedback rápido:

```bash
# Rodar apenas um arquivo de teste específico
uv run pytest tests/test_dcf.py

# Rodar um teste específico pelo nome
uv run pytest tests/test_ddm.py -k "test_calculo_ddm_gordon"

# Checar apenas formatação e linting
uv run ruff check src tests
uv run ruff format --check src tests

# Checar apenas tipos estáticos com MyPy
uv run mypy src/modelos/dcf.py
```

Antes de entregar a tarefa, valide a suíte completa:

```bash
make lint tipos testes
```

---

## 3. Checklist para o Agente ao Adicionar/Alterar Testes

- [ ] Nenhum teste faz chamadas de rede ou depende de arquivos fora do versionamento?
- [ ] O teste cobre tanto casos de sucesso quanto casos de borda (divisão por zero, dados contábeis nulos, taxas negativas)?
- [ ] O código de teste está formatado de acordo com as regras do Ruff e tipado de acordo com o MyPy?
- [ ] Se novos testes foram adicionados, a contagem na tabela de testes do `guia.md` foi conferida?

