"""Cartões e faixa de preço em HTML da aba Valuation. Só montam texto: nenhuma conta aqui.

Todo texto vem escapado. O CSS (`CSS`) vai uma vez para a página, em `app.py`; as cores neutras
são translúcidas, para valer no tema claro e no escuro do Streamlit.
"""

from __future__ import annotations

from collections.abc import Sequence
from html import escape

import pandas as pd

from valuation.saida import formato as fo

CSS = """<style>
.lc-sec{border-left:3px solid #c9a56b;padding-left:14px;margin:0 0 22px 0}
.lc-sec summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:8px;
  margin:0 0 12px -17px;padding-left:17px;user-select:none}
.lc-sec summary::-webkit-details-marker{display:none}
.lc-sec summary::before{content:"";width:7px;height:7px;border-right:2px solid currentColor;
  border-bottom:2px solid currentColor;transform:rotate(-45deg);
  transition:transform .15s;opacity:.6;flex:none}
.lc-sec[open]>summary::before{transform:rotate(45deg)}
.lc-sec summary:hover::before{opacity:1}
.lc-sec summary:focus-visible{outline:2px solid #c9a56b;outline-offset:2px;border-radius:4px}
.lc-sec:not([open]){padding-bottom:0}
.lc-sec:not([open])>summary{margin-bottom:0}
.lc-sec h3{margin:0;font-size:1.2rem;font-weight:600;letter-spacing:-.01em}
.lc-sec .lc-nota{margin:8px 0 0 0;font-size:.8rem;opacity:.7}
.lc-grade{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:10px}
.lc-cart{background:rgba(128,128,128,.12);border:1px solid rgba(128,128,128,.28);border-radius:12px;
  padding:14px 14px 12px;display:flex;flex-direction:column;gap:6px;min-width:0}
.lc-cart.lc-destaque{background:rgba(128,128,128,.22)}
.lc-cart.lc-larga{grid-column:span 2}
.lc-rot{display:flex;justify-content:space-between;gap:6px;font-size:.82rem;font-weight:500;
  opacity:.7;text-transform:uppercase;letter-spacing:.04em}
.lc-q{width:15px;height:15px;border-radius:50%;border:1px solid currentColor;font-size:10px;
  line-height:13px;text-align:center;flex:none;cursor:help}
.lc-val{font-size:1.55rem;font-weight:600;line-height:1.25;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.lc-val small{font-size:.8rem;font-weight:500;opacity:.7}
.lc-obs{font-size:.78rem;opacity:.75;line-height:1.35}
.lc-subs{margin-top:auto;display:flex;flex-direction:column;gap:3px;font-size:.8rem;
  border-top:1px solid rgba(128,128,128,.28);padding-top:8px}
.lc-subs div{display:flex;justify-content:space-between;gap:8px}
.lc-subs span{opacity:.7}.lc-subs b{font-weight:700;font-variant-numeric:tabular-nums}
.lc-pos{color:#1a9e6f}.lc-neg{color:#d14b3f}
.lc-selo{display:inline-flex;border-radius:99px;padding:3px 14px;font-size:.95rem;font-weight:600;
  width:max-content}
.lc-ok{background:rgba(26,158,111,.18);color:#1a9e6f}
.lc-warn{background:rgba(217,115,13,.2);color:#d9730d}
.lc-bad{background:rgba(209,75,63,.2);color:#d14b3f}
.lc-selos{display:flex;flex-wrap:wrap;gap:8px}
.lc-selos .lc-selo{padding:6px 12px;font-size:.9rem}
.lc-selos small{font-weight:500;opacity:.85;margin-left:6px}
.lc-hero{background:rgba(128,128,128,.12);border:1px solid rgba(128,128,128,.28);border-radius:14px;
  padding:16px 18px 6px;margin-bottom:18px}
.lc-hero-topo{display:flex;flex-wrap:wrap;gap:12px 32px;align-items:flex-end;margin-bottom:12px}
.lc-hero-topo .lc-etq{font-size:.75rem;font-weight:600;text-transform:uppercase;
  letter-spacing:.06em;opacity:.7}
.lc-hero-topo .lc-gr{font-size:2.4rem;font-weight:700;line-height:1.1;
  font-variant-numeric:tabular-nums}
.lc-hero-topo .lc-md{font-size:1.6rem}
.lc-rolagem{overflow-x:auto}
.lc-escala{position:relative;min-width:620px;height:132px;margin:0 8px}
.lc-trilho{position:absolute;left:0;right:0;top:58px;height:4px;border-radius:2px;
  background:rgba(128,128,128,.3)}
.lc-faixa{position:absolute;top:54px;height:12px;border-radius:6px;background:rgba(42,120,214,.28)}
.lc-mk{position:absolute;top:0;transform:translateX(-50%);display:flex;flex-direction:column;
  align-items:center;font-size:.78rem;white-space:nowrap;line-height:1.25}
.lc-mk b{font-size:.95rem;font-variant-numeric:tabular-nums}
.lc-mk::after{content:"";width:2px;height:22px;background:currentColor;margin-top:2px}
.lc-mk i{width:12px;height:12px;border-radius:50%;background:currentColor;margin-top:-2px}
.lc-mk.lc-baixo{top:auto;bottom:0;flex-direction:column-reverse}
.lc-mk.lc-baixo::after{margin:0 0 2px 0}
.lc-mk.lc-esq{transform:translateX(-100%);align-items:flex-end}
.lc-mk.lc-dir{transform:none;align-items:flex-start}
.lc-mk.lc-esq i,.lc-mk.lc-dir i{display:none}
.lc-mk.lc-esq::after{align-self:flex-end;margin-right:-1px}
.lc-mk.lc-dir::after{align-self:flex-start;margin-left:-1px}
.lc-ticks{position:absolute;left:0;right:0;top:74px;height:14px;font-size:.7rem;opacity:.65}
.lc-ticks span{position:absolute;transform:translateX(-50%);font-variant-numeric:tabular-nums}
@media(max-width:420px){.lc-cart.lc-larga{grid-column:span 1}}
</style>"""

