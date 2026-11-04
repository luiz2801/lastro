# ADR 0022 — GUI local em Streamlit com Plotly

- **Data:** 2026-11-03
- **Status:** aceito

## Contexto

O `CLAUDE.md` (seção 1) deixava interface web fora da v1 e o `docs/backlog.md` registrava os
requisitos GUI-01 a GUI-97 com cinco decisões bloqueantes. O usuário respondeu em 2026-11-03: o
essencial é ver **métricas e valuation**, com gráficos de cotação, P/L e outros indicadores sobre a
série histórica; o resto "aparece com o tempo". A recomendação inicial do backlog (FastAPI + frontend
JS) trocava velocidade de entrega por fidelidade visual às páginas de referência.

## Decisão

1. **Tecnologia: Streamlit**, app local de um usuário. Se limitar a fidelidade visual ou a
   interatividade de forma relevante, troca-se por NiceGUI/FastAPI em novo ADR; a camada de serviço
   (item 4) existe justamente para a troca não tocar no motor.
2. **Gráficos: Plotly** (`st.plotly_chart`), para zoom, tooltip e seletor de período. Os PNGs do
   matplotlib continuam sendo a saída em arquivo da CLI (Fase 9); a GUI não os substitui.
3. **Execução:** ao abrir, a GUI lê o universo e os últimos resultados de `saida/` e o cache de
   `data/`, sem rede. Um botão "atualizar dados" chama o mesmo fluxo do `atualizar`/`rodar`.
4. **Camada de serviço** (`src/valuation/servicos/`): funções que devolvem objetos/DataFrames, sem
   `typer`/`rich`. CLI e GUI chamam as mesmas funções; a GUI não faz conta (GUI-90). A extração
   sai de `cli.py` sem mudar nenhuma saída (testes existentes idênticos).
5. **Escopo inicial:** página de ativo com indicadores e série histórica, cotação e valuation por
   cenário (GUI-01/02/03, 10–12, 20–22, 40–43). Navegação global, carteira, edição de premissas e
   demais itens seguem a ordem do backlog.
6. **Dependências:** `streamlit` e `plotly`, em grupo opcional `gui` do `pyproject.toml` (a CLI
   não passa a exigi-las). Escuta só em `127.0.0.1`, sem telemetria (`browser.gatherUsageStats =
   false`), sem login (GUI-95). Comando `valuation gui` e alvo `make gui` (GUI-97).
7. **Tema e idioma:** PT-BR; tema segue o do navegador/Streamlit.

## Consequências

- Nova dependência de runtime opcional; `make lint tipos testes` passa a cobrir `gui/` e `servicos/`.
- Streamlit reexecuta o script a cada interação: resultados pesados usam `st.cache_data` sobre
  as funções de serviço, nunca recálculo na tela.
- Testes da GUI sem rede, com fixtures sintéticas; `streamlit.testing.v1.AppTest` para as páginas.
- O layout denso das referências (cards, abas) será aproximado, não copiado.
