"""Preços, market cap e macro de uma empresa na data-base."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from valuation.config import DIR_PROCESSED, DIR_RAW, Settings
from valuation.data import cadastro as cad
from valuation.data import macro as mac
from valuation.data import precos as prc
from valuation.data.http import SessaoHttp
from valuation.data.validacao import ErroDadosExternos, Leitura, Validado


@dataclass(frozen=True)
class Mercado:
    empresa: cad.Empresa
    precos: dict[str, Validado]
    ibov: Validado
    macro: mac.Macro
    cap: prc.MarketCap
    yf: prc.YFinanceProvider
    avisos_coleta: list[str] = field(default_factory=list)
    """Dados que faltaram na coleta: classe sem preço, dólar sem segunda fonte."""

    @property
    def avisos(self) -> list[str]:
        """Avisos sobre os dados obtidos (market cap, macro, divergência entre as fontes)."""
        validados = (*self.precos.values(), self.ibov)
        return [*self.cap.avisos, *self.macro.avisos, *(a for v in validados if (a := v.aviso))]

    @property
    def todos_os_avisos(self) -> list[str]:
        return [*self.avisos_coleta, *self.avisos]


def carregar_macro(
    settings: Settings,
    base: dt.date,
    agora: dt.datetime,
    forcar: bool,
    yf: prc.PrecosProvider,
    *,
    sessao: SessaoHttp,
    dir_raw: Path = DIR_RAW,
) -> tuple[mac.Macro, list[str]]:
    """Macro na data-base e avisos; o dólar do yfinance é a segunda fonte do câmbio."""
    avisos: list[str] = []
    cambio_yf: Leitura | None = None
    try:
        d, v = prc.fechamento_ate(yf.historico("BRL=X", base - dt.timedelta(days=15), base), base)
        cambio_yf = Leitura(v, "yfinance BRL=X", d)
    except ErroDadosExternos as e:
        avisos.append(f"dólar sem segunda fonte: {e}")
    try:
        macro = mac.carregar_macro(
            base,
            tolerancias=settings.validacao_cruzada,
            rf_override=settings.custo_capital.rf_brl.override,
            cambio_alternativo=cambio_yf,
            dir_raw=dir_raw,
            ttl=dt.timedelta(hours=settings.cache_ttl_horas.macro),
            sessao=sessao,
            agora=agora,
            forcar=forcar,
        )
    except Exception as e:
        _anexar_avisos(e, avisos)
        raise
    return macro, avisos


def cotacoes(
    empresa: cad.Empresa,
    settings: Settings,
    base: dt.date,
    yf: prc.PrecosProvider,
    brapi: prc.PrecosProvider,
    *,
    dir_processed: Path = DIR_PROCESSED,
) -> tuple[dict[str, Validado], prc.MarketCap, list[str]]:
    """Preço de cada classe (2 fontes), market cap na data-base e avisos."""
    avisos: list[str] = []
    try:
        precos: dict[str, Validado] = {}
        for classe in empresa.classes:
            try:
                precos[classe.ticker] = prc.preco_validado(
                    classe.ticker,
                    base,
                    yf,
                    brapi,
                    tolerancia_rel=settings.validacao_cruzada.preco_rel,
                )
            except ErroDadosExternos as e:
                avisos.append(f"{classe.ticker} sem preço: {e}")
        if not precos:
            raise ErroDadosExternos(f"Nenhum preço disponível para {', '.join(empresa.tickers)}.")
        try:
            composicao = pd.read_parquet(
                dir_processed / "cvm" / str(empresa.cd_cvm) / "composicao_capital.parquet"
            )
        except FileNotFoundError as e:
            raise ErroDadosExternos(
                f"{e.filename} não existe. Rode `valuation atualizar --tickers "
                f"{empresa.tickers[0]}`."
            ) from e
        cap = prc.market_cap(empresa, composicao, {t: p.valor for t, p in precos.items()}, base)
    except Exception as e:
        _anexar_avisos(e, avisos)
        raise
    return precos, cap, avisos


def carregar_mercado(
    ticker: str,
    cadastro: pd.DataFrame,
    settings: Settings,
    base: dt.date,
    agora: dt.datetime,
    forcar: bool,
    *,
    sessao: SessaoHttp,
    dir_raw: Path = DIR_RAW,
    dir_processed: Path = DIR_PROCESSED,
) -> Mercado:
    """Preço por classe, Ibovespa, macro e market cap na data-base, cada um em 2 fontes.

    Se falhar depois de um aviso, ele segue nas notas da exceção (`__notes__`), na ordem em que
    surgiu.
    """
    empresa = cad.empresa_por_ticker(cadastro, ticker)
    yf = prc.YFinanceProvider(
        dir_raw / "precos",
        dt.timedelta(hours=settings.cache_ttl_horas.precos),
        agora,
        forcar=forcar,
    )
    brapi = prc.BrapiProvider(sessao)
    avisos: list[str] = []
    try:
        precos, cap, de_cotacoes = cotacoes(
            empresa, settings, base, yf, brapi, dir_processed=dir_processed
        )
        avisos += de_cotacoes
        ibov = prc.preco_validado(
            "^BVSP", base, yf, brapi, tolerancia_rel=settings.validacao_cruzada.preco_rel
        )
        macro, de_macro = carregar_macro(
            settings, base, agora, forcar, yf, sessao=sessao, dir_raw=dir_raw
        )
        avisos += de_macro
    except Exception as e:
        _anexar_avisos(e, avisos)
        raise
    return Mercado(empresa, precos, ibov, macro, cap, yf, avisos)


def _anexar_avisos(erro: Exception, avisos: list[str]) -> None:
    """Põe `avisos` antes das notas que `erro` já traz: a ordem é a de quando surgiram."""
    erro.__notes__ = [*avisos, *getattr(erro, "__notes__", [])]
