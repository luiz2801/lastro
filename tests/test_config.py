import datetime as dt
from pathlib import Path

import pytest
import yaml

from valuation.config import ErroConfiguracao, carregar_settings


def test_settings_do_repositorio_carrega() -> None:
    s = carregar_settings()
    assert s.versao == 1
    assert s.custo_capital.metodo in {"brl_direto", "usd_crp"}
    assert s.csv.separador == ";"


def test_data_base_hoje_usa_parametro() -> None:
    s = carregar_settings()
    if s.data_base == "hoje":
        assert s.resolver_data_base(dt.date(2026, 10, 30)) == dt.date(2026, 10, 30)


def test_campo_desconhecido_falha(tmp_path: Path) -> None:
    original = carregar_settings().model_dump(mode="json")
    original["campo_inexistente"] = 1
    caminho = tmp_path / "settings.yaml"
    caminho.write_text(yaml.safe_dump(original), encoding="utf-8")
    with pytest.raises(ErroConfiguracao, match="campo_inexistente"):
        carregar_settings(caminho)


def test_pesos_dos_cenarios_devem_somar_um(tmp_path: Path) -> None:
    original = carregar_settings().model_dump(mode="json")
    original["perfil"]["moderado"]["pesos_cenarios"]["base"] = 0.6
    caminho = tmp_path / "settings.yaml"
    caminho.write_text(yaml.safe_dump(original), encoding="utf-8")
    with pytest.raises(ErroConfiguracao, match="somar 1"):
        carregar_settings(caminho)


def test_arquivo_ausente_falha(tmp_path: Path) -> None:
    with pytest.raises(ErroConfiguracao, match="não encontrado"):
        carregar_settings(tmp_path / "nao_existe.yaml")


@pytest.mark.parametrize(
    ("caminho_campo", "valor", "mensagem"),
    [
        (("estrutura_alvo",), {"metodo": "manual"}, "divida_sobre_capital"),
        (("kd",), {"spread_min": 0.05, "spread_max": 0.01}, "spread_min"),
    ],
)
def test_custo_capital_invalido(
    tmp_path: Path, caminho_campo: tuple[str, ...], valor: object, mensagem: str
) -> None:
    original = carregar_settings().model_dump(mode="json")
    original["custo_capital"][caminho_campo[0]] = valor
    caminho = tmp_path / "settings.yaml"
    caminho.write_text(yaml.safe_dump(original), encoding="utf-8")
    with pytest.raises(ErroConfiguracao, match=mensagem):
        carregar_settings(caminho)


def test_erp_numero_solto_vira_manual(tmp_path: Path) -> None:
    original = carregar_settings().model_dump(mode="json")
    original["custo_capital"]["erp"] = 0.06
    caminho = tmp_path / "settings.yaml"
    caminho.write_text(yaml.safe_dump(original), encoding="utf-8")
    erp = carregar_settings(caminho).custo_capital.erp
    assert (erp.fonte, erp.valor) == ("manual", 0.06)


def test_erp_do_repositorio_tem_cinco_anos_e_faixa_de_1pp() -> None:
    erp = carregar_settings().custo_capital.erp
    assert (erp.anos_explicitos, erp.faixa_g, erp.valor) == (5, 0.01, 0.05)


def test_erp_campo_desconhecido_falha(tmp_path: Path) -> None:
    original = carregar_settings().model_dump(mode="json")
    original["custo_capital"]["erp"]["extra"] = 1
    caminho = tmp_path / "settings.yaml"
    caminho.write_text(yaml.safe_dump(original), encoding="utf-8")
    with pytest.raises(ErroConfiguracao, match="extra"):
        carregar_settings(caminho)
