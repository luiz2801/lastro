# ADR 0019 — Setores como enum e `rodar-setor` (execução em lote por setor)

- **Data:** 2026-10-30
- **Status:** aceito

## Contexto

O `CLAUDE.md` deixa o modo em lote para a Fase 11, "só se o usuário pedir" (seções 1 e 17). O
usuário pediu: enumerar os setores, enumerar as empresas de cada setor e rodar o algoritmo sobre
elas. Os setores disponíveis são os `setor_cvm` de `config/universo_ibovespa.csv` (33 valores
distintos). `config/setores.yaml` tem outra função (pares e tipo de modelo) e só cobre 6 setores.

## Decisão

1. **Enum de setores.** `SetorCVM` (`src/valuation/universo.py`) é um `StrEnum` fixo no código,
   com um membro por `setor_cvm`. Um teste confere que o enum coincide com o CSV versionado, e
   `carregar_universo` falha se aparecer um setor fora do enum. O nome do membro (`BANCOS`) e o
   texto da CVM (`Bancos`) são aceitos, sem distinguir caixa, acento ou pontuação.
2. **Empresas do setor.** Vêm do CSV, na ordem dele, com `tipo_modelo` de cada linha.
3. **`valuation setores [SETOR]`** lista os setores com a contagem, ou as empresas de um setor.
4. **`valuation rodar-setor SETOR`** roda o `rodar` de cada empresa, uma após a outra, com as
   mesmas opções do `rodar`. Holdings (e tipos não suportados) são puladas com aviso. Um erro em
   uma empresa não interrompe as demais; ao final, uma tabela mostra o resultado de cada uma e a
   execução sai com 1 se alguma falhou. Perfil inválido é checado uma vez, antes do laço.
5. **Sem resumo consolidado entre empresas.** Cada execução grava sua pasta
   `saida/{TICKER}/{data}/`, como no `rodar`.

## Consequências

- Um setor com empresas que ainda não têm `atualizar` executado falha pela mensagem já existente
  do `rodar` (empresa a empresa), e as demais continuam.
- Novo setor no universo exige acrescentar o membro ao enum; o teste de coincidência aponta a
  falta.
- O enum usa os setores da CVM, não as chaves de `setores.yaml` (`petroleo_gas`, `bancos`...):
  `valuation setores petroleo_gas` não existe. Para a PETR4, o setor é `PETROLEO_E_GAS`.
- Não há paralelismo: o laço roda uma empresa por vez, como o `rodar` (dados de rede e cache).
