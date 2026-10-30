"""Conciliação com os documentos das companhias (`tests/golden/referencias.yaml`, em R$ milhões).

Roda sobre os dados reais em `data/processed/cvm/` (fora do git): sem eles, os testes são pulados.
Rode `valuation atualizar --tickers PETR4,VALE3,WEGE3` antes.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import yaml

from valuation.config import DIR_PROCESSED
from valuation.contabil import nao_financeiras as nf
from valuation.contabil import padronizacao as pad
from valuation.contabil import periodos as per

REFERENCIAS = Path(__file__).parent / "golden" / "referencias.yaml"
CD_CVM = {"PETR4": 9512, "VALE3": 4170, "WEGE3": 5410}
MILHAO = 1e6
TOLERANCIA = {"PETR4": 0.5, "VALE3": 0.5, "WEGE3": 0.002}  # R$ mi (arredondamento dos releases)
TOLERANCIA_APROXIMADOS = 50.0

# Chave da referência -> métrica do pipeline. Fluxos: sinal da companhia (IR positivo).
FLUXOS = {
    "receita_liquida": lambda m: m["receita_liquida"],
    "lucro_controladora": lambda m: m["lucro_liquido_controladora"],
    "lucro_total": lambda m: m["lucro_liquido"],
    "da": lambda m: m["da"],
    "ebitda": lambda m: m["ebitda"],
    "ir_csll": lambda m: -m["ir_csll"],
}
SALDOS = {
    "divida_financeira_sem_arrendamento": lambda m: m["divida_financeira"],
    "arrendamento": lambda m: m["arrendamento"],
    "disponibilidades_cp": lambda m: m["caixa_e_aplicacoes"],
    "caixa_e_aplicacoes_cp": lambda m: m["caixa_e_aplicacoes"],
    "financiamentos": lambda m: m["divida_financeira"],
    "divida_bruta_com_arrendamento": lambda m: m["divida_financeira"] + m["arrendamento"],
    "arrendamento_cp": lambda m: m["arrendamento_cp"],
    "arrendamento_lp": lambda m: m["arrendamento"] - m["arrendamento_cp"],
    "financiamentos_cp": lambda c: c["emprestimos_cp"] - c["arrendamento_cp_em_emprestimos"],
    "financiamentos_lp": lambda c: c["emprestimos_lp"] - c["arrendamento_lp_em_emprestimos"],
    "aplicacoes_lp": lambda c: c["aplicacoes_financeiras_lp"],
}
# Definições próprias das companhias, fora do plano padronizado (dependem de `caixa_extra` e
# derivativos no YAML da empresa, Fase 5).
NAO_COMPARAVEIS = {
    "disponibilidades_ajustadas",
    "divida_liquida_companhia",
    "derivativos_liquidos",
    "caixa_liquido_companhia",
}


@cache
def _contas(ticker: str) -> pd.DataFrame:
    try:
        demonstracoes = pad.ler_demonstracoes(DIR_PROCESSED, CD_CVM[ticker])
    except FileNotFoundError:
        pytest.skip(f"sem dados de {ticker} em data/processed (rode `valuation atualizar`)")
    plano = pad.carregar_mapeamento()
    return pad.padronizar(pad.selecionar_reapresentacoes(demonstracoes), plano, ticker=ticker)


def _fluxos_do_periodo(ticker: str, periodo: str) -> pd.Series | None:
    """`2025` exercício, `1T26` trimestre, `1S26`/`9M26` acumulado no ano."""
    contas = _contas(ticker)
    if re.fullmatch(r"\d{4}", periodo):
        largo, data = per.anual(contas), int(periodo)
    else:
        n, tipo, aa = int(periodo[0]), periodo[1], int(periodo[2:])
        meses = {"T": 3 * n, "S": 6 * n, "M": n}[tipo]
        data = pd.Timestamp(year=2000 + aa, month=meses, day=1) + pd.offsets.MonthEnd(0)
        largo = (
            per.trimestral(contas)
            if tipo == "T"
            else per.acumulado_no_ano(contas).join(per.saldos(contas))
        )
    if data not in largo.index:
        return None
    return nf.metricas(largo.loc[[data]], aliquota_nominal=0.34).iloc[0]


def _saldos_na_data(ticker: str, data: str) -> tuple[pd.Series, pd.Series] | None:
    contas = _contas(ticker)
    largo = per.trimestral(contas)
    dt = pd.Timestamp(data)
    if dt not in largo.index:
        return None
    return nf.metricas(largo.loc[[dt]], aliquota_nominal=0.34).iloc[0], largo.loc[dt]


def _casos() -> list[Any]:
    refs = yaml.safe_load(REFERENCIAS.read_text(encoding="utf-8"))
    casos = []
    for ticker, ref in refs.items():
        tol = TOLERANCIA[ticker]
        for periodo, valores in (ref.get("periodos") or {}).items():
            for chave, valor in valores.items():
                casos.append(pytest.param(ticker, "fluxo", str(periodo), chave, valor, tol))
        for data, valores in (ref.get("saldos") or {}).items():
            for chave, valor in valores.items():
                casos.append(pytest.param(ticker, "saldo", str(data), chave, valor, tol))
        for periodo, valores in (ref.get("aproximados") or {}).items():
            tipo = "saldo" if "-" in str(periodo) else "fluxo"
            for chave, valor in valores.items():
                casos.append(
                    pytest.param(ticker, tipo, str(periodo), chave, valor, TOLERANCIA_APROXIMADOS)
                )
    return casos


@pytest.mark.parametrize("ticker, tipo, periodo, chave, esperado, tolerancia", _casos())
def test_conciliacao(
    ticker: str, tipo: str, periodo: str, chave: str, esperado: float, tolerancia: float
) -> None:
    if chave in NAO_COMPARAVEIS:
        pytest.skip(f"{chave}: definição própria da companhia")
    if tipo == "fluxo":
        metricas = _fluxos_do_periodo(ticker, periodo)
        if metricas is None:
            pytest.skip(f"{ticker} {periodo} ainda não está nos dados da CVM")
        obtido = FLUXOS[chave](metricas)
    else:
        resultado = _saldos_na_data(ticker, periodo)
        if resultado is None:
            pytest.skip(f"{ticker} {periodo} ainda não está nos dados da CVM")
        metricas, contas = resultado
        funcao = SALDOS[chave]
        try:
            obtido = funcao(metricas)
        except KeyError:
            obtido = funcao(contas.fillna(0))
    assert obtido / MILHAO == pytest.approx(esperado, abs=tolerancia)
