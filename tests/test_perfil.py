import datetime as dt
import json
from pathlib import Path

import pytest

from valuation.config import carregar_settings
from valuation.perfil import ErroPerfil
from valuation.perfil import registro as reg
from valuation.perfil.parametros import parametros_do_perfil
from valuation.perfil.pontuacao import classificar, perfil_da_pontuacao
from valuation.perfil.questionario import (
    QUESTIONARIO,
    VETO_HORIZONTE_CURTO,
    VETO_NAO_ACEITA_PERDAS,
)

HOJE = dt.date(2026, 10, 30)


def respostas(padrao: int = 3, **trocas: int) -> dict[str, int]:
    """Mesma alternativa em todas as perguntas, com trocas pontuais (`q2=1`)."""
    return {p.chave: trocas.get(p.chave, padrao) for p in QUESTIONARIO}


# --- questionário ---------------------------------------------------------------------------


def test_questionario_tem_10_perguntas_de_1_a_5_pontos() -> None:
    assert len(QUESTIONARIO) == 10
    assert len({p.chave for p in QUESTIONARIO}) == 10
    for p in QUESTIONARIO:
        pontos = [a.pontos for a in p.alternativas]
        assert min(pontos) == 1 and max(pontos) == 5, p.chave


def test_vetos_estao_no_horizonte_e_na_perda_maxima() -> None:
    vetos = {(p.chave, a.veto) for p in QUESTIONARIO for a in p.alternativas if a.veto}
    assert vetos == {("q2", VETO_HORIZONTE_CURTO), ("q9", VETO_NAO_ACEITA_PERDAS)}


# --- pontuação ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pontuacao", "perfil"),
    [(10, "conservador"), (24, "conservador"), (25, "moderado"), (37, "moderado"),
     (38, "arrojado"), (50, "arrojado")],
)  # fmt: skip
def test_faixas_de_pontuacao(pontuacao: int, perfil: str) -> None:
    assert perfil_da_pontuacao(pontuacao) == perfil


def test_classificar_soma_os_pontos() -> None:
    c = classificar(respostas(3))
    assert (c.pontuacao, c.perfil, c.vetos_aplicados) == (30, "moderado", ())
    assert classificar(respostas(5)).perfil == "arrojado"
    assert classificar(respostas(1, q2=2, q9=2)).pontuacao == 12


def test_veto_de_horizonte_forca_conservador() -> None:
    c = classificar(respostas(5, q2=1))  # 46 pontos
    assert c.pontuacao == 46
    assert c.perfil == "conservador"
    assert c.vetos_aplicados == (VETO_HORIZONTE_CURTO,)


def test_veto_de_perdas_forca_conservador() -> None:
    c = classificar(respostas(5, q2=1, q9=1))
    assert c.perfil == "conservador"
    assert c.vetos_aplicados == (VETO_HORIZONTE_CURTO, VETO_NAO_ACEITA_PERDAS)


@pytest.mark.parametrize(
    "ruins",
    [
        {k: v for k, v in respostas().items() if k != "q5"},
        {**respostas(), "q11": 1},
        respostas(q3=0),
        respostas(q3=6),
    ],
)
def test_respostas_invalidas_falham(ruins: dict[str, int]) -> None:
    with pytest.raises(ErroPerfil):
        classificar(ruins)


# --- registro JSON --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "esperado"),
    [
        (dt.date(2026, 10, 30), dt.date(2027, 10, 30)),
        (dt.date(2028, 2, 29), dt.date(2029, 2, 28)),
        (dt.date(2026, 1, 31), dt.date(2027, 1, 31)),
    ],
)
def test_validade_de_12_meses(data: dt.date, esperado: dt.date) -> None:
    assert reg.criar_registro(respostas(), data).valido_ate == esperado


def test_somar_meses_atravessa_ano_e_limita_dia() -> None:
    assert reg.somar_meses(dt.date(2026, 11, 30), 3) == dt.date(2027, 2, 28)


def test_vencido_so_depois_do_ultimo_dia() -> None:
    r = reg.criar_registro(respostas(), HOJE)
    assert not r.vencido(dt.date(2027, 10, 30))
    assert r.vencido(dt.date(2027, 10, 31))


