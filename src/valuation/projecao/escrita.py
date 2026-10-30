"""Gera `config/empresas/{TICKER}.yaml` comentado (`valuation premissas sugerir --escrever`).

O arquivo inteiro é regenerado a partir de `PremissasEmpresa` (comentários próprios do usuário se
perdem; a CLI guarda o anterior em `.bak`). Campo `sugerido` continua `sugerido`, com o valor de
hoje e a origem em comentário; campo manual fica como está, com a sugestão ao lado (ADR 0006).
"""

from __future__ import annotations

import datetime as dt
import textwrap
from typing import Any

import yaml

from valuation.projecao.premissas import SUGERIDO, PremissasEmpresa, Trajetoria
from valuation.projecao.sugestor import Sugestao, Sugestoes, pct, pp

COLUNA_COMENTARIO = 36
LARGURA = 100


def _flow(valor: Any) -> str:
    """Valor YAML numa linha (estilo flow)."""
    texto = yaml.safe_dump(
        valor, default_flow_style=True, allow_unicode=True, sort_keys=False, width=10**6
    ).strip()
    return texto.removesuffix("\n...").strip()


def _linha(indent: int, chave: str, valor: Any, comentario: str = "") -> str:
    texto = f"{' ' * indent}{chave}: {_flow(valor)}"
    if comentario:
        texto = f"{texto.ljust(COLUNA_COMENTARIO)} # {comentario}"
    return texto


def _nota(valor: object, sugestao: Sugestao, casas: int = 1) -> str:
    texto = f"{pct(sugestao.valor, casas)} ({sugestao.origem})"
    return f"sugerido: {texto}" if valor == SUGERIDO else f"manual; sugerido seria {texto}"


def _comentarios(indent: int, linhas: list[str]) -> list[str]:
    prefixo = f"{' ' * indent}# "
    return [
        quebrada
        for texto in linhas
        for quebrada in textwrap.wrap(
            texto, LARGURA, initial_indent=prefixo, subsequent_indent=prefixo + "  "
        )
    ]


def _caminho(
    indent: int, chave: str, valor: Trajetoria | tuple[float, ...], inicio: Sugestao, fim: Sugestao
) -> list[str]:
    if isinstance(valor, tuple):
        notas = [
            f"manual (lista por ano); sugerido seria de {pct(inicio.valor)} a {pct(fim.valor)}",
        ]
    else:
        notas = [f"inicio {_nota(valor.inicio, inicio)}", f"fim {_nota(valor.fim, fim)}"]
    dados = list(valor) if isinstance(valor, tuple) else valor.model_dump(mode="json")
    return [*_comentarios(indent, notas), _linha(indent, chave, dados)]


