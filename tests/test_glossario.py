import json

import pytest
from typer.testing import CliRunner

from valuation.cli import app
from valuation.modelos import multiplos as mt
from valuation.saida import glossario as gl


def test_chaves_unicas_e_grupos_validos() -> None:
    chaves = [t.chave for t in gl.TERMOS]
    assert len(chaves) == len(set(chaves))
    assert {t.grupo for t in gl.TERMOS} <= set(gl.GRUPOS)


def test_todo_termo_tem_texto_completo() -> None:
    for t in gl.TERMOS:
        assert all((t.sigla, t.nome, t.definicao, t.formula, t.interpretacao)), t.chave


def test_legendas_usam_chaves_existentes() -> None:
    for legenda in (gl.LEGENDA_DCF, gl.LEGENDA_DDM, gl.LEGENDA_WACC, gl.LEGENDA_MULTIPLOS):
        gl.termos(legenda)


def test_todo_multiplo_do_motor_tem_termo() -> None:
    gl.termos(mt.MULTIPLOS)


@pytest.mark.parametrize(
    ("texto", "chave"),
    [
        ("WACC", "wacc"),
        ("p/vp", "p_vp"),
        ("EV EBITDA", "ev_ebitda"),
        ("Ke implícito", "ke_implicito"),
    ],
)
def test_buscar_ignora_caixa_acento_e_simbolos(texto: str, chave: str) -> None:
    assert [t.chave for t in gl.buscar(texto)] == [chave]


def test_buscar_parcial_e_inexistente() -> None:
    assert {"ev", "ev_ebitda"} <= {t.chave for t in gl.buscar("valor da firma")}
    assert gl.buscar("zzz") == []
    assert gl.buscar("  ") == []


def test_dicionario_serializavel() -> None:
    d = gl.dicionario(["wacc", "g"])
    assert list(d) == ["wacc", "g"]
    assert set(d["wacc"]) == {"sigla", "nome", "definicao", "formula", "interpretacao"}
    assert json.dumps(gl.dicionario())


def test_comando_glossario_termo() -> None:
    r = CliRunner().invoke(app, ["glossario", "wacc"])
    assert r.exit_code == 0
    assert "Custo médio ponderado de capital" in r.stdout
    assert "Como se calcula" in r.stdout


def test_comando_glossario_lista_tudo() -> None:
    r = CliRunner().invoke(app, ["glossario"])
    assert r.exit_code == 0
    for grupo in gl.GRUPOS:
        assert grupo in r.stdout


def test_comando_glossario_desconhecido_sai_com_1() -> None:
    r = CliRunner().invoke(app, ["glossario", "zzz"])
    assert r.exit_code == 1
    assert "não encontrado" in r.stdout
