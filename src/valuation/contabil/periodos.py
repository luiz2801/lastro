"""Visões em formato largo (uma coluna por conta padrão) derivadas de `contas_padronizadas`.

Fluxos (DRE, DFC, DVA) só existem na CVM como exercício (DFP), acumulado no ano (ITR) e, na DRE,
trimestre. Tudo aqui parte do **acumulado no ano** (YTD; o exercício é o YTD de dezembro):

- trimestre = YTD do trimestre - YTD do trimestre anterior do mesmo ano;
- LTM = último exercício + YTD atual - YTD do mesmo período do ano anterior.

Saldos (BPA, BPP) são lidos na própria data. Todas as funções supõem exercício social de janeiro a
dezembro (o caso de todas as companhias da B3 vistas até aqui).
"""

from __future__ import annotations

from typing import cast

import numpy as np
import numpy.typing as npt
import pandas as pd

from valuation.contabil import ErroContabil


def _eh_fim_de_ano(datas: pd.Index) -> npt.NDArray[np.bool_]:
    indice = pd.DatetimeIndex(datas)
    return np.asarray((indice.month == 12) & (indice.day == 31))


def _largo(longo: pd.DataFrame) -> pd.DataFrame:
    largo = longo.pivot_table(
        index="dt_fim", columns="conta_padrao", values="valor", aggfunc="first"
    )
    largo.columns.name = None
    return largo.sort_index()


def saldos(contas: pd.DataFrame) -> pd.DataFrame:
    """Saldos de balanço por data (índice `dt_fim`)."""
    return _largo(contas[contas["periodicidade"] == "S"])


def acumulado_no_ano(contas: pd.DataFrame) -> pd.DataFrame:
    """Fluxos acumulados desde 1º de janeiro, por data final (dezembro = exercício)."""
    fluxos = contas[contas["periodicidade"] != "S"]
    inicio_do_ano = (fluxos["dt_ini"].dt.month == 1) & (fluxos["dt_ini"].dt.day == 1)
    mesmo_ano = fluxos["dt_ini"].dt.year == fluxos["dt_fim"].dt.year
    return _largo(fluxos[inicio_do_ano & mesmo_ano])


def anual(contas: pd.DataFrame) -> pd.DataFrame:
    """Exercícios: fluxos de janeiro a dezembro e saldos em 31/12. Índice = ano (int)."""
    ytd = acumulado_no_ano(contas)
    bal = saldos(contas)
    partes = [df[_eh_fim_de_ano(df.index)] for df in (ytd, bal)]
    largo = pd.concat(partes, axis=1)
    largo.index = pd.Index(pd.DatetimeIndex(largo.index).year, name="ano")
    return largo


def trimestral(contas: pd.DataFrame) -> pd.DataFrame:
    """Fluxos do trimestre e saldos no fim do trimestre. Índice = data final do trimestre.

    Trimestre sem o YTD anterior do mesmo ano fica NaN (ex.: 4T sem o ITR do 3T).
    """
    ytd = acumulado_no_ano(contas)
    ytd = ytd[pd.DatetimeIndex(ytd.index).month.isin([3, 6, 9, 12])]
    anterior = ytd.copy()
    anterior.index = pd.DatetimeIndex(anterior.index) + pd.offsets.QuarterEnd(1)
    trimestre = ytd - anterior.reindex(ytd.index)
    primeiro = pd.DatetimeIndex(ytd.index).month == 3
    trimestre.loc[primeiro] = ytd.loc[primeiro]
    bal = saldos(contas)
    return pd.concat([trimestre, bal.reindex(trimestre.index)], axis=1)


def data_mais_recente(contas: pd.DataFrame) -> pd.Timestamp:
    """Última data com fluxos acumulados e balanço ao mesmo tempo."""
    comuns = acumulado_no_ano(contas).index.intersection(saldos(contas).index)
    if comuns.empty:
        raise ErroContabil("Nenhuma data com DRE/DFC e balanço ao mesmo tempo.")
    return pd.Timestamp(comuns.max())


def ltm(contas: pd.DataFrame, dt_fim: pd.Timestamp | None = None) -> pd.Series:
    """Últimos 12 meses até `dt_fim` (padrão: `data_mais_recente`): fluxos LTM e saldos na data.

    Conta com algum componente ausente sai NaN. Falta de um período inteiro é erro.
    """
    fim = pd.Timestamp(dt_fim) if dt_fim is not None else data_mais_recente(contas)
    ytd = acumulado_no_ano(contas)
    bal = saldos(contas)
    if fim not in bal.index:
        raise ErroContabil(f"Sem balanço em {fim.date()}.")
    if _eh_fim_de_ano(pd.DatetimeIndex([fim]))[0]:
        necessarios = [fim]
    else:
        necessarios = [
            pd.Timestamp(year=fim.year - 1, month=12, day=31),
            fim,
            fim - pd.DateOffset(years=1),
        ]
    faltando = [d.date().isoformat() for d in necessarios if d not in ytd.index]
    if faltando:
        raise ErroContabil(f"LTM em {fim.date()} precisa dos acumulados de {', '.join(faltando)}.")
    linhas = [cast(pd.Series, ytd.loc[d]) for d in necessarios]
    fluxos = linhas[0] if len(linhas) == 1 else linhas[0] + linhas[1] - linhas[2]
    serie: pd.Series = pd.concat([fluxos, cast(pd.Series, bal.loc[fim])])
    serie.name = fim
    return serie
