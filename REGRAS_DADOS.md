# REGRAS_DADOS.md — Regras para Camada de Dados e Ingestão

> Instruções modulares para agentes de IA atuando na ingestão, scrapers, APIs e arquivos de configuração de mercado.
> Escopo: `src/data/*.py`, `config/cadastro_manual.csv`, `config/universo_ibovespa.csv`, `config/settings.yaml` (seção dados/fontes) e `docs/fontes.md`.

---

## 1. Princípios Inegociáveis

1. **Adaptadores Isolados**: Nenhuma camada superior (`contabil`, `projecao`, `modelos`) deve conhecer URLs, formatos de arquivo ou particularidades de provedores externos. Todo acesso passa exclusivamente por funções de `src/data/`.
2. **Proibição de Dados Falsos**: **Nunca** invente cotações, datas de balanço, múltiplos ou séries temporais. Se um dado não estiver disponível na fonte ou no cache, levante uma exceção explícita ou retorne ausência com aviso claro.
3. **Somente Fontes Gratuitas**: Utilize estritamente as fontes acordadas:
   - CVM Dados Abertos (DFP/ITR, cadastros);
   - BCB / SGS (Selic, IPCA, CDI);
   - Yahoo Finance (`yfinance`) e brapi (`brapi.dev` gratuito com `BRAPI_TOKEN` opcional).
4. **Idempotência e Cache Obrigatório**:
   - Todo download HTTP deve passar pelo cliente `src/data/http.py`.
   - O payload bruto é salvo em `data/raw/` acompanhado de um arquivo de metadados (`.meta.json`) contendo URL, timestamp ISO e hash SHA-256.
   - Respeite o TTL configurado no `settings.yaml` antes de realizar nova requisição de rede.

---

## 2. Armadilhas Comuns da Camada de Dados

- **Sufixo `.SA` para Yahoo Finance**:
  - Na B3, o Yahoo Finance exige o sufixo (ex: `PETR4.SA`, `VALE3.SA`).
  - No brapi e nos registros CVM, o ticker é sem sufixo (`PETR4`, `VALE3`).
  - A camada de dados deve normalizar tickers na fronteira.
- **Escala de Ações (ADR 0003)**:
  - Na CVM, o campo `QT_ACAO` nos arquivos DFP/ITR pode vir reportado em **unidades** ou em **milhares de ações**.
  - Sempre valide a escala e normalize para unidades inteiras de ações antes de passar para as camadas seguintes.
- **Moeda dos Relatórios da Vale (ADR 0002)**:
  - Embora a Vale reporte internacionalmente em USD, na CVM os demonstrativos oficiais protocolados estão em BRL. A ingestão padrão CVM lê BRL.
- **Validação Cruzada de Preços (ADR 0004)**:
  - Quando a brapi estiver configurada além do Yahoo Finance, aplique validação cruzada para garantir integridade da cotação de fechamento mais recente.

---

## 3. Checklist para o Agente ao Modificar `src/data/`

- [ ] Qualquer nova URL, endpoint de API ou código de série do BCB foi documentado em `docs/fontes.md`?
- [ ] O tratamento de falha de conexão e timeout é gracioso (com log informativo e sem crash opaco)?
- [ ] Os testes correspondentes em `tests/test_cvm.py`, `tests/test_precos.py`, `tests/test_macro.py` ou `tests/test_http.py` usam mocks/fixtures locais e **não** acessam a internet?
- [ ] Tipos anotados e validados com `mypy` limpo?

