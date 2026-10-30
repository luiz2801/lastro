"""Gráficos PNG da saída (seção 13 do CLAUDE.md), legendas em PT-BR.

Usa `matplotlib.figure.Figure` direto (sem `pyplot`): nada de estado global nem de backend
interativo. Estilo: superfície clara, grade hairline, linhas de 2 px, marcas finas, cores
categóricas na ordem fixa (azul, laranja, verde-água) e texto sempre em tinta neutra.
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Literal, ParamSpec

import matplotlib
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure
from matplotlib.patches import Patch, Rectangle

from valuation.saida.arquivos import CenarioSaida, Faixa

SUPERFICIE = "#fcfcfb"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
MUDO = "#898781"
GRADE = "#e1e0d9"
EIXO = "#c3c2b7"
AZUL, LARANJA, VERDE_AGUA, AMARELO = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
BOM, CRITICO = "#0ca30c", "#d03b3b"
SEQUENCIAL = LinearSegmentedColormap.from_list("azul", ["#cde2fb", "#86b6ef", "#2a78d6", "#184f95"])
DPI = 150
P = ParamSpec("P")


def _sem_mathtext(f: Callable[P, Path]) -> Callable[P, Path]:
    """ "R$" aparece duas vezes em muitos textos: sem isto o matplotlib lê o trecho como fórmula."""

    @functools.wraps(f)
    def interna(*args: P.args, **kwargs: P.kwargs) -> Path:
        with matplotlib.rc_context({"text.parse_math": False}):
            return f(*args, **kwargs)

    return interna


def br(valor: float, casas: int = 2) -> str:
    """Número no formato pt-BR (1.234,56)."""
    if not np.isfinite(valor):
        return "—"
    return f"{valor:,.{casas}f}".translate(str.maketrans(",.", ".,"))


def reais(valor: float) -> str:
    return f"R$ {br(valor)}"


def pct(valor: float, casas: int = 1) -> str:
    return f"{br(valor * 100, casas)}%"


def _figura(
    largura: float, altura: float, titulo: str, subtitulo: str = ""
) -> tuple[Figure, float]:
    fig = Figure(figsize=(largura, altura), dpi=DPI, facecolor=SUPERFICIE)
    fig.text(0.02, 0.97, titulo, fontsize=13, fontweight="bold", color=TINTA, va="top")
    if subtitulo:
        fig.text(0.02, 0.925, subtitulo, fontsize=9, color=TINTA_2, va="top")
    return fig, 0.88 if subtitulo else 0.92


def _eixo(ax: Axes, *, grade: Literal["x", "y"] = "y") -> None:
    ax.set_facecolor(SUPERFICIE)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(EIXO)
    ax.tick_params(colors=MUDO, labelsize=8, length=0)
    ax.grid(axis=grade, color=GRADE, linewidth=0.8)
    ax.set_axisbelow(True)


def _salvar(fig: Figure, caminho: Path) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(caminho, dpi=DPI, facecolor=SUPERFICIE)
    return caminho


@_sem_mathtext
def football_field(
    faixas: Sequence[Faixa],
    *,
    preco: float,
    preco_maximo: float,
    caminho: Path,
    ticker: str,
    perfil: str,
) -> Path:
    """Barras horizontais de valor por ação por método, com o preço atual e o preço máximo de
    compra do perfil como linhas verticais."""
    n = len(faixas)
    fig, topo = _figura(
        9.5,
        1.6 + 0.55 * n,
        f"Football field — {ticker}",
        f"Valor por ação (R$) por método; perfil {perfil}",
    )
    ax = fig.add_axes((0.27, 0.16, 0.68, topo - 0.22))
    _eixo(ax, grade="x")
    ax.set_yticks(range(n))
    ax.set_yticklabels(
        [f.rotulo + (" (baixa confiança)" if f.aviso else "") for f in faixas],
        fontsize=9,
        color=TINTA_2,
    )
    ax.invert_yaxis()
    for i, f in enumerate(faixas):
        ax.barh(
            i,
            f.maximo - f.minimo,
            left=f.minimo,
            height=0.42,
            color=AZUL,
            alpha=0.45 if f.aviso else 1.0,
        )
        ax.text(f.minimo, i, f"{br(f.minimo)} ", ha="right", va="center", fontsize=8, color=TINTA_2)
        ax.text(f.maximo, i, f" {br(f.maximo)}", ha="left", va="center", fontsize=8, color=TINTA_2)
        if f.ponto is not None and f.minimo <= f.ponto <= f.maximo:
            ax.plot(
                [f.ponto],
                [i],
                marker="o",
                markersize=6,
                color=SUPERFICIE,
                markeredgecolor=TINTA,
                markeredgewidth=1.5,
            )
    ax.axvline(preco, color=LARANJA, linewidth=2)
    ax.axvline(preco_maximo, color=VERDE_AGUA, linewidth=2, linestyle="--")
    todos = [v for f in faixas for v in (f.minimo, f.maximo)] + [preco, preco_maximo]
    lo, hi = min(todos), max(todos)
    folga = (hi - lo) * 0.12 or 1.0
    ax.set_xlim(min(0.0, lo - folga) if lo < 0 else max(0.0, lo - folga), hi + folga)
    ax.set_ylim(n - 0.5, -0.5)
    ax.legend(
        handles=[
            Patch(color=AZUL, label="Faixa do método"),
            Patch(color=LARANJA, label=f"Preço atual ({reais(preco)})"),
            Patch(color=VERDE_AGUA, label=f"Preço máximo de compra ({reais(preco_maximo)})"),
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, -0.09),
        ncol=3,
        frameon=False,
        fontsize=8,
        labelcolor=TINTA_2,
    )
    return _salvar(fig, caminho)


@_sem_mathtext
def cascata_ponte(
    ponte: pd.DataFrame, *, caminho: Path, ticker: str, cenario: str, moeda: str
) -> Path:
    """Cascata EV -> equity (em milhões) a partir de `ponte.tabela`."""
    v = ponte.set_index("item")["valor"]
    passos = [
        ("Valor da\nfirma", v["valor_da_firma"], True),
        ("Dívida\nbruta", v["divida_bruta"], False),
        ("Caixa e\naplicações", v["caixa_e_aplicacoes"], False),
        ("Minoritários", v["minoritarios"], False),
        ("Coligadas", v["investimentos_coligadas"], False),
        ("Dívida\nextra", v["divida_extra"], False),
        ("Equity", v["equity"], True),
    ]
    fig, topo = _figura(
        9.5, 5.0, f"Ponte EV → equity — {ticker}", f"Cenário {cenario}; R$ milhões ({moeda})"
    )
    ax = fig.add_axes((0.08, 0.2, 0.89, topo - 0.26))
    _eixo(ax)
    acumulado = 0.0
    for i, (_, valor, total) in enumerate(passos):
        mi = valor / 1e6
        if total:
            base, altura, cor = 0.0, mi, AZUL
            acumulado = mi
        else:
            base, altura = acumulado, mi
            cor = BOM if mi >= 0 else CRITICO
            acumulado += mi
        ax.bar(i, altura, bottom=base, width=0.55, color=cor)
        topo_barra = max(base, base + altura)
        ax.text(i, topo_barra, f"{br(mi, 0)}", ha="center", va="bottom", fontsize=8, color=TINTA_2)
    ax.axhline(0, color=EIXO, linewidth=1)
    ax.set_xticks(range(len(passos)))
    ax.set_xticklabels([p[0] for p in passos], fontsize=8, color=TINTA_2)
    ax.margins(y=0.12)
    ax.yaxis.set_major_formatter(lambda x, _: br(x, 0))
    ax.legend(
        handles=[
            Patch(color=AZUL, label="Total"),
            Patch(color=BOM, label="Aumenta o equity"),
            Patch(color=CRITICO, label="Reduz o equity"),
        ],
        loc="upper right",
        frameon=False,
        fontsize=8,
        labelcolor=TINTA_2,
    )
    return _salvar(fig, caminho)


@_sem_mathtext
def heatmap(
    matriz: pd.DataFrame,
    *,
    caminho: Path,
    titulo: str,
    rotulo_x: str,
    rotulo_y: str,
    preco: float | None = None,
) -> Path:
    """Sensibilidade do valor por ação (R$); célula central (valor do cenário) com contorno."""
    fig, topo = _figura(
        8.5,
        6.2,
        titulo,
        "Valor por ação (R$)"
        + (f"; preço atual {reais(preco)} (células em negrito: acima do preço)" if preco else ""),
    )
    ax = fig.add_axes((0.12, 0.12, 0.8, topo - 0.2))
    ax.set_facecolor(SUPERFICIE)
    valores = matriz.to_numpy(dtype=float)
    ax.imshow(valores, cmap=SEQUENCIAL, aspect="auto")
    for i in range(valores.shape[0]):
        for j in range(valores.shape[1]):
            v = valores[i, j]
            escuro = np.isfinite(v) and v > np.nanmin(valores) + 0.6 * (
                np.nanmax(valores) - np.nanmin(valores)
            )
            acima = preco is not None and np.isfinite(v) and v >= preco
            ax.text(
                j,
                i,
                br(v),
                ha="center",
                va="center",
                fontsize=7,
                color="#ffffff" if escuro else TINTA,
                fontweight="bold" if acima else "normal",
            )
    ci, cj = valores.shape[0] // 2, valores.shape[1] // 2
    ax.add_patch(
        Rectangle((cj - 0.5, ci - 0.5), 1, 1, fill=False, edgecolor=LARANJA, linewidth=2.5)
    )
    ax.set_xticks(range(valores.shape[1]))
    ax.set_xticklabels([pct(float(c), 2) for c in matriz.columns], fontsize=8, color=TINTA_2)
    ax.set_yticks(range(valores.shape[0]))
    ax.set_yticklabels([pct(float(i), 2) for i in matriz.index], fontsize=8, color=TINTA_2)
    ax.set_xlabel(rotulo_x, fontsize=9, color=TINTA_2)
    ax.set_ylabel(rotulo_y, fontsize=9, color=TINTA_2)
    ax.tick_params(length=0)
    for lado in ax.spines.values():
        lado.set_visible(False)
    return _salvar(fig, caminho)


class Painel:
    """Uma série do `historico_vs_projecao`: histórico e projeção por cenário (R$ milhões)."""

    def __init__(
        self, titulo: str, historico: pd.Series, projecao: Mapping[str, pd.Series]
    ) -> None:
        self.titulo, self.historico, self.projecao = titulo, historico, projecao


@_sem_mathtext
def historico_vs_projecao(
    paineis: Sequence[Painel], *, caminho: Path, ticker: str, referencia: str, moeda: str
) -> Path:
    n = len(paineis)
    fig, topo = _figura(
        4.2 * n,
        4.6,
        f"Histórico x projeção — {ticker}",
        f"R$ milhões ({moeda}); projeção do cenário {referencia}; faixa: pessimista a otimista",
    )
    largura = 0.88 / n
    for k, p in enumerate(paineis):
        ax = fig.add_axes((0.06 + k * (largura + 0.01), 0.14, largura - 0.04, topo - 0.28))
        _eixo(ax)
        h = p.historico.dropna()
        h = h / 1e6
        ax.plot(h.index, h.to_numpy(dtype=float), color=AZUL, linewidth=2, label="Histórico")
        ref = p.projecao.get(referencia)
        if ref is not None:
            ref = ref / 1e6
            if len(h):
                ax.plot(
                    [h.index[-1], ref.index[0]],
                    [h.to_numpy(dtype=float)[-1], ref.to_numpy(dtype=float)[0]],
                    color=LARANJA,
                    linewidth=1,
                    linestyle=":",
                )
            ax.plot(
                ref.index,
                ref.to_numpy(dtype=float),
                color=LARANJA,
                linewidth=2,
                linestyle="--",
                label="Projeção",
            )
        lo, hi = p.projecao.get("pessimista"), p.projecao.get("otimista")
        if lo is not None and hi is not None:
            ax.fill_between(
                lo.index,
                lo.to_numpy(dtype=float) / 1e6,
                hi.to_numpy(dtype=float) / 1e6,
                color=LARANJA,
                alpha=0.15,
                linewidth=0,
            )
        ax.set_title(p.titulo, fontsize=10, color=TINTA, loc="left")
        ax.set_xticks(
            sorted({int(x) for x in [*h.index, *(ref.index if ref is not None else [])]})[::2]
        )
        ax.yaxis.set_major_formatter(lambda x, _: br(x, 0))
        if k == 0:
            ax.legend(loc="upper left", frameon=False, fontsize=8, labelcolor=TINTA_2)
    return _salvar(fig, caminho)


@_sem_mathtext
def composicao_valor(
    cenarios: Mapping[str, CenarioSaida],
    *,
    caminho: Path,
    ticker: str,
    rotulo_fluxos: str,
    rotulo_total: str,
    moeda: str,
) -> Path:
    """Por cenário, VP dos fluxos explícitos e VP do valor terminal (barras empilhadas)."""
    nomes = list(cenarios)
    fig, topo = _figura(
        8.0,
        1.8 + 0.9 * len(nomes),
        f"Composição do valor — {ticker}",
        f"{rotulo_total}, R$ milhões ({moeda}); parcela do valor terminal à direita",
    )
    ax = fig.add_axes((0.14, 0.2, 0.72, topo - 0.28))
    _eixo(ax, grade="x")
    for i, nome in enumerate(nomes):
        c = cenarios[nome]
        fl, vt = c.vp_fluxos / 1e6, c.vp_terminal / 1e6
        ax.barh(i, fl, height=0.5, color=AZUL)
        ax.barh(i, vt, left=fl + 0.0, height=0.5, color=LARANJA, edgecolor=SUPERFICIE, linewidth=2)
        total = fl + vt
        ax.text(
            max(total, fl, 0),
            i,
            f"  {pct(vt / total, 0) if total > 0 else '—'}",
            va="center",
            fontsize=8,
            color=TINTA_2,
        )
    ax.set_yticks(range(len(nomes)))
    ax.set_yticklabels(nomes, fontsize=9, color=TINTA_2)
    ax.invert_yaxis()
    ax.xaxis.set_major_formatter(lambda x, _: br(x, 0))
    ax.margins(x=0.1)
    ax.legend(
        handles=[
            Patch(color=AZUL, label=rotulo_fluxos),
            Patch(color=LARANJA, label="VP do valor terminal"),
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, -0.1),
        ncol=2,
        frameon=False,
        fontsize=8,
        labelcolor=TINTA_2,
    )
    return _salvar(fig, caminho)
