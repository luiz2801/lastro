"""Indicadores por ativo (RF-004, ADR 0020, Etapa C3): a "página por ativo" em forma de tabela.

Funções puras sobre as métricas já calculadas pela camada contábil e sobre os `Fundamentos` dos
múltiplos; nenhum valor existente de DCF, DDM ou múltiplos muda. Dois grupos:

- **Históricos** (`historicos`, `historicos_financeira`): razões entre contas do mesmo período,
  por exercício e no LTM. Os que já existiam (margem EBITDA, ROIC, ROE e payout das financeiras)
  são só reexpostos; os novos são margem líquida, dívida líquida/EBITDA e ROE das não financeiras.
- **De mercado** (`de_mercado`): P/L, P/VP, dividend yield, EV/EBITDA e EV/EBIT, calculados por
  `modelos.multiplos.multiplo` (a mesma conta do `comparar`), em LTM e market cap da data-base.

Convenções: razão com denominador não positivo é NaN (margem sobre receita ≤ 0, dívida
líquida/EBITDA com EBITDA ≤ 0, ROE com PL inicial ≤ 0). A margem líquida e o ROE usam o lucro e o
PL da **controladora**; o ROE usa o PL do início do período (como o das financeiras, LL_t =
ROE_t x PL_{t-1}). Dívida líquida/EBITDA usa o EBITDA ajustado (o mesmo do EV/EBITDA) e a dívida
líquida conforme `ajustes.ifrs16` (arrendamento incluído por padrão).

**Balanço e caixa** (`balanco_e_caixa`, ADR 0024; só na GUI): endividamento, liquidez e caixa das
não financeiras. Cada valor ausente vem com o motivo, porque falta de dado não pode virar zero.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from valuation.modelos import multiplos as mt

# Indicador -> (rótulo, unidade, chave do glossário).
HISTORICOS: dict[str, tuple[str, str, str]] = {
    "margem_liquida": ("Margem líquida", "%", "margem_liquida"),
    "margem_ebitda": ("Margem EBITDA", "%", "margem_ebitda"),
    "divida_liquida_ebitda": ("Dívida líquida / EBITDA", "x", "divida_liquida_ebitda"),
    "roe": ("ROE (PL inicial)", "%", "roe"),
    "roic": ("ROIC", "%", "roic"),
}
HISTORICOS_FINANCEIRA: dict[str, tuple[str, str, str]] = {
    "roe": ("ROE (PL inicial)", "%", "roe"),
    "payout": ("Payout", "%", "payout"),
    "roa": ("ROA", "%", "roa"),
    "alavancagem": ("Ativo / PL", "x", "alavancagem"),
}
# Múltiplos de mercado exibidos (todos existem em `modelos.multiplos`).
MERCADO: tuple[mt.NomeMultiplo, ...] = ("p_l", "p_vp", "dividend_yield", "ev_ebitda", "ev_ebit")
MERCADO_FINANCEIRA: tuple[mt.NomeMultiplo, ...] = mt.MULTIPLOS_FINANCEIRA


# Grupo -> indicador -> (rótulo, unidade, chave do glossário). "mi" = R$ milhões.
BALANCO: dict[str, dict[str, tuple[str, str, str]]] = {
    "Endividamento": {
        "divida_bruta_pl": ("Dívida bruta / PL", "x", "divida_bruta_pl"),
        "divida_liquida_pl": ("Dívida líquida / PL", "x", "divida_liquida_pl"),
        "divida_bruta_ebitda": ("Dívida bruta / EBITDA", "x", "divida_bruta_ebitda"),
        "divida_liquida_ebit": ("Dívida líquida / EBIT", "x", "divida_liquida_ebit"),
        "cobertura_juros": ("Cobertura de juros", "x", "cobertura_juros"),
        "passivos_ativos": ("Passivos / Ativos", "%", "passivos_ativos"),
        "pl_ativos": ("PL / Ativos", "%", "pl_ativos"),
        "perfil_divida": ("Dívida CP / Dívida bruta", "%", "perfil_divida"),
    },
    "Liquidez": {
        "liquidez_corrente": ("Liquidez corrente", "x", "liquidez_corrente"),
        "liquidez_seca": ("Liquidez seca", "x", "liquidez_seca"),
        "liquidez_imediata": ("Liquidez imediata", "x", "liquidez_imediata"),
        "liquidez_geral": ("Liquidez geral", "x", "liquidez_geral"),
    },
    "Caixa": {
        "caixa_aplicacoes": ("Caixa e aplicações (R$ mi)", "mi", "caixa_aplicacoes"),
        "caixa_divida_cp": ("Caixa / Dívida CP", "x", "caixa_divida_cp"),
        "caixa_ativo": ("Caixa / Ativos", "%", "caixa_ativo"),
        "conversao_cfo_ebitda": ("CFO / EBITDA", "%", "conversao_cfo_ebitda"),
        "conversao_fcf_lucro": ("FCF / Lucro", "%", "conversao_fcf_lucro"),
    },
}
MOTIVO_CONTA_AUSENTE = "conta ausente na demonstração"
MOTIVO_DIVIDA_FORA = (
    "empréstimos zerados, com despesa financeira na DRE: a dívida deve estar em outra linha "
    "(debêntures em Outras Obrigações, por exemplo)"
)


def _razao(numerador: pd.Series, denominador: pd.Series) -> pd.Series:
    """Numerador / denominador, NaN onde o denominador não é positivo."""
    return (numerador / denominador).where(denominador > 0).replace([np.inf, -np.inf], np.nan)


def historicos(m: pd.DataFrame) -> pd.DataFrame:
    """Indicadores de `contabil.nao_financeiras.metricas` (uma linha por período, ou o LTM).

    Aceita também `to_frame().T` do `metricas_ltm`. Colunas de `HISTORICOS`.
    """
    out = pd.DataFrame(index=m.index)
    out["margem_liquida"] = _razao(m["lucro_liquido_controladora"], m["receita_liquida"])
    out["margem_ebitda"] = m["margem_ebitda"].astype(float)
    out["divida_liquida_ebitda"] = _razao(m["divida_liquida"], m["ebitda_ajustado"])
    out["roe"] = _razao(m["lucro_liquido_controladora"], m["pl_controladora_inicio"])
    out["roic"] = m["roic"].astype(float)
    return out


def historicos_financeira(m: pd.DataFrame) -> pd.DataFrame:
    """Indicadores de `contabil.financeiras.metricas` (reexpostos sem mudar valor)."""
    return m.reindex(columns=list(HISTORICOS_FINANCEIRA)).astype(float)


def de_mercado(f: mt.Fundamentos, *, financeira: bool = False) -> dict[str, float]:
    """Múltiplos de mercado do ativo (NaN quando indefinidos, como no `comparar`)."""
    nomes = MERCADO_FINANCEIRA if financeira else MERCADO
    return {nome: mt.multiplo(f, nome) for nome in nomes}


def _conta(largo: pd.DataFrame, nome: str, opcional: bool = False) -> pd.Series:
    if nome in largo.columns:
        serie = largo[nome].astype(float)
    else:
        serie = pd.Series(np.nan, index=largo.index, dtype="float64")
    return serie.fillna(0.0) if opcional else serie


def balanco_e_caixa(
    largo: pd.DataFrame, m: pd.DataFrame, *, ifrs16: str = "divida"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Indicadores de `BALANCO` e o motivo de cada valor ausente, por período.

    `largo` = contas por período (`periodos.anual` ou LTM), `m` = `nao_financeiras.metricas` das
    mesmas linhas. Dívida com arrendamento conforme `ifrs16`, a mesma base da ponte. Base = PL
    total, porque a dívida é consolidada. Passivos = PC + PNC: a conta 2 da CVM inclui o PL e é
    igual ao ativo.
    """
    ativo = _conta(largo, "ativo_total")
    pc = _conta(largo, "passivo_circulante")
    pnc = _conta(largo, "passivo_nao_circulante")
    ac = _conta(largo, "ativo_circulante")
    pl = m["patrimonio_liquido_total"].astype(float)
    caixa = m["caixa_e_aplicacoes"].astype(float)
    bruta = m["divida_bruta"].astype(float)
    liquida = m["divida_liquida"].astype(float)
    despesa = -_conta(largo, "despesas_financeiras")
    em_emprestimos = _conta(largo, "arrendamento_cp_em_emprestimos", opcional=True)
    divida_cp = _conta(largo, "emprestimos_cp") - em_emprestimos
    if ifrs16 == "divida":
        divida_cp = (
            divida_cp + em_emprestimos + _conta(largo, "arrendamento_cp_outros", opcional=True)
        )
    divida_fora = (m["divida_financeira"].astype(float) == 0) & (despesa > 0)
    sem_pl = "PL não positivo"
    # Indicador -> (numerador, denominador, motivo quando o denominador não é positivo).
    razoes: dict[str, tuple[pd.Series, pd.Series, str]] = {
        "divida_bruta_pl": (bruta, pl, sem_pl),
        "divida_liquida_pl": (liquida, pl, sem_pl),
        "divida_bruta_ebitda": (bruta, m["ebitda_ajustado"], "EBITDA não positivo"),
        "divida_liquida_ebit": (liquida, m["ebit_ajustado"], "EBIT não positivo"),
        "cobertura_juros": (
            m["ebit_ajustado"],
            despesa,
            "a DRE não abre as despesas financeiras (conta zerada)",
        ),
        "passivos_ativos": (pc + pnc, ativo, "ativo não positivo"),
        "pl_ativos": (pl, ativo, "ativo não positivo"),
        "perfil_divida": (divida_cp, bruta, "sem dívida"),
        "liquidez_corrente": (ac, pc, "sem passivo circulante"),
        "liquidez_seca": (ac - _conta(largo, "estoques"), pc, "sem passivo circulante"),
        "liquidez_imediata": (caixa, pc, "sem passivo circulante"),
        "liquidez_geral": (ac + _conta(largo, "realizavel_lp"), pc + pnc, "sem passivo"),
        "caixa_divida_cp": (caixa, divida_cp, "sem dívida de curto prazo"),
        "caixa_ativo": (caixa, ativo, "ativo não positivo"),
        "conversao_cfo_ebitda": (m["cfo"], m["ebitda_ajustado"], "EBITDA não positivo"),
        "conversao_fcf_lucro": (
            m["fcf_caixa"],
            m["lucro_liquido_controladora"],
            "lucro não positivo",
        ),
    }
    baseadas_na_divida = {
        "divida_bruta_pl",
        "divida_liquida_pl",
        "divida_bruta_ebitda",
        "divida_liquida_ebit",
        "perfil_divida",
        "caixa_divida_cp",
    }
    valores = pd.DataFrame(index=m.index)
    motivos = pd.DataFrame(index=m.index, dtype="object")
    for nome, (numerador, denominador, motivo) in razoes.items():
        den = denominador.astype(float)
        num = numerador.astype(float)
        valor = _razao(num, den)
        texto = pd.Series(None, index=m.index, dtype="object")
        texto[den <= 0] = motivo
        texto[num.isna() | den.isna()] = MOTIVO_CONTA_AUSENTE
        if nome in baseadas_na_divida:
            valor = valor.where(~divida_fora)
            texto[divida_fora] = MOTIVO_DIVIDA_FORA
        valores[nome] = valor
        motivos[nome] = texto
    valores["caixa_aplicacoes"] = caixa
    motivos["caixa_aplicacoes"] = pd.Series(None, index=m.index, dtype="object").where(
        caixa.notna(), MOTIVO_CONTA_AUSENTE
    )
    return valores, motivos
