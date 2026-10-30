# Documentos das companhias

Documentos publicados nos sites de RI, usados para conciliar os dados da CVM
(`tests/golden/referencias.yaml`, `docs/fontes.md`). Os arquivos ficam fora do git (tamanho);
só este índice é versionado. Nomes: `{período}_{documento}[_{padrão ou moeda}].{ext}`.

★ = fonte de valores em `tests/golden/referencias.yaml`.

## PETR4 — Petrobras

| Arquivo | Conteúdo |
|---|---|
| `2T26_desempenho_brl.pdf` ★ | Relatório de desempenho 2T26 em R$ (Tabela 1, Tabela 10 reconciliação do EBITDA, endividamento) |
| `2T26_desempenho_usd.pdf` | Mesmo relatório em US$ |
| `2T26_demonstracoes_financeiras_brl.pdf` | Informações financeiras intermediárias 30/06/2026 em R$ |
| `2T26_demonstracoes_financeiras_usd.pdf` | Demonstrações intermediárias condensadas em US$ |
| `2T26_tabelas_brl.xlsx` / `2T26_tabelas_usd.xlsx` | Tabelas do relatório de desempenho |

## VALE3 — Vale

| Arquivo | Conteúdo |
|---|---|
| `2025_relatorio_administracao.pdf` ★ | Relatório da Administração 2025 (receita, EBITDA ajustado, lucro, dívida em R$) |
| `2025_relatorio_anual.pdf` | Relatório Anual 2025 (abril/2026) |
| `2025_form_20f.pdf` | Form 20-F 2025 (tradução, em US$) |
| `2026_formulario_referencia.pdf` | Formulário de Referência 2026 |
| `2026-08-31_composicao_acionaria.pdf` ★ | Ações em circulação, tesouraria e capital total |
| `{1T26,3T26}_desempenho_brgaap.pdf` ★ | Indicadores e reconciliação do LAJIDA em R$ |
| `{1T26,2T26,3T26}_desempenho_ifrs.pdf` | Relatório de desempenho completo (US$) |
| `{1T26,2T26,3T26}_desempenho.xlsx` | Planilhas do desempenho |
| `{1T26,2T26,3T26}_demonstracoes_financeiras_{brgaap,ifrs}.pdf` | Demonstrações intermediárias (BRGAAP em R$; IFRS em US$). O de 2T26 BRGAAP não tem camada de texto |

## WEGE3 — WEG

| Arquivo | Conteúdo |
|---|---|
| `3T26_release.pdf` ★ | Release 3T26 (Tabelas 1, 4 cálculo do EBITDA, 5 caixa líquido; anexos) |
| `{1T26,2T26}_release.pdf` | Releases anteriores |
| `{2T26,3T26}_itr.pdf` | ITR completo (com notas explicativas) |

Apagados em 2026-10-30 por não servirem ao projeto: transcrições e apresentações de
teleconferência, apresentação institucional, informe de governança, relatórios de sustentabilidade,
fiscais e de produção, Form SD, simulador de preço realizado da Vale e três resumos `.md` gerados
por IA com números errados.
