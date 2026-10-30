import datetime as dt
from pathlib import Path

import pytest
import yaml

from sintetico import historico_anual
from valuation.config import DIR_EMPRESAS, ErroConfiguracao, carregar_setores
from valuation.contabil.nao_financeiras import AjustesContabeis, NaoRecorrente
from valuation.projecao import escrita
from valuation.projecao import premissas as pm
from valuation.projecao import sugestor as sg

MINIMO = {"ticker": "SINT3", "tipo_modelo": "nao_financeira", "classes_acao": ["SINT3"]}


def test_padroes_sao_sugeridos() -> None:
    p = pm.PremissasEmpresa.model_validate(MINIMO)
    assert p == pm.premissas_padrao("sint3", "nao_financeira", ["SINT3"])
    assert p.projecao.horizonte_anos == "perfil"
    assert p.projecao.receita.crescimento == pm.Trajetoria()
    assert p.projecao.capex_sobre_receita == pm.SUGERIDO
    assert p.cenarios.pessimista.crescimento_pp == pm.SUGERIDO
    assert p.ajustes.ifrs16 == "divida"
    assert p.pares.setor is None


def test_valores_manuais_e_listas() -> None:
    p = pm.PremissasEmpresa.model_validate(
        {
            **MINIMO,
            "projecao": {
                "horizonte_anos": 7,
                "receita": {"crescimento": [0.06, 0.05]},
                "margens": {"ebitda": {"inicio": 0.3}},
                "nwc_sobre_receita": -0.05,
            },
        }
    )
    assert p.projecao.receita.crescimento == (0.06, 0.05)
    assert p.projecao.margens.ebitda == pm.Trajetoria(inicio=0.3)
    assert p.projecao.nwc_sobre_receita == -0.05


