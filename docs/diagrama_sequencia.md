# Diagrama de Sequência — `valuation rodar TICKER`

Complementa o [diagrama de atividades](diagrama_atividades.md): aqui o foco é **quem chama quem, e em que ordem**, no caminho não financeiro (DCF) do comando `rodar` em [`cli.py`](../src/valuation/cli.py). O ramo financeiro (DDM) está resumido no bloco `alt`. Contratos e parâmetros ficam no [`guia.md`](../guia.md).

```mermaid
sequenceDiagram
    autonumber
    actor U as Usuário
    participant CLI as cli.rodar
    participant CFG as config / perfil
    participant CTB as contabil<br/>(padronizacao, periodos, qa)
    participant DAD as data<br/>(cvm, precos, macro, validacao)
    participant PRJ as projecao<br/>(sugestor, projetor)
    participant CC as custo_capital<br/>(beta, capm, kd, wacc)
    participant MOD as modelos<br/>(dcf, ponte, multiplos)
    participant ANA as analise<br/>(cenarios, sensibilidade)
    participant OUT as saida<br/>(csv, graficos, arquivos)

    U->>CLI: valuation rodar PETR4 [--cenario --perfil --data-base]
    CLI->>CFG: carregar_settings()
    CLI->>CFG: resolver_perfil(JSON, hoje, override)
    alt perfil ausente ou vencido (> 12 meses) e sem --perfil
        CFG-->>CLI: ErroPerfil
        CLI-->>U: mensagem em PT-BR, saída 1
    end
    CFG-->>CLI: settings, perfil efetivo
    CLI->>CFG: parametros_do_perfil(perfil)
    CFG-->>CLI: margem de segurança, pesos, horizonte, hurdle

    CLI->>CTB: _padronizar(ticker)
    CTB->>DAD: contas CVM (DFP 10 anos, ITR) via cache + .meta.json
    DAD-->>CTB: parquets brutos
    CTB->>CTB: reapresentações, mapeamento_contas.yaml, visões A/T/LTM
    CTB->>CTB: qa (balanço fecha, DRE, saltos)
    alt erro crítico de QA ou holding / não suportada
        CTB-->>CLI: ErroContabil
        CLI-->>U: saída 1 (diagnóstico em qa_TICKER.json)
    end
    CTB-->>CLI: contas padronizadas, plano, premissas da empresa

    alt tipo_modelo = financeira
        CLI->>CLI: _rodar_financeira (Ke, projeção ROE/payout, DDM,<br/>lucro residual, P/VP justificado, saídas)
        CLI-->>U: resultado do DDM e fim
    end

    CLI->>PRJ: _sugerir(histórico, base)
    PRJ-->>CLI: métricas históricas e premissas sugeridas
    CLI->>PRJ: _resolver(sugestões + YAML, horizonte)
    PRJ-->>CLI: premissas resolvidas e deltas dos cenários

    CLI->>DAD: _mercado(ticker, base)
    par cotações e macro
        DAD->>DAD: yfinance (brapi como fallback) e market cap multi-classe
    and
        DAD->>DAD: SGS, Focus, Tesouro (Selic, IPCA, câmbio, Rf)
    end
    DAD->>DAD: validacao cruzada (preço 2%, câmbio 1,5%)
    DAD-->>CLI: preços, market cap, macro, avisos

    CLI->>DAD: _coletar_pares(setor / incluir / excluir)
    DAD-->>CLI: fundamentos e mercado dos pares
    CLI->>CC: _custo_capital(beta, Ke, Kd, estrutura)
    CC->>CC: beta (regressão semanal vs Ibovespa, Blume)
    CC->>CC: Ke (brl_direto | usd_crp), Kd, WACC
    CC-->>CLI: custo de capital (valida WACC > g)
    CLI->>MOD: _multiplos(empresa, pares)
    MOD-->>CLI: múltiplos, estatísticas P10/P90, valores implícitos

    CLI->>ANA: cenarios.analisar(premissas, deltas, dados, cc, ronic, perfil, preço)
    loop pessimista, base, otimista
        ANA->>PRJ: projetar(histórico, premissas do cenário)
        PRJ-->>ANA: FCFF ano a ano (com ano parcial)
        ANA->>MOD: dcf.avaliar (VP dos FCFF + valor terminal)
        MOD-->>ANA: EV e checagens (VT/EV, g < WACC)
        ANA->>MOD: ponte EV para equity
        MOD-->>ANA: valor por ação do cenário
    end
    ANA->>ANA: pondera pelos pesos do perfil, aplica margem de segurança
    ANA-->>CLI: valor justo ponderado, preço máximo de compra, retorno vs hurdle

    CLI->>ANA: wacc_x_g e margem_x_crescimento
    ANA-->>CLI: matrizes de sensibilidade
    CLI->>MOD: dcf.g_implicito(EV/EBITDA mediano dos pares)
    MOD-->>CLI: g de saída (checagem do terminal)

    CLI-->>U: tabelas rich no terminal (valuation, projeção, múltiplos, sensibilidade)
    CLI->>OUT: gravar CSVs (wacc, projecao_*, ponte, sensibilidade, multiplos, resumo)
    CLI->>OUT: _gravar_complementos (historico, qa.json, valores_reais,<br/>premissas_usadas.yaml, gráficos PNG, meta.json por último)
    OUT-->>CLI: saida/TICKER/AAAA-MM-DD/
    CLI-->>U: avisos, aviso de não ser recomendação, caminho gravado
```

## Notas

- Qualquer `Erro*` de domínio (`ErroPerfil`, `ErroContabil`, `ErroCustoCapital`, `ErroModelo` etc.) é capturado em `rodar` e vira mensagem em PT-BR com saída não nula (`_erro`).
- O motor de cálculo (`projetar`, `dcf`, `ponte`, `cenarios`, `sensibilidade`) é puro: não faz I/O nem lê relógio. Todo I/O fica em `data/` e `saida/`; `cli.py` só orquestra.
- `--cenario base|pessimista|otimista` roda um só cenário no laço; `--sem-graficos` omite os PNG; `--forcar` ignora o cache em `_mercado`.
- Fora deste fluxo: `valuation atualizar` (só ingestão), `perfil` (questionário) e `carteira` (ADR 0020).