def renderizar(premissas: PremissasEmpresa, sugestoes: Sugestoes, *, data_base: dt.date) -> str:
    """Texto do YAML da empresa; `carregar_premissas` dele devolve as mesmas `premissas`."""
    p = premissas
    a, pr, c = p.ajustes, p.projecao, p.cenarios
    s = sugestoes
    aj = a.model_dump(mode="json")
    linhas = [
        f"# Premissas de {p.ticker} (seção 9.1 do CLAUDE.md), geradas por",
        f"# `valuation premissas sugerir {p.ticker} --escrever` em {data_base.isoformat()}, "
        f"com o histórico até {s.ano_base}.",
        "# `sugerido` = recalculado do histórico a cada execução; o comentário mostra o valor de",
        "# hoje e a origem. Troque por um número para fixar (ou, em crescimento e margem, por uma",
        f"# lista com um valor por ano projetado a partir de {s.ano_base + 1}).",
        "# Taxas em decimal (0.05 = 5%). Estudo pessoal; não é recomendação de investimento.",
        _linha(0, "ticker", p.ticker),
        _linha(0, "tipo_modelo", p.tipo_modelo, "nao_financeira | financeira"),
        _linha(0, "classes_acao", list(p.classes_acao)),
        _linha(0, "moeda_relatorio", p.moeda_relatorio, "auto | BRL | USD"),
        "",
        "ajustes:",
        _linha(2, "consolidado", aj["consolidado"]),
        _linha(2, "ifrs16", aj["ifrs16"], "divida | ignorar"),
        _linha(2, "capex_equivalente_arrendamento", aj["capex_equivalente_arrendamento"]),
        _linha(2, "minoritarios", aj["minoritarios"], "contabil | multiplo_pvp"),
        _linha(2, "coligadas", aj["coligadas"], "somar_investimento_contabil | manter_no_ebit"),
        _linha(2, "caixa_extra", aj["caixa_extra"], "contas padrão somadas ao caixa"),
        _linha(2, "divida_extra", aj["divida_extra"], "contas padrão subtraídas na ponte"),
        *_comentarios(
            2, ["{ano, conta: ebit, valor (unidades da moeda; ganho > 0, perda < 0), descricao}"]
        ),
        _linha(2, "nao_recorrentes", aj["nao_recorrentes"]),
        _linha(2, "mapeamento_extra", aj["mapeamento_extra"], "regras de mapeamento_contas.yaml"),
        "",
        "projecao:",
        _linha(2, "horizonte_anos", pr.horizonte_anos, "perfil | inteiro (anos com fluxo por vir)"),
        "  receita:",
        *_caminho(
            4, "crescimento", pr.receita.crescimento, s.crescimento_inicio, s.crescimento_fim
        ),
        "  margens:",
        *_caminho(4, "ebitda", pr.margens.ebitda, s.margem_inicio, s.margem_fim),
    ]
    for chave, sugestao in (
        ("da_sobre_receita", s.da_sobre_receita),
        ("capex_sobre_receita", s.capex_sobre_receita),
        ("nwc_sobre_receita", s.nwc_sobre_receita),
        ("arrendamento_sobre_receita", s.arrendamento_sobre_receita),
    ):
        valor = getattr(pr, chave)
        linhas += [*_comentarios(2, [_nota(valor, sugestao)]), _linha(2, chave, valor)]
    aliquota = pr.aliquota_imposto
    linhas += [
        *_comentarios(
            2, [f"valor {_nota(aliquota.valor, s.aliquota)}", "limite_superior null => nominal"]
        ),
        _linha(2, "aliquota_imposto", aliquota.model_dump(mode="json")),
        "  terminal:",
        _linha(4, "g_nominal", pr.terminal.g_nominal, "null => settings.terminal.g_nominal_max"),
        _linha(4, "ronic", pr.terminal.ronic, "null => settings | wacc | roic_historico | número"),
        "",
        *_comentarios(
            0,
            [
                "Deltas somados ao cenário base em todos os anos explícitos (0.02 = 2 p.p.).",
                "Pessimista: -crescimento, -margem, +capex; otimista: o contrário. Sugeridos:",
                f"crescimento ±{pp(s.delta_crescimento.valor)} ({s.delta_crescimento.origem});",
                f"margem ±{pp(s.delta_margem.valor)} ({s.delta_margem.origem});",
                f"capex ±{pp(s.delta_capex.valor)} ({s.delta_capex.origem}).",
            ],
        ),
        "cenarios:",
        _linha(2, "pessimista", c.pessimista.model_dump(mode="json")),
        _linha(2, "otimista", c.otimista.model_dump(mode="json")),
        "",
        "pares:",
        _linha(2, "setor", p.pares.setor, "chave em config/setores.yaml"),
        _linha(2, "incluir", list(p.pares.incluir)),
        _linha(2, "excluir", list(p.pares.excluir)),
        "",
        "custo_capital:                      # sobrescritas opcionais (Fase 6)",
        _linha(
            2,
            "beta",
            p.custo_capital.beta.model_dump(mode="json", exclude_none=True),
            "regressao | comparaveis | manual (com valor)",
        ),
        _linha(
            2,
            "kd",
            p.custo_capital.kd.model_dump(mode="json", exclude_none=True),
            "historico | manual (com valor)",
        ),
    ]
    if s.avisos:
        linhas += ["", *_comentarios(0, [f"Aviso: {aviso}" for aviso in s.avisos])]
    return "\n".join(linhas) + "\n"
