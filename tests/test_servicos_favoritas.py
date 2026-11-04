"""`servicos/favoritas.py`: mesma regra da CLI, sem repetir e sem aceitar fora do universo."""

from pathlib import Path

import pytest

from valuation.config import ErroConfiguracao
from valuation.saida import favoritos as fav
from valuation.servicos import favoritas as sfav


def test_adicionar_no_fim_sem_repetir_e_criando_o_arquivo(tmp_path: Path) -> None:
    caminho = tmp_path / "favoritos.yaml"
    assert sfav.adicionar("WEGE3", {"WEGE3", "PETR4"}, caminho) == ["WEGE3"]
    assert sfav.adicionar("PETR4", {"WEGE3", "PETR4"}, caminho) == ["WEGE3", "PETR4"]
    assert sfav.adicionar("WEGE3", {"WEGE3", "PETR4"}, caminho) == ["WEGE3", "PETR4"]
    assert fav.carregar_favoritos(caminho) == ["WEGE3", "PETR4"]


def test_fora_do_universo_nao_grava(tmp_path: Path) -> None:
    caminho = tmp_path / "favoritos.yaml"
    with pytest.raises(ErroConfiguracao, match="fora do universo"):
        sfav.adicionar("ZZZZ3", {"WEGE3"}, caminho)
    assert not caminho.exists()


def test_remover_quem_nao_esta_nao_quebra(tmp_path: Path) -> None:
    caminho = tmp_path / "favoritos.yaml"
    sfav.adicionar("WEGE3", {"WEGE3"}, caminho)
    assert sfav.remover("PETR4", caminho) == ["WEGE3"]
    assert sfav.remover("WEGE3", caminho) == []