COR_PESSIMISTA = "#d14b3f"
COR_BASE = "#2a78d6"
COR_PONDERADO = "#a8854f"
COR_OTIMISTA = "#1a9e6f"
TRACO = "—"


def selo(texto: str, tom: str) -> str:
    """`tom`: ok | warn | bad."""
    return f'<span class="lc-selo lc-{tom}">{escape(texto)}</span>'


def texto_com_sinal(valor: float) -> str:
    """Taxa com sinal, em verde ou vermelho; sem dado, traço."""
    if pd.isna(valor):
        return TRACO
    classe = "lc-pos" if valor >= 0 else "lc-neg"
    sinal = "+" if valor >= 0 else ""
    return f'<span class="{classe}">{escape(sinal + fo.taxa(valor))}</span>'


def cartao(
    rotulo: str,
    valor: str,
    *,
    bruto: bool = False,
    pequeno: str = "",
    nota: str = "",
    ajuda: str = "",
    subs: Sequence[tuple[str, str]] = (),
    destaque: bool = False,
    larga: bool = False,
) -> str:
    """Um cartão: rótulo (com ? e tooltip), valor grande e, opcionalmente, linhas de apoio.

    `valor` é texto puro, escapado aqui; com `bruto=True` já é HTML montado por este módulo.
    `nota` é uma linha pequena sob o valor, em HTML já seguro (use `escape`).
    `subs` são pares (rótulo, valor) já formatados em texto puro.
    """
    classes = "lc-cart" + (" lc-destaque" if destaque else "") + (" lc-larga" if larga else "")
    q = f'<span class="lc-q" title="{escape(ajuda, quote=True)}">?</span>' if ajuda else ""
    corpo = valor if bruto else escape(valor)
    extra = f" <small>{escape(pequeno)}</small>" if pequeno else ""
    linhas = "".join(f"<div><span>{escape(a)}</span><b>{b}</b></div>" for a, b in subs)
    bloco = f'<div class="lc-subs">{linhas}</div>' if subs else ""
    obs = f'<div class="lc-obs">{nota}</div>' if nota else ""
    return (
        f'<div class="{classes}"><div class="lc-rot"><span>{escape(rotulo)}</span>{q}</div>'
        f'<div class="lc-val">{corpo}{extra}</div>{obs}{bloco}</div>'
    )


