"""Beta da ação (seção 10.1 do guia): regressão semanal, Blume, comparáveis (Hamada) ou manual.

Funções puras: recebem séries de preço já baixadas (`adj_close`, ajustado por proventos) e a
data-base. Nada aqui consulta a rede.
"""

from __future__ import annotations

import datetime as dt
import statistics
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

import pandas as pd
import statsmodels.api as sm

from valuation.custo_capital import ErroCustoCapital

MIN_SEMANAS = 52  # abaixo disso a regressão não é feita
LIMIAR_SEMANAS_PARADAS = 0.10  # fração de semanas com retorno zero que indica baixa liquidez
MetodoBeta = Literal["regressao", "comparaveis", "manual"]


@dataclass(frozen=True)
class ResultadoBeta:
    """`beta` é o valor usado no CAPM (com Blume, se configurado); `beta_bruto` é o da OLS."""

    metodo: MetodoBeta
    beta: float
    beta_bruto: float | None = None
    erro_padrao: float | None = None
    r2: float | None = None
    n_obs: int | None = None
    inicio: dt.date | None = None
    fim: dt.date | None = None
    ticker: str | None = None
    avisos: tuple[str, ...] = ()


def blume(beta: float) -> float:
    """Ajuste de Blume: 0,67 x beta + 0,33 (puxa o beta em direção a 1)."""
    return 0.67 * beta + 0.33


def desalavancar(beta_alavancado: float, divida_sobre_equity: float, aliquota: float) -> float:
    """Hamada: beta_u = beta_L / (1 + (1 - t) x D/E)."""
    return beta_alavancado / (1 + (1 - aliquota) * divida_sobre_equity)


def realavancar(beta_desalavancado: float, divida_sobre_equity: float, aliquota: float) -> float:
    """Hamada: beta_L = beta_u x (1 + (1 - t) x D/E)."""
    return beta_desalavancado * (1 + (1 - aliquota) * divida_sobre_equity)


def precos_semanais(precos: pd.Series, data_base: dt.date) -> pd.Series:
    """Último preço de cada semana (sexta-feira), só com pregões até `data_base`."""
    serie = precos.loc[precos.index <= pd.Timestamp(data_base)].dropna()
    return serie.resample("W-FRI").last().dropna()


def classe_mais_liquida(
    historicos: Mapping[str, pd.DataFrame], data_base: dt.date, janela_semanas: int
) -> str:
    """Ticker com o maior volume financeiro mediano (close x volume) na janela do beta."""
    inicio = pd.Timestamp(data_base) - pd.Timedelta(weeks=janela_semanas)
    volumes: dict[str, float] = {}
    for ticker, hist in historicos.items():
        janela = hist.loc[(hist.index > inicio) & (hist.index <= pd.Timestamp(data_base))]
        financeiro = (janela["close"] * janela["volume"]).dropna()
        if not financeiro.empty:
            volumes[ticker] = float(financeiro.median())
    if not volumes:
        raise ErroCustoCapital(f"Sem preços na janela do beta para {', '.join(historicos)}.")
    return max(volumes, key=lambda t: volumes[t])


def regressao(
    acao: pd.Series,
    indice: pd.Series,
    *,
    data_base: dt.date,
    janela_semanas: int,
    ajuste_blume: bool,
    min_r2_aviso: float,
    ticker: str | None = None,
) -> ResultadoBeta:
    """OLS dos retornos semanais da ação contra o índice nas últimas `janela_semanas` semanas.

    `acao` e `indice` são preços diários ajustados (índice = data). Avisa se o R² ficar abaixo de
    `min_r2_aviso`, se a janela vier incompleta ou se muitas semanas não tiverem variação (ação
    pouco líquida: beta pouco confiável).
    """
    semanais = pd.concat(
        {"acao": precos_semanais(acao, data_base), "indice": precos_semanais(indice, data_base)},
        axis=1,
        join="inner",
    )
    retornos = semanais.pct_change().dropna().tail(janela_semanas)
    n = len(retornos)
    nome = ticker or "ação"
    if n < MIN_SEMANAS:
        raise ErroCustoCapital(
            f"Beta de {nome}: só {n} semanas de retorno até {data_base} (mínimo {MIN_SEMANAS})."
        )
    ajuste = sm.OLS(retornos["acao"], sm.add_constant(retornos["indice"])).fit()
    bruto = float(ajuste.params["indice"])
    r2 = float(ajuste.rsquared)

    avisos: list[str] = []
    if n < janela_semanas:
        avisos.append(f"Beta de {nome}: janela incompleta ({n} de {janela_semanas} semanas).")
    if r2 < min_r2_aviso:
        avisos.append(f"Beta de {nome}: R² de {r2:.2f} abaixo de {min_r2_aviso:.2f}.")
    paradas = float((retornos["acao"] == 0).mean())
    if paradas > LIMIAR_SEMANAS_PARADAS:
        avisos.append(
            f"Beta de {nome}: {paradas:.0%} das semanas sem variação de preço (baixa liquidez)."
        )
    return ResultadoBeta(
        metodo="regressao",
        beta=blume(bruto) if ajuste_blume else bruto,
        beta_bruto=bruto,
        erro_padrao=float(ajuste.bse["indice"]),
        r2=r2,
        n_obs=n,
        inicio=retornos.index[0].date(),
        fim=retornos.index[-1].date(),
        ticker=ticker,
        avisos=tuple(avisos),
    )


def comparaveis(
    pares: Mapping[str, tuple[float, float]],
    *,
    divida_sobre_equity_alvo: float,
    aliquota: float,
) -> ResultadoBeta:
    """Mediana dos betas desalavancados dos pares, realavancada na estrutura-alvo.

    `pares` = ticker -> (beta alavancado, D/E do par).
    """
    if not pares:
        raise ErroCustoCapital(
            "Beta por comparáveis sem pares medidos: confira `pares` em config/setores.yaml e "
            "rode `valuation atualizar --com-pares`."
        )
    desalavancados = [desalavancar(b, de, aliquota) for b, de in pares.values()]
    mediana = statistics.median(desalavancados)
    avisos = () if len(pares) >= 3 else (f"Beta por comparáveis com só {len(pares)} par(es).",)
    return ResultadoBeta(
        metodo="comparaveis",
        beta=realavancar(mediana, divida_sobre_equity_alvo, aliquota),
        beta_bruto=mediana,
        n_obs=len(pares),
        avisos=avisos,
    )


def manual(valor: float) -> ResultadoBeta:
    return ResultadoBeta(metodo="manual", beta=valor)
