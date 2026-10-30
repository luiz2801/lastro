# ADR 0011 — Plano de contas e métricas das financeiras

- **Data:** 2026-10-30
- **Status:** aceito

## Contexto

A Fase 10 começa pela "seção `financeira:` do mapeamento, construída após inspeção real dos dados
de ITUB4/BBAS3" (seção 7.2 do `CLAUDE.md`). O usuário pediu que a fase cubra bancos **e**
seguradoras e que os pares abranjam o máximo de empresas possível. A inspeção de 25 financeiras
(DFP 2015–2025, ITR 2025–2026) mostrou:

- **Três planos de contas**: o de bancos (ITUB4, BBAS3, BBDC4…), o de seguradoras (BBSE3, IRBR3:
  lucro em `3.13`, PL em `2.03`) e o comercial (PSSA3, CXSE3: lucro em `3.11`).
- **Códigos que mudam no tempo**: no plano de bancos o lucro consolidado passou de `3.09` a `3.11`
  e o PL de `2.08` a `2.07` em 2019–2020 (BB, Bradesco, Santander, Banrisul…); Itaú, BTG e BMG
  continuam em `3.09`/`2.08`. As descrições não mudam.
- **Atribuição em dois lugares**: no BB de 2024–2025 há linhas "atribuído à controladora" sob
  `3.09` ("antes das participações") **e** sob `3.11` (lucro consolidado).
- **Só individual**: BAZA3, BNBR3, BGIP4, BPAR3, BMIN4, MERC4 e DMFN3 não publicam consolidado;
  BAZA3 usou até 2019 um plano antigo ("Resultado Antes Tributação/Participações", IR em duas
  linhas, "Lucro/Prejuízo do Período").
- **Períodos zerados**: os ITR de 2025 desses bancos trazem o balanço comparativo de 31/12/2024
  todo com zeros; pela regra "vale o documento mais recente" (ADR 0005) o balanço sumia.
- **Atribuição zerada**: ABCB4 (2020–2023) e IRBR3 (2022–2025) informam zero na controladora e nos
  não controladores, com lucro consolidado diferente de zero.
- **Dividendos sem linha**: o Santander passou ao DFC pelo método direto em 2021 e não abre os
  dividendos pagos.
- **Corretoras** (WIZC3, QUAL3) estão no setor CVM "Seguradoras e Corretoras", mas usam o plano
  comercial e vivem de comissões: sem float, sem capital regulatório.

## Decisão

1. **Seção `financeira:` do mapeamento por regex de descrição**, com o mínimo que o DDM usa:
   lucro consolidado, da controladora e dos não controladores, LAIR, IR/CSLL, ativo e passivo
   total, PL consolidado, não controladores no PL, dividendos/JCP pagos à controladora; `3.01` e
   `3.03` só informam. A atribuição tem uma regra por pai (`3.11` primeiro, depois `3.13` e
   `3.09`) e uma última que só casa a DRE individual (sem "consolidado"), onde o lucro é todo da
   controladora.
2. **Contas críticas**: LAIR, IR/CSLL, lucro, lucro da controladora, ativo, passivo e PL.
3. **Individual quando não há consolidado**: a CLI usa as individuais, com aviso, se a companhia
   não publica nenhuma demonstração consolidada (vale também para não financeiras).
4. **Documento com período só de zeros não substitui outro** que informe o mesmo período (vale
   para todas as companhias); se for o único, fica.
5. **Métricas** (`contabil/financeiras.py`): PL da controladora = PL consolidado − não
   controladores; ROE = lucro da controladora / PL da controladora **do início** do período (a
   mesma convenção do DDM, LL_t = ROE_t × PL_{t−1}); comparação com o período anterior só se ele
   estiver exatamente 12 meses antes. Dividendos ausentes ficam vazios (não zero), e o payout
   também. Atribuição zerada com lucro diferente de zero ⇒ lucro todo da controladora (o QA avisa).
6. **QA próprio**: balanço (ativo = passivo total) e PL positivo são erro; subcontas só de `1` e
   `2`; atribuição do lucro; saltos de ativo, PL e lucro. Sem a lista de contas não mapeadas
   relevantes (depósitos e captações de um banco apareceriam sempre).
7. **WIZC3 e QUAL3 passam a `nao_financeira`** no `cadastro_manual.csv` (FCFF, não DDM).

## Consequências

- Cobertura de 100% das contas críticas em 23 das 25 financeiras; BSLI4 (BRB, DRE semestral em
  parte dos anos, 40%) e CXSE3 (sem DRE de 2015, 91%) ficam abaixo. QA sem erros em todas.
- O BB aparece com `fontes_divergentes` em 2024 (atribuição sob `3.09` × `3.11`): esperado.
- O payout histórico é de caixa (dividendos pagos no ano / lucro do ano): mistura exercícios e
  dividendos extraordinários (Itaú 2025: 108%). Serve de ponto de partida, não de política.
- Não há dados regulatórios (Basileia) nem lucro recorrente gerencial: limitação já prevista na
  seção 11.3 do `CLAUDE.md`.