def sub(rotulo: str, valor: str) -> tuple[str, str]:
    """Linha de apoio com valor em texto puro (escapado)."""
    return rotulo, escape(valor)


def secao(titulo: str, cartoes: Sequence[str], nota: str = "") -> str:
    """Seção que o clique no título minimiza (`<details>`, sem JavaScript); abre por padrão."""
    aviso = f'<p class="lc-nota">{escape(nota)}</p>' if nota else ""
    return (
        f'<details class="lc-sec" open><summary><h3>{escape(titulo)}</h3></summary>'
        f'<div class="lc-grade">{"".join(cartoes)}</div>{aviso}</details>'
    )


def selos(itens: Sequence[tuple[str, str, str]]) -> str:
    """Pílulas (nome, detalhe, tom) em uma linha que quebra."""
    pilulas = "".join(
        f'<span class="lc-selo lc-{tom}" title="{escape(detalhe, quote=True)}">'
        f"{'✓' if tom == 'ok' else '!'} {escape(nome)}<small>{escape(detalhe)}</small></span>"
        for nome, detalhe, tom in itens
    )
    return f'<div class="lc-selos">{pilulas}</div>'


def _marcador(x: float, rotulo: str, valor: float, cor: str, posicao: str = "") -> str:
    return (
        f'<div class="lc-mk {posicao}" style="left:{x:.2f}%;color:{cor}">'
        f"<span>{escape(rotulo)}</span>"
        f"<b>{escape(fo.reais(valor))}</b><i></i></div>"
    )


def faixa_de_preco(
    *,
    pessimista: float,
    base: float,
    otimista: float,
    ponderado: float,
    preco: float,
    maximo: float,
    resumo: Sequence[tuple[str, str, bool]],
) -> str:
    """Faixa grande: números-chave no topo e a escala de preço com os cenários e o preço.

    `resumo` = (rótulo, texto já em HTML seguro, grande?). A escala vai de 0 até o maior valor
    (com folga), e o preço e o máximo ficam embaixo, cada um para um lado, porque costumam estar
    a poucos reais um do outro.
    """
    pontos = [v for v in (pessimista, base, otimista, ponderado, preco, maximo) if pd.notna(v)]
    teto = max(pontos) * 1.08 if pontos else 1.0
    passo = next((p for p in (1, 2, 5, 10, 20, 25, 50, 100, 200, 500) if teto / p <= 9), 1000)
    escala = [i * passo for i in range(int(teto // passo) + 1)]
    teto = max(teto, escala[-1])

    def x(v: float) -> float:
        return v / teto * 100

    topo = "".join(
        f'<div><div class="lc-etq">{escape(r)}</div><div class="lc-gr{" lc-md" if not g else ""}">'
        f"{t}</div></div>"
        for r, t, g in resumo
    )
    marcas = ""
    if pd.notna(pessimista) and pd.notna(otimista):
        marcas += (
            f'<div class="lc-faixa" style="left:{x(pessimista):.2f}%;'
            f'width:{x(otimista) - x(pessimista):.2f}%"></div>'
        )
    for rotulo, valor, cor in (
        ("Pessimista", pessimista, COR_PESSIMISTA),
        ("Base", base, COR_BASE),
        ("Ponderado", ponderado, COR_PONDERADO),
        ("Otimista", otimista, COR_OTIMISTA),
    ):
        if pd.notna(valor):
            marcas += _marcador(x(valor), rotulo, valor, cor)
    if pd.notna(maximo):
        marcas += _marcador(x(maximo), "Preço máximo", maximo, "currentColor", "lc-baixo lc-esq")
    if pd.notna(preco):
        marcas += _marcador(x(preco), "Preço da rodada", preco, "currentColor", "lc-baixo lc-dir")
    ticks = "".join(f'<span style="left:{x(t):.2f}%">{t:g}</span>' for t in escala)
    return (
        f'<div class="lc-hero"><div class="lc-hero-topo">{topo}</div>'
        f'<div class="lc-rolagem"><div class="lc-escala"><div class="lc-trilho"></div>{marcas}'
        f'<div class="lc-ticks">{ticks}</div></div></div></div>'
    )