@pytest.mark.parametrize(
    "trecho",
    [
        {"campo_novo": 1},
        {"projecao": {"capex_sobre_receita": "sugerdo"}},
        {"projecao": {"capex_sobre_receita": -0.1}},
        {"projecao": {"horizonte_anos": 0}},
        {"projecao": {"aliquota_imposto": {"valor": 0.4, "limite_superior": 0.34}}},
        {"cenarios": {"pessimista": {"crescimento_pp": 0.9}}},
        {"custo_capital": {"beta": {"metodo": "manual"}}},
        {"tipo_modelo": "holding"},
        {"classes_acao": []},
    ],
)
def test_yaml_invalido(trecho: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        pm.PremissasEmpresa.model_validate({**MINIMO, **trecho})


def test_carregar_confere_ticker(tmp_path: Path) -> None:
    caminho = pm.caminho_premissas("sint3", tmp_path)
    assert caminho.name == "SINT3.yaml"
    caminho.write_text(yaml.safe_dump(MINIMO), encoding="utf-8")
    assert pm.carregar_premissas(caminho).ticker == "SINT3"
    outro = tmp_path / "OUTR3.yaml"
    outro.write_text(yaml.safe_dump(MINIMO), encoding="utf-8")
    with pytest.raises(ErroConfiguracao, match="difere do nome"):
        pm.carregar_premissas(outro)
    invalido = tmp_path / "RUIM3.yaml"
    invalido.write_text("ticker: [", encoding="utf-8")
    with pytest.raises(ErroConfiguracao, match="não é YAML válido"):
        pm.carregar_premissas(invalido)


def test_conferir_cadastro() -> None:
    p = pm.premissas_padrao("PETR4", "nao_financeira", ["PETR3", "PETR4"])
    pm.conferir_cadastro(p, ("PETR4", "PETR3"), "nao_financeira")
    with pytest.raises(ErroConfiguracao, match="classes_acao"):
        pm.conferir_cadastro(p, ("PETR4",), "nao_financeira")
    with pytest.raises(ErroConfiguracao, match="tipo_modelo"):
        pm.conferir_cadastro(p, ("PETR3", "PETR4"), "financeira")


def test_ajustes_contabeis() -> None:
    ajustes = pm.Ajustes.model_validate(
        {
            "ifrs16": "ignorar",
            "coligadas": "manter_no_ebit",
            "caixa_extra": ["aplicacoes_financeiras_lp"],
            "nao_recorrentes": [{"ano": 2020, "valor": -5e8, "descricao": "impairment"}],
        }
    )
    assert pm.ajustes_contabeis(ajustes) == AjustesContabeis(
        ifrs16="ignorar",
        capex_equivalente_arrendamento=True,
        coligadas="manter_no_ebit",
        nao_recorrentes=(NaoRecorrente(2020, -5e8, "impairment"),),
        caixa_extra=("aplicacoes_financeiras_lp",),
    )


def test_yamls_do_repositorio_carregam() -> None:
    setores = carregar_setores()
    assert setores["petroleo_gas"].commodity and not setores["maquinas_equipamentos"].commodity
    for ticker in ("PETR4", "VALE3", "WEGE3"):
        p = pm.carregar_premissas(pm.caminho_premissas(ticker, DIR_EMPRESAS))
        assert p.pares.setor in setores


def _sugestoes() -> sg.Sugestoes:
    h = historico_anual([0.10] * 9, [0.20] * 10)
    return sg.sugerir(
        h, g_terminal=sg.Sugestao(0.04, "teste"), aliquota_limite=0.34, commodity=True
    )


def test_escrita_ida_e_volta(tmp_path: Path) -> None:
    p = pm.PremissasEmpresa.model_validate(
        {
            "ticker": "PETR4",
            "tipo_modelo": "nao_financeira",
            "classes_acao": ["PETR3", "PETR4"],
            "ajustes": {
                "nao_recorrentes": [{"ano": 2020, "valor": -1.5e9, "descricao": "baixa: ativo"}],
                "mapeamento_extra": {"titulos": [{"dem": "BPA", "cd": "1.02.01.01"}]},
                "caixa_extra": ["titulos"],
            },
            "projecao": {
                "horizonte_anos": 5,
                "receita": {"crescimento": [0.06, 0.05]},
                "margens": {"ebitda": {"inicio": 0.4, "fim": "sugerido"}},
                "capex_sobre_receita": 0.12,
                "aliquota_imposto": {"valor": "sugerido", "limite_superior": 0.3},
                "terminal": {"g_nominal": 0.04, "ronic": "roic_historico"},
            },
            "cenarios": {"otimista": {"margem_ebitda_pp": 0.01}},
            "pares": {"setor": "petroleo_gas", "excluir": ["PRIO3"]},
            "custo_capital": {"beta": {"metodo": "manual", "valor": 1.1}},
        }
    )
    texto = escrita.renderizar(p, _sugestoes(), data_base=dt.date(2026, 10, 30))
    caminho = tmp_path / "PETR4.yaml"
    caminho.write_text(texto, encoding="utf-8")
    assert pm.carregar_premissas(caminho) == p
    assert "manual; sugerido seria 6,0% (mediana 2021-2025)" in texto  # capex
    assert "fim sugerido: 20,0% (média entre" in texto
    assert "manual (lista por ano); sugerido seria de 10,0% a 4,0%" in texto
    assert "# Aviso: Setor de commodity" in texto
    assert max(len(linha) for linha in texto.splitlines() if linha.startswith("#")) <= 100


def test_escrita_padrao_mantem_sugerido(tmp_path: Path) -> None:
    p = pm.premissas_padrao("SINT3", "nao_financeira", ["SINT3"])
    texto = escrita.renderizar(p, _sugestoes(), data_base=dt.date(2026, 10, 30))
    assert "  capex_sobre_receita: sugerido" in texto
    assert "# sugerido: 6,0% (mediana 2021-2025)" in texto
    assert pm.PremissasEmpresa.model_validate(yaml.safe_load(texto)) == p
