"""Anomalias na referência dos gráficos da GUI (`guia_de_tratamento_de_anomalias_...md`, ADR 0023).

Funções puras, usadas só pela GUI: o `comparar` e `modelos/multiplos.py` seguem com a própria
winsorização. A série nunca é apagada: `descartados` guarda cada ponto fora e o motivo.

- Múltiplo sempre positivo: ≤ 0 sai; com n ≥ 15, Log-IQR com corte `exp(Q3 + 1,5·IQR)` em ln; com
  n < 15, corte fixo do parâmetro. O guia escreve Q1 na seção 4, passo 2; o correto é Q3 (seção 3).
- Métrica que pode ser negativa: IQR de Tukey nos dois lados, na escala linear.
- Dividend yield, payout e liquidez: nada sai, só se marcam os pontos fora de 1,5·IQR.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

import numpy as np
import pandas as pd

N_MINIMO_IQR = 15
N_MINIMO_TUKEY = 4
MULTIPLICADOR_IQR = 1.5


class Classe(StrEnum):
    POSITIVO = "positivo"
    PODE_NEGATIVO = "pode_negativo"
    SO_MARCAR = "so_marcar"


CLASSES: dict[str, Classe] = {
    "p_l": Classe.POSITIVO,
    "p_vp": Classe.POSITIVO,
    "ev_ebitda": Classe.POSITIVO,
    "ev_ebit": Classe.POSITIVO,
    "ev_receita": Classe.POSITIVO,
    "margem_liquida": Classe.PODE_NEGATIVO,
    "margem_ebitda": Classe.PODE_NEGATIVO,
    "roe": Classe.PODE_NEGATIVO,
    "roic": Classe.PODE_NEGATIVO,
    "divida_liquida_ebitda": Classe.PODE_NEGATIVO,
    "dividend_yield": Classe.SO_MARCAR,
    "payout": Classe.SO_MARCAR,
    "divida_bruta_pl": Classe.PODE_NEGATIVO,
    "divida_liquida_pl": Classe.PODE_NEGATIVO,
    "divida_bruta_ebitda": Classe.PODE_NEGATIVO,
    "divida_liquida_ebit": Classe.PODE_NEGATIVO,
    "cobertura_juros": Classe.PODE_NEGATIVO,
    "conversao_cfo_ebitda": Classe.PODE_NEGATIVO,
    "conversao_fcf_lucro": Classe.PODE_NEGATIVO,
    "passivos_ativos": Classe.SO_MARCAR,
    "pl_ativos": Classe.SO_MARCAR,
    "perfil_divida": Classe.SO_MARCAR,
    "caixa_divida_cp": Classe.SO_MARCAR,
    "caixa_ativo": Classe.SO_MARCAR,
    "liquidez_corrente": Classe.SO_MARCAR,
    "liquidez_seca": Classe.SO_MARCAR,
    "liquidez_imediata": Classe.SO_MARCAR,
    "liquidez_geral": Classe.SO_MARCAR,
}
ALTERNATIVAS = {
    "abaixo": "EV/EBITDA, se a operação for lucrativa, ou EV/Receita",
    "acima": "confira se o lucro está baixo de forma não recorrente; com crescimento alto, PEG",
}

Referencia = Literal["mediana", "media_winsorizada", "media_simples"]
ROTULOS_REFERENCIA: dict[Referencia, str] = {
    "mediana": "Mediana",
    "media_winsorizada": "Média winsorizada",
    "media_simples": "Média simples",
}
AVISO_MEDIA_SIMPLES = "A média simples é sensível a extremos; prefira a mediana."


@dataclass(frozen=True)
class Filtro:
    classe: Classe
    metodo: str  # log_iqr | corte_fixo | tukey | marcacao | sem_corte
    limite_inferior: float | None
    limite_superior: float | None
    amostra: pd.Series  # sem lacunas nem ≤ 0 (positivos); base da média winsorizada
    validos: pd.Series
    descartados: pd.Series  # data/empresa -> motivo; lacuna (NaN) não conta
    marcados: pd.Series  # fora de 1,5·IQR, mas mantidos (`SO_MARCAR`)


def _quartis(valores: pd.Series) -> tuple[float, float]:
    q1, q3 = np.quantile(valores.to_numpy(dtype="float64"), [0.25, 0.75])
    return float(q1), float(q3)


def _limites_tukey(valores: pd.Series) -> tuple[float, float]:
    q1, q3 = _quartis(valores)
    faixa = MULTIPLICADOR_IQR * (q3 - q1)
    return q1 - faixa, q3 + faixa


def _corte_log_iqr(valores: pd.Series) -> float:
    q1, q3 = _quartis(np.log(valores))
    return float(np.exp(q3 + MULTIPLICADOR_IQR * (q3 - q1)))


def _texto(valor: float) -> str:
    return f"{valor:.1f}".replace(".", ",")


def _filtrar_positivo(serie: pd.Series, corte_fixo: float | None) -> Filtro:
    invalidos = serie[serie <= 0]
    motivos = {i: "múltiplo ≤ 0" for i in invalidos.index}
    amostra = serie[serie > 0]
    if len(amostra) >= N_MINIMO_IQR:
        metodo, corte = "log_iqr", _corte_log_iqr(amostra)
    elif corte_fixo is not None:
        metodo, corte = "corte_fixo", corte_fixo
    else:
        metodo, corte = "sem_corte", None
    validos = amostra
    if corte is not None:
        acima = amostra[amostra > corte]
        motivos.update(dict.fromkeys(acima.index, f"acima do corte ({_texto(corte)}x)"))
        validos = amostra[amostra <= corte]
    return Filtro(
        Classe.POSITIVO,
        metodo,
        None,
        corte,
        amostra,
        validos,
        pd.Series(motivos, dtype="object").reindex(serie.index).dropna(),
        pd.Series(dtype="float64"),
    )


def _filtrar_tukey(serie: pd.Series) -> Filtro:
    vazio = pd.Series(dtype="object")
    if len(serie) < N_MINIMO_TUKEY:
        return Filtro(
            Classe.PODE_NEGATIVO,
            "sem_corte",
            None,
            None,
            serie,
            serie,
            vazio,
            pd.Series(dtype="float64"),
        )
    inferior, superior = _limites_tukey(serie)
    fora = (serie < inferior) | (serie > superior)
    motivos = {
        i: f"abaixo do limite ({_texto(inferior)})"
        if serie[i] < inferior
        else f"acima do limite ({_texto(superior)})"
        for i in serie[fora].index
    }
    return Filtro(
        Classe.PODE_NEGATIVO,
        "tukey",
        inferior,
        superior,
        serie,
        serie[~fora],
        pd.Series(motivos, dtype="object"),
        pd.Series(dtype="float64"),
    )


def _filtrar_marcacao(serie: pd.Series) -> Filtro:
    vazio = pd.Series(dtype="object")
    if len(serie) < N_MINIMO_TUKEY:
        return Filtro(
            Classe.SO_MARCAR,
            "marcacao",
            None,
            None,
            serie,
            serie,
            vazio,
            pd.Series(dtype="float64"),
        )
    inferior, superior = _limites_tukey(serie)
    marcados = serie[(serie < inferior) | (serie > superior)]
    return Filtro(Classe.SO_MARCAR, "marcacao", inferior, superior, serie, serie, vazio, marcados)


def filtrar(serie: pd.Series, classe: Classe, corte_fixo: float | None = None) -> Filtro:
    """Aplica o tratamento da `classe`. Lacunas (NaN) saem antes e não contam como descartadas."""
    sem_lacunas = serie.dropna().astype("float64")
    if classe is Classe.POSITIVO:
        return _filtrar_positivo(sem_lacunas, corte_fixo)
    if classe is Classe.PODE_NEGATIVO:
        return _filtrar_tukey(sem_lacunas)
    return _filtrar_marcacao(sem_lacunas)


def referencia(filtro: Filtro, tipo: Referencia) -> float:
    """Estatística de referência; NaN se não houver ponto válido.

    A média winsorizada leva os pontos da amostra aos limites do filtro em vez de descartá-los.
    """
    if filtro.validos.empty:
        return float("nan")
    if tipo == "mediana":
        return float(filtro.validos.median())
    if tipo == "media_simples":
        return float(filtro.validos.mean())
    return float(filtro.amostra.clip(filtro.limite_inferior, filtro.limite_superior).mean())


def sugestao_alternativa(motivo: str) -> str:
    """O que olhar no lugar de um ponto descartado (guia, seção 7)."""
    chave = "abaixo" if "≤ 0" in motivo else "acima"
    return ALTERNATIVAS[chave]