def test_gravar_e_ler_ida_e_volta(tmp_path: Path) -> None:
    r = reg.criar_registro(respostas(4, q2=1), HOJE)
    caminho = reg.gravar(r, tmp_path / "sub" / "perfil.json")
    bruto = json.loads(caminho.read_text(encoding="utf-8"))
    assert bruto == {
        "versao_questionario": 1,
        "data": "2026-10-30",
        "valido_ate": "2027-10-30",
        "respostas": respostas(4, q2=1),
        "pontuacao": 37,
        "vetos_aplicados": [VETO_HORIZONTE_CURTO],
        "perfil": "conservador",
    }
    assert reg.ler(caminho) == r


def _gravar_bruto(caminho: Path, **trocas: object) -> Path:
    bruto = reg.criar_registro(respostas(), HOJE).para_dict() | trocas
    caminho.write_text(json.dumps(bruto), encoding="utf-8")
    return caminho


@pytest.mark.parametrize(
    ("trocas", "mensagem"),
    [
        ({"perfil": "arrojado"}, "editado à mão"),
        ({"pontuacao": 31}, "editado à mão"),
        ({"valido_ate": "2030-01-01"}, "editado à mão"),
        ({"perfil": "agressivo"}, "perfil desconhecido"),
        ({"versao_questionario": 0}, "questionário v0"),
        ({"data": "ontem"}, "inválido"),
        ({"respostas": {"q1": 1}}, "Respostas incompletas"),
    ],
)
def test_ler_recusa_arquivo_inconsistente(
    tmp_path: Path, trocas: dict[str, object], mensagem: str
) -> None:
    caminho = _gravar_bruto(tmp_path / "perfil.json", **trocas)
    with pytest.raises(ErroPerfil, match=mensagem):
        reg.ler(caminho)


def test_ler_json_quebrado(tmp_path: Path) -> None:
    caminho = tmp_path / "perfil.json"
    caminho.write_text("{", encoding="utf-8")
    with pytest.raises(ErroPerfil, match="inválido"):
        reg.ler(caminho)


# --- resolver_perfil ------------------------------------------------------------------------


def test_resolver_usa_json_valido(tmp_path: Path) -> None:
    caminho = reg.gravar(reg.criar_registro(respostas(5), HOJE), tmp_path / "p.json")
    efetivo = reg.resolver_perfil(caminho, HOJE, None)
    assert (efetivo.perfil, efetivo.origem) == ("arrojado", "questionario")
    assert efetivo.registro is not None


def test_override_vence_mesmo_sem_arquivo(tmp_path: Path) -> None:
    efetivo = reg.resolver_perfil(tmp_path / "nao_existe.json", HOJE, "conservador")
    assert (efetivo.perfil, efetivo.origem, efetivo.registro) == ("conservador", "override", None)


def test_resolver_sem_arquivo_pede_questionario(tmp_path: Path) -> None:
    with pytest.raises(ErroPerfil, match="valuation perfil"):
        reg.resolver_perfil(tmp_path / "nao_existe.json", HOJE, None)


def test_resolver_perfil_vencido(tmp_path: Path) -> None:
    antigo = reg.criar_registro(respostas(), dt.date(2025, 10, 29))
    caminho = reg.gravar(antigo, tmp_path / "p.json")
    with pytest.raises(ErroPerfil, match="vencido em 2026-10-29"):
        reg.resolver_perfil(caminho, HOJE, None)


# --- parâmetros -----------------------------------------------------------------------------


def test_parametros_do_settings_do_repositorio() -> None:
    config = carregar_settings().perfil
    margens = [parametros_do_perfil(p, config).margem_seguranca for p in
               ("conservador", "moderado", "arrojado")]  # fmt: skip
    assert margens == sorted(margens, reverse=True)
    for nome in ("conservador", "moderado", "arrojado"):
        p = parametros_do_perfil(nome, config)
        assert p.perfil == nome
        assert p.peso_pessimista + p.peso_base + p.peso_otimista == pytest.approx(1)


def test_hurdle_e_selic_mais_spread() -> None:
    p = parametros_do_perfil("moderado", carregar_settings().perfil)
    assert p.hurdle(0.15) == pytest.approx(0.15 + p.hurdle_spread_selic)
