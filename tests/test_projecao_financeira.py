"""Sugestões, premissas, cenários e projeção do DDM (projecao/financeira.py)."""

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from valuation.projecao import ErroProjecao, escrita
from valuation.projecao import financeira as pf
from valuation.projecao import premissas as pm
from valuation.projecao.sugestor import Sugestao

G = Sugestao(0.05, "g terminal = settings.terminal.g_nominal_max")
MINIMO = {"ticker": "BANC4", "tipo_modelo": "financeira", "classes_acao": ["BANC4"]}


def historico(roe: list[float], payout: list[float], inicio: int = 2016) -> pd.DataFrame:
    anos = pd.RangeIndex(inicio, inicio + len(roe), name="ano")
    return pd.DataFrame({"roe": roe, "payout": payout}, index=anos)


ROE = [0.10, 0.12, 0.14, 0.16, 0.18, 0.20, 0.22, 0.24, 0.26, 0.28]
PAYOUT = [0.3, 0.3, 0.3, 0.3, 0.3, 0.4, 0.6, 0.5, 1.4, 0.7]


def test_sugerir_calculado_a_mao() -> None:
    s = pf.sugerir(historico(ROE, PAYOUT), g_terminal=G)
    assert s.ano_base == 2025
    assert s.roe_inicio.valor == pytest.approx(0.24)  # mediana de 0,20..0,28
    assert s.roe_fim.valor == pytest.approx(0.19)  # mediana de 0,10..0,28
    assert s.roe_inicio.origem == "mediana do ROE 2021-2025"
    assert s.payout_inicio.valor == pytest.approx(0.6)  # mediana de 0,4 0,6 0,5 1,4 0,7
    assert np.std(ROE, ddof=1) > 0.05
    assert s.delta_roe.valor == 0.05  # 1 desvio-padrão (6,06 p.p.) limitado ao teto
    assert "limitado a [1,00 p.p., 5,00 p.p.]" in s.delta_roe.origem
    assert s.g_terminal == G
    assert s.avisos == ()
    assert s.estatisticas.at["ultimo", "payout"] == pytest.approx(0.7)


def test_sugerir_limites_e_avisos() -> None:
    curto = historico([np.nan, 0.03], [np.nan, np.nan], inicio=2024)
    s = pf.sugerir(curto, g_terminal=G)
    assert s.delta_roe.valor == pytest.approx(0.01)  # piso
    assert any("ROE de longo prazo sugerido (3,0%)" in a for a in s.avisos)
    assert any("Sem dividendos" in a for a in s.avisos)
    assert s.payout_inicio.valor == 1.0  # ROE <= g: sem payout sustentável, limite
    alto = pf.sugerir(historico([0.2, 0.2], [1.5, 1.5]), g_terminal=G)
    assert alto.payout_inicio.valor == 1.0
    assert "limitada a [0%, 100%]" in alto.payout_inicio.origem
    with pytest.raises(ErroProjecao, match="Sem ROE"):
        pf.sugerir(historico([np.nan], [0.5]), g_terminal=G)


def test_payout_final() -> None:
    assert pf.payout_final(0.20, 0.05) == pytest.approx(0.75)
    with pytest.raises(ErroProjecao, match="não supera o g"):
        pf.payout_final(0.05, 0.05)


def _sugestoes() -> pf.SugestoesFinanceira:
    return pf.sugerir(historico(ROE, PAYOUT), g_terminal=G)


def test_resolver_e_cenarios() -> None:
    anos = pf.anos_projetados(dt.date(2026, 10, 30), 3)
    assert anos == (2026, 2027, 2028)
    p = pf.resolver(pm.ProjecaoFinanceira(), _sugestoes(), anos=anos)
    assert p.roe == pytest.approx((0.24, 0.215, 0.19))
    assert p.payout == pytest.approx((0.6, (0.6 + 1 - 0.05 / 0.19) / 2, 1 - 0.05 / 0.19))
    manual = pm.ProjecaoFinanceira(roe=(0.2, 0.18, 0.16, 0.15), payout_inicio=0.5)
    m = pf.resolver(manual, _sugestoes(), anos=anos)
    assert m.roe == (0.2, 0.18, 0.16) and m.payout_inicio == 0.5
    with pytest.raises(ErroProjecao, match="lista tem 1 valores"):
        pf.resolver(pm.ProjecaoFinanceira(roe=(0.2,)), _sugestoes(), anos=anos)
    with pytest.raises(ErroProjecao, match="não supera o g"):
        pf.resolver(pm.ProjecaoFinanceira(roe=pm.Trajetoria(fim=0.04)), _sugestoes(), anos=anos)

    deltas = pf.resolver_cenarios(pm.CenariosFinanceira(), _sugestoes())
    sigma = _sugestoes().delta_roe.valor
    assert deltas == {"pessimista": -sigma, "base": 0.0, "otimista": sigma}
    fixo = pm.CenariosFinanceira(otimista=pm.DeltaCenarioFinanceira(roe_pp=0.01))
    assert pf.resolver_cenarios(fixo, _sugestoes())["otimista"] == 0.01
    pess = pf.aplicar_cenario(p, -0.02, "pessimista")
    assert pess.roe == pytest.approx((0.22, 0.195, 0.17))
    assert pess.payout[-1] == pytest.approx(1 - 0.05 / 0.17)
    assert pess.cenario == "pessimista"


