"""Preços de ações, Ibovespa e dólar, com duas fontes gratuitas para validação cruzada.

- Principal: `yfinance` (histórico com `Close` e `Adj Close`, sem ajuste automático).
- Alternativa: brapi.dev. Sem token só atende PETR4, VALE3, MGLU3 e ITUB4; com token gratuito
  (variável de ambiente `BRAPI_TOKEN`) atende o resto. Falha da brapi vira aviso, nunca erro.

O histórico do yfinance é cacheado em `data/raw/precos/` (parquet + `.meta.json`).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pandas as pd
import requests

from valuation.data.cadastro import Empresa
from valuation.data.http import SessaoHttp
from valuation.data.validacao import ErroDadosExternos, Leitura, Validado, cruzar

logger = logging.getLogger(__name__)

URL_BRAPI = "https://brapi.dev/api/quote/{simbolo}"
VARIAVEL_TOKEN_BRAPI = "BRAPI_TOKEN"
TOLERANCIA_DIAS_COTACAO = 4
COLUNAS_HISTORICO = ["close", "adj_close", "volume"]


class ErroPrecos(ErroDadosExternos):
    """Falha ao obter preços de um provedor."""


@dataclass(frozen=True)
class Cotacao:
    simbolo: str
    preco: float
    data: dt.date
    market_cap: float | None
    fonte: str


class PrecosProvider(Protocol):
    nome: str

    def historico(self, simbolo: str, inicio: dt.date, fim: dt.date) -> pd.DataFrame:
        """Diário, índice = data (sem fuso), colunas `COLUNAS_HISTORICO`."""
        ...

    def cotacao(self, simbolo: str) -> Cotacao:
        """Última cotação disponível."""
        ...


def simbolo_yahoo(ticker: str) -> str:
    """`PETR4` -> `PETR4.SA`; índices e câmbio (`^BVSP`, `BRL=X`) ficam como estão."""
    return ticker if ticker.startswith("^") or "=" in ticker or "." in ticker else f"{ticker}.SA"


class YFinanceProvider:
    nome = "yfinance"

    def __init__(
        self,
        dir_cache: Path,
        ttl: dt.timedelta,
        agora: dt.datetime,
        *,
        forcar: bool = False,
        tentativas: int = 3,
        espera: Callable[[float], None] = time.sleep,
    ) -> None:
        self._dir = dir_cache
        self._ttl = ttl
        self._agora = agora
        self._forcar = forcar
        self._tentativas = tentativas
        self._espera = espera

    def _baixar(self, simbolo: str, inicio: dt.date, fim: dt.date) -> pd.DataFrame:
        import yfinance as yf

        ultimo: Exception | None = None
        for n in range(1, self._tentativas + 1):
            try:
                bruto = yf.Ticker(simbolo).history(
                    start=inicio.isoformat(),
                    end=(fim + dt.timedelta(days=1)).isoformat(),
                    auto_adjust=False,
                )
            except Exception as e:  # yfinance levanta tipos variados
                ultimo = e
            else:
                if not bruto.empty:
                    df = pd.DataFrame(
                        {
                            "close": bruto["Close"],
                            "adj_close": bruto["Adj Close"],
                            "volume": bruto["Volume"],
                        }
                    )
                    df.index = pd.DatetimeIndex(bruto.index).tz_localize(None).normalize()
                    df.index.name = "data"
                    return df.astype("float64")
                ultimo = ErroPrecos("resposta vazia")
            logger.debug("yfinance %s tentativa %d/%d: %s", simbolo, n, self._tentativas, ultimo)
            if n < self._tentativas:
                self._espera(2.0**n)
        raise ErroPrecos(f"yfinance não devolveu dados de {simbolo}: {ultimo}")

    def historico(self, simbolo: str, inicio: dt.date, fim: dt.date) -> pd.DataFrame:
        base = f"{simbolo.replace('^', '_').replace('=', '_')}_{inicio:%Y%m%d}_{fim:%Y%m%d}"
        parquet = self._dir / f"yf_{base}.parquet"
        meta = parquet.with_suffix(".meta.json")
        if parquet.is_file() and meta.is_file() and not self._forcar:
            baixado = dt.datetime.fromisoformat(json.loads(meta.read_text())["baixado_em"])
            if self._agora - baixado < self._ttl:
                return pd.read_parquet(parquet)
        try:
            df = self._baixar(simbolo, inicio, fim)
        except ErroPrecos:
            if parquet.is_file() and not self._forcar:
                logger.warning("yfinance falhou para %s; usando cópia vencida do cache", simbolo)
                return pd.read_parquet(parquet)
            raise
        self._dir.mkdir(parents=True, exist_ok=True)
        df.to_parquet(parquet)
        meta.write_text(
            json.dumps({"simbolo": simbolo, "baixado_em": self._agora.isoformat()}),
            encoding="utf-8",
        )
        return df

    def cotacao(self, simbolo: str) -> Cotacao:
        df = self.historico(
            simbolo, (self._agora - dt.timedelta(days=10)).date(), self._agora.date()
        )
        return Cotacao(simbolo, float(df["close"].iloc[-1]), df.index[-1].date(), None, self.nome)


class BrapiProvider:
    nome = "brapi"

    def __init__(self, sessao: SessaoHttp, token: str | None = None) -> None:
        self._sessao = sessao
        self._token = token if token is not None else os.environ.get(VARIAVEL_TOKEN_BRAPI)

    def _consultar(self, simbolo: str, extra: str = "") -> dict[str, object]:
        url = URL_BRAPI.format(simbolo=simbolo.replace("^", "%5E"))
        params = [p for p in (extra, f"token={self._token}" if self._token else "") if p]
        if params:
            url += "?" + "&".join(params)
        try:
            r = self._sessao.get(url, headers={}, timeout=30, stream=False)
        except requests.RequestException as e:
            raise ErroPrecos(f"brapi: falha de rede para {simbolo}: {e}") from e
        try:
            corpo = r.json()
        except ValueError:
            corpo = {}
        if r.status_code != 200 or corpo.get("error"):
            dica = "" if self._token else f" (sem {VARIAVEL_TOKEN_BRAPI}; só 4 tickers sem token)"
            raise ErroPrecos(
                f"brapi {simbolo}: {corpo.get('message', f'HTTP {r.status_code}')}{dica}"
            )
        resultados = corpo.get("results") or []
        if not resultados:
            raise ErroPrecos(f"brapi {simbolo}: sem resultados")
        return dict(resultados[0])

    def cotacao(self, simbolo: str) -> Cotacao:
        r = self._consultar(simbolo)
        try:
            data = dt.datetime.fromisoformat(str(r["regularMarketTime"]).replace("Z", "+00:00"))
            cap = r.get("marketCap")
            return Cotacao(
                simbolo,
                float(r["regularMarketPrice"]),  # type: ignore[arg-type]
                data.date(),
                float(cap) if cap else None,  # type: ignore[arg-type]
                self.nome,
            )
        except (KeyError, TypeError, ValueError) as e:
            raise ErroPrecos(f"brapi {simbolo}: resposta inesperada ({e})") from e

    def historico(self, simbolo: str, inicio: dt.date, fim: dt.date) -> pd.DataFrame:
        anos = max(1, (fim - inicio).days // 365 + 1)
        r = self._consultar(simbolo, f"range={anos}y&interval=1d")
        linhas = r.get("historicalDataPrice")
        if not isinstance(linhas, list) or not linhas:
            raise ErroPrecos(f"brapi {simbolo}: sem histórico (plano gratuito é limitado)")
        df = pd.DataFrame(linhas)
        indice = pd.to_datetime(df["date"], unit="s").dt.normalize()
        saida = pd.DataFrame(
            {
                "close": df["close"].astype("float64"),
                "adj_close": df.get("adjustedClose", df["close"]).astype("float64"),
                "volume": df["volume"].astype("float64"),
            }
        ).set_index(pd.DatetimeIndex(indice, name="data"))
        return saida.loc[(saida.index >= pd.Timestamp(inicio)) & (saida.index <= pd.Timestamp(fim))]


def fechamento_ate(hist: pd.DataFrame, data_base: dt.date) -> tuple[dt.date, float]:
    """Último `Close` (não ajustado por dividendos) com data <= `data_base`."""
    valido = hist.loc[hist.index <= pd.Timestamp(data_base), "close"].dropna()
    if valido.empty:
        raise ErroPrecos(f"Sem preço até {data_base}")
    return valido.index[-1].date(), float(valido.iloc[-1])


def preco_validado(
    ticker: str,
    data_base: dt.date,
    principal: PrecosProvider,
    alternativo: PrecosProvider | None,
    *,
    tolerancia_rel: float,
    janela_dias: int = 15,
) -> Validado:
    """Fechamento em `data_base` pelo provedor principal, conferido com a cotação do alternativo.

    O alternativo só informa a cotação atual, então só entra na comparação se a data dela
    estiver a até `TOLERANCIA_DIAS_COTACAO` dias do fechamento principal.
    """
    hist = principal.historico(
        simbolo_yahoo(ticker), data_base - dt.timedelta(days=janela_dias), data_base
    )
    data, preco = fechamento_ate(hist, data_base)
    lido = Leitura(preco, principal.nome, data)

    alt: Leitura | None = None
    if alternativo is not None:
        try:
            c = alternativo.cotacao(ticker)
        except ErroDadosExternos as e:
            logger.warning("Preço de %s sem segunda fonte: %s", ticker, e)
        else:
            if abs((c.data - data).days) <= TOLERANCIA_DIAS_COTACAO:
                alt = Leitura(c.preco, alternativo.nome, c.data)
            else:
                logger.info(
                    "Cotação %s de %s (%s) distante do fechamento (%s); não comparada",
                    alternativo.nome,
                    ticker,
                    c.data,
                    data,
                )
    return cruzar(f"Preço {ticker}", lido, alt, tolerancia=tolerancia_rel, relativa=True)


@dataclass(frozen=True)
class ClasseMarketCap:
    ticker: str
    especie: str
    acoes: int
    preco: float


@dataclass(frozen=True)
class MarketCap:
    valor: float
    classes: tuple[ClasseMarketCap, ...]
    data_acoes: dt.date
    avisos: tuple[str, ...]


def market_cap(
    empresa: Empresa,
    composicao: pd.DataFrame,
    precos: dict[str, float],
    data_base: dt.date,
) -> MarketCap:
    """Soma `ações em circulação vezes preço` por espécie (ON e PN), sem tesouraria.

    `composicao` é o `composicao_capital.parquet` da companhia. A composição da CVM só separa
    ON e PN; units não podem ser decompostas e são ignoradas. Se uma espécie com ações não
    tiver ticker cotado, usa-se o preço da outra espécie, com aviso (aproximação).
    """
    disponivel = composicao.loc[composicao["dt_refer"] <= pd.Timestamp(data_base)]
    if disponivel.empty:
        raise ErroPrecos(f"{empresa.razao_social}: sem composição do capital até {data_base}")
    ult = disponivel.sort_values("dt_refer").iloc[-1]
    quantidades = {
        "ON": int(ult["qt_acao_ordin_cap_integr"]) - int(ult["qt_acao_ordin_tesouro"]),
        "PN": int(ult["qt_acao_pref_cap_integr"]) - int(ult["qt_acao_pref_tesouro"]),
    }
    cotados = {
        esp: next(
            (c.ticker for c in empresa.classes if c.especie == esp and c.ticker in precos), None
        )
        for esp in quantidades
    }
    if not any(cotados.values()):
        raise ErroPrecos(f"{empresa.tickers}: nenhuma classe ON/PN com preço disponível")

    avisos: list[str] = []
    classes: list[ClasseMarketCap] = []
    for esp, qtd in quantidades.items():
        if qtd <= 0:
            continue
        ticker = cotados[esp]
        if ticker is None:
            ticker = next(t for t in cotados.values() if t is not None)
            avisos.append(
                f"{qtd:,} ações {esp} sem ticker cotado; usado o preço de {ticker}".replace(
                    ",", "."
                )
            )
        classes.append(ClasseMarketCap(ticker, esp, qtd, precos[ticker]))
    return MarketCap(
        sum(c.acoes * c.preco for c in classes),
        tuple(classes),
        ult["dt_refer"].date(),
        tuple(avisos),
    )
