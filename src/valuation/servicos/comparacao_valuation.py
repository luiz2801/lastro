"""Valores do valuation do ativo contra pares, setor CVM e Ibovespa, só com rodadas já em `saida/`.

Cada grupo lê o `resumo.csv` e o `wacc.csv` da última rodada de cada empresa (sem rede e sem
recalcular nada). O que depende do perfil (upside, retorno esperado, VT) só entra na referência
quando a rodada da empresa usou o mesmo perfil da rodada do ativo: o perfil muda o horizonte, e
este muda o valor. Beta, Ke, Kd, WACC e g não dependem do perfil.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from valuation.analise import anomalias as an
from valuation.config import ConfigCsv, ErroConfiguracao, Setor
from valuation.data import cadastro as cad
from valuation.projecao import premissas as pm
from valuation.saida import favoritos as fav
from valuation.servicos import comparacao as scmp
from valuation.universo import EmpresaUniverso, SetorCVM, empresas_do_setor

GRUPO_PARES = "pares"
GRUPO_SETOR = "setor"
GRUPO_MERCADO = "mercado"
ROTULOS_GRUPO = {
    GRUPO_PARES: "Pares",
    GRUPO_SETOR: "Setor CVM",
    GRUPO_MERCADO: "Ibovespa",
}


@dataclass(frozen=True)
class Indicador:
    chave: str
    rotulo: str
    unidade: str  # "%" ou "" (número puro)
    arquivo: str  # resumo | wacc
    coluna: str  # coluna do resumo ou componente do wacc.csv
    modelos: tuple[str, ...] = ("dcf", "ddm")
    depende_do_perfil: bool = False


INDICADORES: tuple[Indicador, ...] = (
    Indicador("beta", "Beta", "", "wacc", "beta"),
    Indicador("ke", "Custo do equity (Ke)", "%", "resumo", "ke"),
    Indicador("kd", "Custo da dívida (Kd)", "%", "wacc", "kd", ("dcf",)),
    Indicador("wacc", "WACC", "%", "resumo", "wacc", ("dcf",)),
    Indicador("g", "Crescimento (g)", "%", "resumo", "g"),
    Indicador("upside", "Upside", "%", "resumo", "upside", depende_do_perfil=True),
    Indicador(
        "ke_implicito", "Retorno esperado", "%", "resumo", "ke_implicito", depende_do_perfil=True
    ),
    Indicador("vt", "VT / EV", "%", "resumo", "vt_sobre_ev", ("dcf",), True),
    Indicador("vt_ddm", "VT / valor", "%", "resumo", "vt_sobre_valor", ("ddm",), True),
)
POR_CHAVE = {i.chave: i for i in INDICADORES}


@dataclass(frozen=True)
class RodadaLida:
    """O que a comparação usa de uma rodada: modelo, perfil, data e os valores por indicador."""

    ticker: str
    data_base: dt.date
    perfil: str
    modelo: str
    valores: dict[str, float]


def _numero(valor: object) -> float:
    try:
        return float(valor)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float("nan")


def valores_da_rodada(resumo: pd.Series, wacc: pd.DataFrame | None) -> dict[str, float]:
    """Valor de cada indicador que a rodada tem; o que não existe fica de fora."""
    componentes: dict[str, float] = {}
    if wacc is not None and {"componente", "valor"} <= set(wacc.columns):
        componentes = {
            str(c): _numero(v) for c, v in zip(wacc["componente"], wacc["valor"], strict=True)
        }
    valores: dict[str, float] = {}
    for i in INDICADORES:
        valor = (
            _numero(resumo.get(i.coluna))
            if i.arquivo == "resumo"
            else componentes.get(i.coluna, float("nan"))
        )
        if pd.notna(valor):
            valores[i.chave] = valor
    return valores


def ler_rodada(ticker: str, config: ConfigCsv, dir_saida: Path) -> RodadaLida | None:
    """Última rodada em disco do ticker, só `resumo.csv` e `wacc.csv`; `None` sem rodada legível."""
    pasta = fav.pasta_mais_recente(ticker, dir_saida)
    if pasta is None:
        return None
    try:
        resumo = fav.ler_resumo(pasta / "resumo.csv", config).iloc[0]
        wacc = (
            fav.ler_csv_saida(pasta / "wacc.csv", config)
            if (pasta / "wacc.csv").is_file()
            else None
        )
        data_base = dt.date.fromisoformat(str(resumo["data_base"]))
    except (ValueError, KeyError, ErroConfiguracao, pd.errors.ParserError, IndexError):
        return None
    modelo = "dcf" if pd.isna(resumo.get("modelo")) else str(resumo["modelo"])
    perfil = "" if pd.isna(resumo.get("perfil")) else str(resumo["perfil"])
    return RodadaLida(ticker, data_base, perfil, modelo, valores_da_rodada(resumo, wacc))


def ler_rodadas(
    tickers: Sequence[str], config: ConfigCsv, dir_saida: Path
) -> dict[str, RodadaLida | None]:
    return {t: ler_rodada(t, config, dir_saida) for t in tickers}


@dataclass(frozen=True)
class ReferenciaValuation:
    valor: float
    n: int  # empresas com o indicador válido, depois do filtro de anomalias
    sem_rodada: tuple[str, ...] = ()
    outro_perfil: tuple[str, ...] = ()  # rodada existe, mas com perfil diferente do ativo
    anomalas: tuple[str, ...] = ()


def referencia_valuation(
    rodadas: Mapping[str, RodadaLida | None],
    indicador: Indicador,
    perfil: str,
    modelo: str,
    tipo: an.Referencia,
) -> ReferenciaValuation:
    """Mediana (ou a média escolhida) do indicador no grupo, com o filtro de anomalias dos gráficos.

    Só entra quem tem rodada do mesmo modelo (DCF e DDM não se misturam) e, nos indicadores que
    dependem do perfil, do mesmo perfil.
    """
    if modelo not in indicador.modelos:
        return ReferenciaValuation(float("nan"), 0)
    valores: dict[str, float] = {}
    sem_rodada: list[str] = []
    outro_perfil: list[str] = []
    for ticker, r in rodadas.items():
        if r is None:
            sem_rodada.append(ticker)
        elif r.modelo != modelo:
            continue
        elif indicador.depende_do_perfil and r.perfil != perfil:
            outro_perfil.append(ticker)
        elif indicador.chave in r.valores:
            valores[ticker] = r.valores[indicador.chave]
    filtro = an.filtrar(pd.Series(valores, dtype="float64"), an.Classe.PODE_NEGATIVO)
    return ReferenciaValuation(
        an.referencia(filtro, tipo),
        len(filtro.validos),
        tuple(sem_rodada),
        tuple(outro_perfil),
        tuple(str(k) for k in filtro.descartados.index),
    )


def grupos_de_comparacao(
    ticker: str,
    proprios: Sequence[str],
    premissas: pm.PremissasEmpresa,
    setor_pares: Setor | None,
    universo: Sequence[EmpresaUniverso],
) -> dict[str, list[str]]:
    """Tickers de cada grupo, sem as classes do próprio ativo.

    Pares: `setores.yaml` (+ incluir - excluir). Setor CVM: empresas do universo com o mesmo setor
    do cadastro da CVM e do mesmo tipo de modelo. Ibovespa: o universo todo do mesmo tipo.
    """
    fora = {cad.normalizar_ticker(t) for t in (ticker, *proprios)}
    pares = scmp.tickers_pares(premissas, (ticker, *proprios), setor_pares)
    meu = next((e for e in universo if e.ticker in fora), None)
    if meu is None:
        return {GRUPO_PARES: pares, GRUPO_SETOR: [], GRUPO_MERCADO: []}
    mesmo_tipo = [e for e in universo if e.tipo_modelo == meu.tipo_modelo]
    do_setor = empresas_do_setor(mesmo_tipo, meu.setor)
    return {
        GRUPO_PARES: pares,
        GRUPO_SETOR: [e.ticker for e in do_setor if e.ticker not in fora],
        GRUPO_MERCADO: [e.ticker for e in mesmo_tipo if e.ticker not in fora],
    }


def setor_do_ativo(ticker: str, universo: Sequence[EmpresaUniverso]) -> SetorCVM | None:
    return next((e.setor for e in universo if e.ticker == ticker), None)