def test_projetar_calculado_a_mao() -> None:
    p = pf.PremissasFinanceiras(
        anos=(2026, 2027), roe=(0.2, 0.2), payout_inicio=0.5, g_terminal=0.05
    )
    t = pf.projetar(100.0, p, data_base=dt.date(2026, 7, 1))
    fracao = (dt.date(2026, 12, 31) - dt.date(2026, 7, 1)).days / 365
    lucro_1 = 0.2 * 100 * fracao
    pl_1 = 100 + lucro_1 * 0.5
    assert list(t.columns) == list(pf.COLUNAS_PROJECAO)
    assert t.loc[2026, "lucro"] == pytest.approx(lucro_1)
    assert t.loc[2026, "pl_final"] == pytest.approx(pl_1)
    assert t.loc[2027, "payout"] == pytest.approx(0.75)  # 1 - 0,05 / 0,2
    assert t.loc[2027, "lucro"] == pytest.approx(0.2 * pl_1)
    assert t.loc[2027, "dividendos"] == pytest.approx(0.75 * 0.2 * pl_1)
    with pytest.raises(ErroProjecao, match="PL da controladora"):
        pf.projetar(-1.0, p, data_base=dt.date(2026, 7, 1))
    with pytest.raises(ErroProjecao, match="Horizonte"):
        pf.anos_projetados(dt.date(2026, 7, 1), 0)


def test_esquema_financeira() -> None:
    p = pm.PremissasEmpresa.model_validate(MINIMO)
    assert p == pm.premissas_padrao("BANC4", "financeira", ["BANC4"])
    assert p.projecao_ddm.roe == pm.Trajetoria()
    assert p.projecao_ddm.payout_inicio == pm.SUGERIDO
    assert p.cenarios_ddm.pessimista.roe_pp == pm.SUGERIDO
    with pytest.raises(Exception, match="FCFF não se aplicam"):
        _ = p.projecao_dcf
    nao_fin = pm.premissas_padrao("SINT3", "nao_financeira", ["SINT3"])
    with pytest.raises(Exception, match="DDM não se aplicam"):
        _ = nao_fin.cenarios_ddm


@pytest.mark.parametrize(
    "trecho, erro",
    [
        ({"projecao": {"receita": {}}}, "receita"),
        ({"cenarios": {"pessimista": {"margem_ebitda_pp": 0.01}}}, "margem_ebitda_pp"),
        ({"ajustes": {"ifrs16": "ignorar"}}, "ifrs16 não se aplicam"),
        ({"custo_capital": {"kd": {"metodo": "historico"}}}, "kd não se aplica"),
        ({"projecao": {"payout_inicio": 1.2}}, "payout_inicio"),
    ],
)
def test_esquema_financeira_invalido(trecho: dict[str, object], erro: str) -> None:
    with pytest.raises(ValueError, match=erro):
        pm.PremissasEmpresa.model_validate({**MINIMO, **trecho})


def test_nao_financeira_recusa_campos_do_ddm() -> None:
    with pytest.raises(ValueError, match="roe"):
        pm.PremissasEmpresa.model_validate(
            {**MINIMO, "tipo_modelo": "nao_financeira", "projecao": {"roe": {}}}
        )


def test_escrita_financeira_ida_e_volta(tmp_path: Path) -> None:
    p = pm.PremissasEmpresa.model_validate(
        {
            **MINIMO,
            "ajustes": {"consolidado": False},
            "projecao": {
                "horizonte_anos": 5,
                "roe": {"inicio": 0.2, "fim": "sugerido"},
                "payout_inicio": 0.4,
                "terminal": {"g_nominal": 0.045},
            },
            "cenarios": {"otimista": {"roe_pp": 0.01}},
            "pares": {"setor": "bancos"},
            "custo_capital": {"beta": {"metodo": "manual", "valor": 0.9}},
        }
    )
    texto = escrita.renderizar_financeira(p, _sugestoes(), data_base=dt.date(2026, 10, 30))
    caminho = tmp_path / "BANC4.yaml"
    caminho.write_text(texto, encoding="utf-8")
    assert pm.carregar_premissas(caminho) == p
    assert "inicio manual; sugerido seria 24,0% (mediana do ROE 2021-2025)" in texto
    assert "manual; sugerido seria 60,0%" in texto
    assert "a partir de 2026)" in texto
    assert "ifrs16" not in texto and "kd:" not in texto
    assert max(len(linha) for linha in texto.splitlines() if linha.startswith("#")) <= 100
    padrao = pm.premissas_padrao("BANC4", "financeira", ["BANC4"])
    texto = escrita.renderizar_financeira(padrao, _sugestoes(), data_base=dt.date(2026, 10, 30))
    assert pm.PremissasEmpresa.model_validate(yaml.safe_load(texto)) == padrao
