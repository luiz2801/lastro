"""Série histórica de múltiplos (ADR 0023): preço de cada data sobre o LTM vigente naquela data.

Funções puras. O `Close` do yfinance já vem na base de hoje quanto a splits; a quantidade de ações
da CVM vem na base de cada data. Por isso a quantidade é levada à base de hoje pelo fator dos splits
**posteriores à data da composição**, e não à data do preço: assim um split que cai entre a
composição vigente e o preço não produz degrau.

Falta de dado é NaN, nunca zero nem interpolação.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping
from dataclasses import replace
from typing import Literal

import numpy as np
import pandas as pd

from valuation.modelos import multiplos as mt

COLUNAS_ACOES = (
    "qt_acao_ordin_cap_integr",
    "qt_acao_pref_cap_integr",
    "qt_acao_total_cap_integr",
    "qt_acao_ordin_tesouro",
    "qt_acao_pref_tesouro",
    "qt_acao_total_tesouro",
)
DIAS_FALLBACK_ITR = 45
DIAS_FALLBACK_DFP = 90
TOLERANCIA_SPLITS = 0.05

Periodo = Literal["1 mês", "6 meses", "YTD", "1 ano", "5 anos", "Máximo"]
PERIODOS: tuple[Periodo, ...] = ("1 mês", "6 meses", "YTD", "1 ano", "5 anos", "Máximo")


def fator_splits(splits: pd.Series, data: pd.Timestamp) -> float:
    """F(data): produto dos fatores dos splits estritamente posteriores a `data`."""
    return float(splits[splits.index > pd.Timestamp(data)].astype("float64").to_numpy().prod())


def acoes_na_base_atual(composicao: pd.DataFrame, splits: pd.Series) -> pd.DataFrame:
    """Quantidades de cada linha vezes F(dt_refer): tudo na mesma base do `Close` do yfinance."""
    df = composicao.copy()
    fatores = pd.Series(
        [fator_splits(splits, d) for d in df["dt_refer"]], index=df.index, dtype="float64"
    )
    for coluna in COLUNAS_ACOES:
        if coluna in df.columns:
            df[coluna] = (df[coluna].astype("float64") * fatores).round().astype("int64")
    return df


def conferir_splits(
    composicao: pd.DataFrame, splits: pd.Series, tolerancia: float = TOLERANCIA_SPLITS
) -> list[str]:
    """Avisos onde a variação das ações da CVM não bate com os splits do yfinance no período.

    Pega salto sem split correspondente e split sem salto; emissão ou recompra acima da tolerância
    também aparece, porque daqui não dá para distingui-las de um split não listado.
    """
    avisos: list[str] = []
    df = composicao.sort_values("dt_refer")
    datas = list(df["dt_refer"])
    totais = list(df["qt_acao_total_cap_integr"].astype("float64"))
    for inicio, fim, q0, q1 in zip(datas, datas[1:], totais, totais[1:], strict=False):
        if q0 <= 0 or q1 <= 0:
            continue
        no_periodo = splits[(splits.index > inicio) & (splits.index <= fim)]
        esperado = float(no_periodo.prod())
        observado = q1 / q0
        if abs(observado / esperado - 1) > tolerancia:
            avisos.append(
                f"Ações da CVM variaram {observado:.2f}x entre {inicio:%d/%m/%Y} e {fim:%d/%m/%Y}, "
                f"mas os splits do yfinance dão {esperado:.2f}x: confira a série nesse trecho."
            )
    return avisos


def pontos_mensais(indice: pd.DatetimeIndex, base: dt.date, anos: int) -> pd.DatetimeIndex:
    """Último pregão de cada mês na janela de `anos` até a data-base."""
    fim = pd.Timestamp(base)
    inicio = fim - pd.DateOffset(years=anos)
    no_periodo = indice[(indice > inicio) & (indice <= fim)]
    if no_periodo.empty:
        return pd.DatetimeIndex([])
    serie = pd.Series(no_periodo, index=no_periodo)
    return pd.DatetimeIndex(serie.groupby(no_periodo.to_period("M")).max().to_numpy())


def datas_de_entrada(fins: Iterable[pd.Timestamp], divulgacoes: pd.DataFrame | None) -> pd.Series:
    """Quando o LTM de cada fim de período entra na série: a 1ª divulgação ou o fallback.

    `divulgacoes` tem `dt_refer` e `dt_receb`. Sem a data, fim do período + 45 dias (ITR) ou + 90
    dias (DFP, dezembro).
    """
    recebidas: dict[pd.Timestamp, pd.Timestamp] = {}
    if divulgacoes is not None and not divulgacoes.empty:
        primeiras = divulgacoes.groupby("dt_refer")["dt_receb"].min()
        recebidas = {pd.Timestamp(str(k)): pd.Timestamp(v) for k, v in primeiras.items()}
    entradas: dict[pd.Timestamp, pd.Timestamp] = {}
    for fim in sorted(pd.Timestamp(f) for f in fins):
        dias = DIAS_FALLBACK_DFP if fim.month == 12 else DIAS_FALLBACK_ITR
        entradas[fim] = recebidas.get(fim, fim + pd.Timedelta(days=dias))
    return pd.Series(entradas, dtype="datetime64[ns]")


def vigencia(pontos: pd.DatetimeIndex, entradas: pd.Series) -> pd.Series:
    """Para cada ponto, o fim de período do LTM mais recente já divulgado; NaT se nenhum."""
    resultado = []
    for ponto in pontos:
        vigentes = entradas[entradas <= ponto]
        resultado.append(vigentes.index.max() if not vigentes.empty else pd.NaT)
    return pd.Series(resultado, index=pontos, dtype="datetime64[ns]")


def serie_multiplo(
    nome: mt.NomeMultiplo,
    market_cap: pd.Series,
    vigentes: pd.Series,
    fundamentos: Mapping[pd.Timestamp, mt.Fundamentos],
) -> pd.Series:
    """Múltiplo em cada data, pela conta do `comparar` (`mt.multiplo`).

    Data sem market cap ou sem LTM, ou com denominador ≤ 0, fica NaN.
    """
    valores: dict[pd.Timestamp, float] = {}
    for data, cap in market_cap.items():
        fim = vigentes.get(data, pd.NaT)
        f = None if pd.isna(fim) else fundamentos.get(fim)
        if f is None or not np.isfinite(cap):
            valores[pd.Timestamp(str(data))] = float("nan")
        else:
            valores[pd.Timestamp(str(data))] = mt.multiplo(replace(f, market_cap=float(cap)), nome)
    return pd.Series(valores, dtype="float64", name=nome)


def denominador_nao_positivo(
    nome: mt.NomeMultiplo,
    vigentes: pd.Series,
    fundamentos: Mapping[pd.Timestamp, mt.Fundamentos],
) -> pd.Series:
    """Datas em que o múltiplo é NaN por métrica ≤ 0 (prejuízo, por exemplo), e não por lacuna."""
    metrica = mt.DEFINICOES[nome][1]
    marcas: dict[pd.Timestamp, bool] = {}
    for data, fim in vigentes.items():
        f = None if pd.isna(fim) else fundamentos.get(fim)
        marcas[pd.Timestamp(str(data))] = f is not None and bool(f.metrica(metrica) <= 0)
    return pd.Series(marcas, dtype="bool")


def cortar_periodo(serie: pd.DataFrame, periodo: Periodo, base: dt.date) -> pd.DataFrame:
    """Trecho da série no período até a data-base (GUI-12)."""
    fim = pd.Timestamp(base)
    inicios: dict[Periodo, pd.Timestamp] = {
        "1 mês": fim - pd.DateOffset(months=1),
        "6 meses": fim - pd.DateOffset(months=6),
        "YTD": pd.Timestamp(base.year, 1, 1),
        "1 ano": fim - pd.DateOffset(years=1),
        "5 anos": fim - pd.DateOffset(years=5),
        "Máximo": pd.Timestamp.min,
    }
    return serie[(serie.index >= inicios[periodo]) & (serie.index <= fim)]
