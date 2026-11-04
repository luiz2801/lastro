"""Figuras Plotly da aba Geral. Só desenham o que os serviços calcularam.

Um eixo por gráfico. Cor: azul = a série, cinza = o que saiu da referência, tinta neutra = a linha
de referência e o valor de hoje.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from valuation.saida import formato as fo
from valuation.servicos.historico_mercado import AnaliseMultiplo

AZUL = "#2a78d6"
CINZA = "#898781"
TINTA = "#52514e"
FORMATO_DATA = "%d/%m/%Y"


def _layout(figura: go.Figure, titulo_y: str, formato_y: str | None = None) -> go.Figure:
    figura.update_layout(
        height=340,
        margin={"l": 8, "r": 8, "t": 28, "b": 8},
        separators=",.",
        hovermode="closest",
        legend={"orientation": "h", "y": 1.08, "x": 0},
        xaxis={"showgrid": False},
        yaxis={"title": titulo_y, "tickformat": formato_y, "zeroline": False},
    )
    return figura


def cotacao(serie: pd.DataFrame, ticker: str) -> go.Figure:
    figura = go.Figure(
        go.Scatter(
            x=serie.index,
            y=serie["close"],
            mode="lines",
            name=ticker,
            line={"color": AZUL, "width": 2},
            hovertemplate=f"%{{x|{FORMATO_DATA}}}<br>R$ %{{y:,.2f}}<extra></extra>",
        )
    )
    figura = _layout(figura, "R$")
    figura.update_layout(hovermode="x")
    return figura


def multiplo(a: AnaliseMultiplo, rotulo: str, rotulo_referencia: str) -> go.Figure:
    """Pontos descartados em cinza, nunca apagados; fora da escala, presos à borda com ▲.

    A escala segue os pontos válidos: um EV/EBIT de 12.000x não pode achatar o resto. O valor
    verdadeiro continua no tooltip.
    """
    percentual = a.nome == "dividend_yield"
    formato_y = ".1%" if percentual else None
    formato_valor = "%{y:.1%}" if percentual else "%{y:.1f}x"
    fora = a.descartados.index
    validos = a.serie.where(~a.serie.index.isin(fora))
    figura = go.Figure()
    figura.add_trace(
        go.Scatter(
            x=validos.index,
            y=validos,
            mode="lines+markers",
            name=rotulo,
            connectgaps=False,
            line={"color": AZUL, "width": 2},
            marker={"color": AZUL, "size": 5},
            hovertemplate=f"%{{x|{FORMATO_DATA}}}<br>{formato_valor}<extra></extra>",
        )
    )
    teto = float(validos.max()) * 1.1 if validos.notna().any() else 1.0
    if len(fora):
        verdadeiro = a.serie.reindex(fora)
        y = verdadeiro.clip(upper=teto).fillna(0.0)
        textos = [
            f"{d:%d/%m/%Y}<br>{fo.multiplo(a.nome, float(verdadeiro[d]))}<br>{a.descartados[d]}"
            for d in fora
        ]
        figura.add_trace(
            go.Scatter(
                x=fora,
                y=y,
                mode="markers",
                name=f"Fora da referência ({len(fora)})",
                marker={
                    "color": CINZA,
                    "size": 9,
                    "symbol": ["triangle-up" if v >= teto else "x" for v in y],
                },
                text=textos,
                hovertemplate="%{text}<extra></extra>",
            )
        )
    if pd.notna(a.referencia):
        figura.add_hline(
            y=a.referencia,
            line={"color": TINTA, "width": 1, "dash": "dash"},
            annotation_text=f"{rotulo_referencia}: {fo.multiplo(a.nome, a.referencia)}",
            annotation_position="top left",
        )
    if pd.notna(a.atual):
        figura.add_trace(
            go.Scatter(
                x=[a.serie.index[-1]],
                y=[a.atual],
                mode="markers",
                name=f"Hoje: {fo.multiplo(a.nome, a.atual)}",
                marker={
                    "color": TINTA,
                    "size": 11,
                    "line": {"color": "white", "width": 2},
                },
                hovertemplate=f"Hoje<br>{formato_valor}<extra></extra>",
            )
        )
    figura = _layout(figura, rotulo, formato_y)
    figura.update_yaxes(range=[0, teto])
    return figura
