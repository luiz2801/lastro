"""Premissas sugeridas a partir do histórico (seção 9.2 do CLAUDE.md e ADR 0006).

Entrada: métricas anuais (`nao_financeiras.metricas(periodos.anual(...))`, índice = ano), só com
exercícios encerrados na data-base. Janelas por ano-calendário: "5a" = os 5 últimos exercícios,
"10a" = os 10 últimos (o crescimento de um ano usa a receita do ano anterior).

- Crescimento: começa na mediana de 5a, limitada a [-5%, 20%], e converge para o g terminal.
- Margem EBITDA **ajustada** (sem equivalência patrimonial e não recorrentes, coerente com o EBIT
  projetado): começa na mediana de 5a e termina na média entre as medianas de 5a e 10a.
- D&A, capex, capital de giro e pagamento de arrendamento sobre a receita: mediana de 5a.
- Alíquota: mediana da efetiva de 5a, limitada a [0, limite].
- Cenários: ±1 desvio-padrão (10a) do crescimento e da margem, limitado a [1, 5] p.p.; capex
  ±0,5 desvio-padrão, limitado a [0,25; 2] p.p. Pessimista = menos crescimento, menos margem e
  mais capex.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from valuation.projecao import ErroProjecao

JANELA_CURTA = 5
JANELA_LONGA = 10
CRESCIMENTO_MIN, CRESCIMENTO_MAX = -0.05, 0.20
REVERSAO_MARGEM = 0.5  # fração do caminho entre a mediana de 5a e a de 10a
DELTA_MIN, DELTA_MAX = 0.01, 0.05
FATOR_DELTA_CAPEX = 0.5
DELTA_CAPEX_MIN, DELTA_CAPEX_MAX = 0.0025, 0.02
MIN_EXERCICIOS = 2


@dataclass(frozen=True)
class Sugestao:
    valor: float
    origem: str  # vai como comentário no YAML e no resumo da CLI


@dataclass(frozen=True)
class Sugestoes:
    ano_base: int  # último exercício do histórico
    crescimento_inicio: Sugestao
    crescimento_fim: Sugestao
    margem_inicio: Sugestao
    margem_fim: Sugestao
    da_sobre_receita: Sugestao
    capex_sobre_receita: Sugestao
    nwc_sobre_receita: Sugestao
    arrendamento_sobre_receita: Sugestao
    aliquota: Sugestao
    delta_crescimento: Sugestao  # magnitude; o sinal depende do cenário
    delta_margem: Sugestao
    delta_capex: Sugestao
    estatisticas: pd.DataFrame  # razões por ano + linhas resumo, para o resumo x histórico
    avisos: tuple[str, ...]


def pct(x: float, casas: int = 1) -> str:
    """Percentual em pt-BR: 0,1234 -> '12,3%'."""
    return "—" if pd.isna(x) else f"{x + 0.0:.{casas}%}".replace(".", ",")  # sem "-0,0%"


def pp(x: float) -> str:
    """Pontos percentuais em pt-BR: 0,015 -> '1,50 p.p.'."""
    return "—" if pd.isna(x) else f"{x * 100:.2f} p.p.".replace(".", ",", 1)


def _limitada(nome: str, valor: float, minimo: float, maximo: float, casas: int = 0) -> str:
    """Origem de uma mediana limitada a [mínimo, máximo]; o valor bruto só aparece se cortado."""
    faixa = f"[{pct(minimo, casas)}, {pct(maximo, casas)}]"
    if minimo <= valor <= maximo:
        return f"{nome}, dentro de {faixa}"
    return f"{nome} = {pct(valor)}, limitada a {faixa}"


def _faixa(serie: pd.Series) -> str:
    anos = serie.dropna().index
    return f"{min(anos)}-{max(anos)}" if len(anos) else "sem dados"


def _janela(serie: pd.Series, ano_base: int, n: int) -> pd.Series:
    return serie[(serie.index > ano_base - n) & (serie.index <= ano_base)].dropna()


def cagr(receita: pd.Series, ano_base: int, n: int) -> float:
    """Crescimento anual composto de `ano_base - n` a `ano_base` (NaN sem os dois pontos > 0)."""
    inicio, fim = receita.get(ano_base - n), receita.get(ano_base)
    if inicio is None or fim is None or pd.isna(inicio) or pd.isna(fim) or inicio <= 0 or fim <= 0:
        return float("nan")
    return float((fim / inicio) ** (1 / n) - 1)


def razoes(historico: pd.DataFrame) -> pd.DataFrame:
    """Séries anuais que alimentam as sugestões (índice = ano, anos faltantes como NaN)."""
    if historico.empty:
        raise ErroProjecao("Histórico vazio: sem exercícios para sugerir premissas.")
    anos = pd.RangeIndex(int(historico.index.min()), int(historico.index.max()) + 1, name="ano")
    h = historico.reindex(anos)
    receita = h["receita_liquida"].astype(float)
    receita_valida = receita.where(receita > 0)
    r = pd.DataFrame(index=anos)
    r["receita_liquida"] = receita
    r["crescimento"] = receita_valida / receita_valida.shift(1) - 1
    r["margem_ebitda_ajustada"] = h["ebitda_ajustado"] / receita_valida
    r["da_sobre_receita"] = h["da"] / receita_valida
    r["capex_sobre_receita"] = h["capex"] / receita_valida
    r["nwc_sobre_receita"] = h["nwc"] / receita_valida
    r["arrendamento_sobre_receita"] = h["pagamento_arrendamento"] / receita_valida
    r["aliquota_efetiva"] = h["aliquota_efetiva"]
    return r.replace([np.inf, -np.inf], np.nan)


def _mediana(r: pd.DataFrame, coluna: str, ano_base: int, n: int) -> float:
    return float(_janela(r[coluna], ano_base, n).median())


def _obrigatoria(valor: float, nome: str) -> float:
    if pd.isna(valor):
        raise ErroProjecao(f"Sem histórico para sugerir {nome}; defina o valor no YAML.")
    return valor


def _delta(
    serie: pd.Series, *, fator: float, piso: float, teto: float, nome: str
) -> tuple[Sugestao, str | None]:
    sigma = float(serie.std(ddof=1)) if len(serie) >= 2 else float("nan")
    if pd.isna(sigma):
        return Sugestao(
            piso, f"piso de {pp(piso)} (histórico curto para o desvio-padrão de {nome})"
        ), (f"Histórico curto para o desvio-padrão de {nome}: delta dos cenários no piso.")
    valor = float(np.clip(fator * sigma, piso, teto))
    rotulo = "1 desvio-padrão" if fator == 1 else f"{fator:g} desvio-padrão".replace(".", ",")
    origem = f"{rotulo} de {nome} {_faixa(serie)} = {pp(fator * sigma)}"
    if not piso <= fator * sigma <= teto:
        origem += f", limitado a [{pp(piso)}, {pp(teto)}]"
    return Sugestao(valor, origem), None


def sugerir(
    historico: pd.DataFrame,
    *,
    g_terminal: Sugestao,
    aliquota_limite: float,
    commodity: bool,
    setor: str | None = None,
) -> Sugestoes:
    """Premissas sugeridas e a origem de cada uma. `g_terminal` traz o valor e de onde ele veio."""
    r = razoes(historico)
    ano_base = int(r.index.max())
    avisos: list[str] = []
    n_exercicios = int(r["receita_liquida"].notna().sum())
    if n_exercicios < MIN_EXERCICIOS:
        raise ErroProjecao(
            f"Só {n_exercicios} exercício(s) no histórico; são necessários {MIN_EXERCICIOS}."
        )
    faltantes = [int(a) for a in r.index[r["receita_liquida"].isna()]]
    if faltantes:
        avisos.append(f"Exercícios ausentes no histórico: {', '.join(map(str, faltantes))}.")
    if n_exercicios < JANELA_LONGA:
        avisos.append(
            f"Histórico de {n_exercicios} exercícios (menos que {JANELA_LONGA}): "
            "medianas e desvios com poucos pontos."
        )

    def curta(coluna: str) -> pd.Series:
        return _janela(r[coluna], ano_base, JANELA_CURTA)

    g5 = curta("crescimento")
    mediana_g = _obrigatoria(float(g5.median()), "o crescimento da receita")
    inicio = float(np.clip(mediana_g, CRESCIMENTO_MIN, CRESCIMENTO_MAX))
    crescimento_inicio = Sugestao(
        inicio,
        _limitada(
            f"mediana do crescimento {_faixa(g5)}", mediana_g, CRESCIMENTO_MIN, CRESCIMENTO_MAX
        ),
    )

    m5 = curta("margem_ebitda_ajustada")
    m10 = _janela(r["margem_ebitda_ajustada"], ano_base, JANELA_LONGA)
    med5 = _obrigatoria(float(m5.median()), "a margem EBITDA")
    med10 = float(m10.median())
    margem_inicio = Sugestao(med5, f"mediana da margem EBITDA ajustada {_faixa(m5)}")
    margem_fim = Sugestao(
        med5 + REVERSAO_MARGEM * (med10 - med5),
        f"média entre a mediana {_faixa(m5)} ({pct(med5)}) e a de {_faixa(m10)} ({pct(med10)})",
    )

    def razao(coluna: str, nome: str, *, opcional: bool = False) -> Sugestao:
        s = curta(coluna)
        valor = float(s.median())
        if pd.isna(valor) and opcional:
            return Sugestao(0.0, f"sem {nome} no histórico")
        return Sugestao(_obrigatoria(valor, nome), f"mediana {_faixa(s)}")

    t5 = curta("aliquota_efetiva")
    mediana_t = float(t5.median())
    if pd.isna(mediana_t):
        aliquota = Sugestao(aliquota_limite, "sem LAIR positivo no histórico: alíquota-limite")
    else:
        aliquota = Sugestao(
            float(np.clip(mediana_t, 0.0, aliquota_limite)),
            _limitada(
                f"mediana da alíquota efetiva {_faixa(t5)}", mediana_t, 0.0, aliquota_limite, 1
            ),
        )

    g10 = _janela(r["crescimento"], ano_base, JANELA_LONGA)
    capex10 = _janela(r["capex_sobre_receita"], ano_base, JANELA_LONGA)
    delta_crescimento, a1 = _delta(g10, fator=1, piso=DELTA_MIN, teto=DELTA_MAX, nome="crescimento")
    delta_margem, a2 = _delta(m10, fator=1, piso=DELTA_MIN, teto=DELTA_MAX, nome="margem EBITDA")
    delta_capex, a3 = _delta(
        capex10,
        fator=FATOR_DELTA_CAPEX,
        piso=DELTA_CAPEX_MIN,
        teto=DELTA_CAPEX_MAX,
        nome="capex/receita",
    )
    avisos.extend(a for a in (a1, a2, a3) if a)
    if commodity:
        nome_setor = f" ({setor})" if setor else ""
        avisos.append(
            f"Setor de commodity{nome_setor}: o histórico reflete o ciclo de preços; revise "
            "crescimento e margens à mão antes de confiar no resultado."
        )

    resumo = pd.DataFrame(
        {
            "ultimo": r.loc[ano_base],
            "mediana_5a": r.apply(lambda s: _janela(s, ano_base, JANELA_CURTA).median()),
            "mediana_10a": r.apply(lambda s: _janela(s, ano_base, JANELA_LONGA).median()),
        }
    ).T
    resumo.loc["cagr_3a", "crescimento"] = cagr(r["receita_liquida"], ano_base, 3)
    resumo.loc["cagr_5a", "crescimento"] = cagr(r["receita_liquida"], ano_base, 5)
    resumo.loc["cagr_10a", "crescimento"] = cagr(r["receita_liquida"], ano_base, 10)

    return Sugestoes(
        ano_base=ano_base,
        crescimento_inicio=crescimento_inicio,
        crescimento_fim=g_terminal,
        margem_inicio=margem_inicio,
        margem_fim=margem_fim,
        da_sobre_receita=razao("da_sobre_receita", "D&A"),
        capex_sobre_receita=razao("capex_sobre_receita", "capex"),
        nwc_sobre_receita=razao("nwc_sobre_receita", "capital de giro"),
        arrendamento_sobre_receita=razao(
            "arrendamento_sobre_receita", "pagamento de arrendamento", opcional=True
        ),
        aliquota=aliquota,
        delta_crescimento=delta_crescimento,
        delta_margem=delta_margem,
        delta_capex=delta_capex,
        estatisticas=resumo,
        avisos=tuple(avisos),
    )
