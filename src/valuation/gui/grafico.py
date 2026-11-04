"""Figuras Plotly da aba Geral. Só desenham o que os serviços calcularam.

Um eixo por gráfico. Cor: azul = a série, cinza = o que saiu da referência, tinta neutra = a linha
de referência e o valor de hoje.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd
import plotly.graph_objects as go

from valuation.saida import formato as fo
from valuation.saida.arquivos import Faixa
from valuation.servicos.historico_mercado import AnaliseMultiplo
from valuation.servicos.indicadores import AnaliseIndicador

AZUL = "#2a78d6"
CINZA = "#898781"
TINTA = "#52514e"
LARANJA = "#d9730d"  # pares do setor
VERDE = "#1a9e6f"  # Ibovespa; azul, laranja e verde validados em claro e escuro
FORMATO_DATA = "%d/%m/%Y"
ROTULOS_PONTE = {
    "valor_da_firma": "EV",
    "divida_bruta": "Dívida bruta",
    "caixa_e_aplicacoes": "Caixa e aplicações",
    "minoritarios": "Minoritários",
    "investimentos_coligadas": "Coligadas",
    "divida_extra": "Dívida extra",
    "equity": "Equity",
}


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


@dataclass(frozen=True)
class LinhaGrupo:
    """Referência de um grupo mês a mês (`valor` e `n`); NaN = lacuna."""

    rotulo: str
    serie: pd.DataFrame
    cor: str
    traco: str


def multiplo(
    a: AnaliseMultiplo,
    rotulo: str,
    rotulo_referencia: str,
    grupos: Sequence[LinhaGrupo] = (),
) -> go.Figure:
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
    maximos = [float(validos.max())] if validos.notna().any() else []
    for grupo in grupos:
        trecho = (
            grupo.serie[grupo.serie.index >= a.serie.index.min()] if len(a.serie) else grupo.serie
        )
        if trecho["valor"].notna().any():
            maximos.append(float(trecho["valor"].max()))
        figura.add_trace(
            go.Scatter(
                x=trecho.index,
                y=trecho["valor"],
                mode="lines",
                name=grupo.rotulo,
                connectgaps=False,
                line={"color": grupo.cor, "width": 2, "dash": grupo.traco},
                customdata=trecho["n"],
                hovertemplate=(
                    f"{grupo.rotulo}<br>%{{x|%m/%Y}}<br>{formato_valor}"
                    "<br>n = %{customdata}<extra></extra>"
                ),
            )
        )
    teto = max(maximos) * 1.1 if maximos else 1.0
    if len(fora):
        verdadeiro = a.serie.reindex(fora)
        y = verdadeiro.clip(upper=teto).fillna(0.0)
        textos = [
            f"{d:%d/%m/%Y}<br>{fo.multiplo(a.nome, float(verdadeiro[d]), 2)}<br>{a.descartados[d]}"
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
            annotation_text=f"{rotulo_referencia}: {fo.multiplo(a.nome, a.referencia, 2)}",
            annotation_position="top left",
        )
    if pd.notna(a.atual):
        figura.add_trace(
            go.Scatter(
                x=[a.serie.index[-1]],
                y=[a.atual],
                mode="markers",
                name=f"Hoje: {fo.multiplo(a.nome, a.atual, 2)}",
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


def indicador(a: AnaliseIndicador, rotulo: str, unidade: str, nome_referencia: str) -> go.Figure:
    """Indicador por período (anual + LTM). Fora da referência em cinza; marcado com contorno."""
    y = a.serie / 1e6 if unidade == "mi" else a.serie
    formato = {"%": ".1%", "x": ".2f", "mi": ",.0f"}[unidade]
    fora = a.serie.index.isin(a.descartados.index)
    figura = go.Figure(
        go.Scatter(
            x=a.serie.index,
            y=y.where(~fora),
            mode="lines+markers",
            name=rotulo,
            connectgaps=False,
            line={"color": AZUL, "width": 2},
            marker={"color": AZUL, "size": 6},
            hovertemplate=f"%{{x}}<br>%{{y:{formato}}}<extra></extra>",
        )
    )
    if fora.any():
        figura.add_trace(
            go.Scatter(
                x=a.serie.index[fora],
                y=y[fora],
                mode="markers",
                name=f"Fora da referência ({int(fora.sum())})",
                marker={"color": CINZA, "size": 9, "symbol": "x"},
                text=[str(a.descartados[i]) for i in a.serie.index[fora]],
                hovertemplate=f"%{{x}}<br>%{{y:{formato}}}<br>%{{text}}<extra></extra>",
            )
        )
    if len(a.marcados):
        figura.add_trace(
            go.Scatter(
                x=a.marcados.index,
                y=a.marcados,
                mode="markers",
                name=f"Fora de 1,5·IQR, mantido ({len(a.marcados)})",
                marker={"color": "rgba(0,0,0,0)", "size": 11, "line": {"color": TINTA, "width": 2}},
                hovertemplate=f"%{{x}}<br>%{{y:{formato}}}<extra></extra>",
            )
        )
    if pd.notna(a.referencia):
        figura.add_hline(
            y=a.referencia,
            line={"color": TINTA, "width": 1, "dash": "dash"},
            annotation_text=f"{nome_referencia}: {fo.formatar(a.referencia, unidade, 2)}",
            annotation_position="top left",
        )
    figura = _layout(
        figura, "R$ mi" if unidade == "mi" else rotulo, ".0%" if unidade == "%" else None
    )
    figura.update_xaxes(type="category")
    return figura


def ponte(itens: pd.Series) -> go.Figure:
    """Cascata EV -> equity, em R$ milhões no rótulo; os totais em tinta."""
    medidas = ["absolute", *["relative"] * (len(itens) - 2), "total"]
    figura = go.Figure(
        go.Waterfall(
            x=[ROTULOS_PONTE.get(str(i), str(i)) for i in itens.index],
            y=itens.to_numpy(),
            measure=medidas,
            connector={"line": {"color": CINZA, "width": 1}},
            increasing={"marker": {"color": AZUL}},
            decreasing={"marker": {"color": CINZA}},
            totals={"marker": {"color": TINTA}},
            text=[fo.formatar(float(v), "mi", 2) for v in itens],
            textposition="outside",
            hovertemplate="%{x}<br>R$ %{text} mi<extra></extra>",
        )
    )
    figura = _layout(figura, "R$")
    figura.update_layout(showlegend=False)
    return figura


def football(faixas: Sequence[Faixa], preco: float, preco_maximo: float) -> go.Figure:
    """Barras de valor por ação; linhas verticais do preço e do preço máximo de compra."""
    nomes = [f"{f.rotulo} *" if f.aviso else f.rotulo for f in faixas]
    figura = go.Figure(
        go.Bar(
            y=nomes,
            x=[f.maximo - f.minimo for f in faixas],
            base=[f.minimo for f in faixas],
            orientation="h",
            marker={"color": AZUL},
            width=0.45,
            name="Faixa de valor por ação",
            text=[f"{fo.reais(f.minimo)} a {fo.reais(f.maximo)}" for f in faixas],
            hovertemplate="%{y}<br>%{text}<extra></extra>",
            textposition="none",
        )
    )
    pontos = [f for f in faixas if f.ponto is not None]
    if pontos:
        figura.add_trace(
            go.Scatter(
                x=[f.ponto for f in pontos],
                y=[f"{f.rotulo} *" if f.aviso else f.rotulo for f in pontos],
                mode="markers",
                name="Base ou mediana",
                marker={"color": TINTA, "size": 9, "line": {"color": "white", "width": 2}},
                text=[fo.reais(float(f.ponto or 0.0)) for f in pontos],
                hovertemplate="%{y}<br>%{text}<extra></extra>",
            )
        )
    for valor, rotulo, traco, ancora in (
        (preco, "Preço", "solid", "top right"),
        (preco_maximo, "Preço máx. de compra", "dash", "bottom right"),
    ):
        if pd.notna(valor):
            figura.add_vline(
                x=valor,
                line={"color": TINTA, "width": 1, "dash": traco},
                annotation_text=f"{rotulo}: {fo.reais(valor)}",
                annotation_position=ancora,
            )
    figura = _layout(figura, "")
    figura.update_layout(
        height=max(280, 46 * len(faixas) + 90),
        xaxis={"title": "R$ por ação", "showgrid": True},
        yaxis={"autorange": "reversed", "title": ""},
    )
    return figura
