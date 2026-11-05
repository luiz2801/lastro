"""`servicos/comparacao_valuation.py`: referências do valuation lidas de rodadas sintéticas."""

import datetime as dt
import math
from pathlib import Path

import pandas as pd

from valuation.config import ConfigCsv, Setor
from valuation.projecao import premissas as pm
from valuation.saida.csv import gravar_csv
from valuation.servicos import comparacao_valuation as scv
from valuation.universo import EmpresaUniverso, SetorCVM

BR = ConfigCsv(separador=";", decimal=",", encoding="utf-8-sig")
MAQ = SetorCVM.MAQUINAS_EQUIPAMENTOS_VEICULOS_E_PECAS


def _rodada(
    raiz: Path, ticker: str, *, perfil: str = "moderado", modelo: str = "dcf", **valores: float
) -> None:
    pasta = raiz / ticker / "2026-10-30"
    linha: dict[str, object] = {
        "ticker": ticker,
        "data_base": "2026-10-30",
        "modelo": modelo,
        "perfil": perfil,
        **{k: v for k, v in valores.items() if k != "beta" and k != "kd"},
    }
    gravar_csv(pd.DataFrame([linha]), pasta / "resumo.csv", BR)
    componentes = {k: v for k, v in valores.items() if k in ("beta", "kd")}
    if componentes:
        gravar_csv(
            pd.DataFrame(
                {
                    "componente": list(componentes),
                    "valor": list(componentes.values()),
                    "detalhe": "",
                }
            ),
            pasta / "wacc.csv",
            BR,
        )


def test_ler_rodada_junta_resumo_e_wacc(tmp_path: Path) -> None:
    _rodada(tmp_path, "AAAA3", ke=0.18, wacc=0.15, beta=0.9, kd=0.12, g=0.05, upside=0.1)
    r = scv.ler_rodada("AAAA3", BR, tmp_path)
    assert r is not None
    assert (r.data_base, r.perfil, r.modelo) == (dt.date(2026, 10, 30), "moderado", "dcf")
    assert r.valores == {
        "beta": 0.9,
        "ke": 0.18,
        "kd": 0.12,
        "wacc": 0.15,
        "g": 0.05,
        "upside": 0.1,
    }
    assert scv.ler_rodada("SEMRODADA3", BR, tmp_path) is None


def test_referencia_e_a_mediana_a_mao(tmp_path: Path) -> None:
    for t, ke in (("AAAA3", 0.16), ("BBBB3", 0.20), ("CCCC3", 0.30)):
        _rodada(tmp_path, t, ke=ke)
    rodadas = scv.ler_rodadas(["AAAA3", "BBBB3", "CCCC3", "DDDD3"], BR, tmp_path)
    ref = scv.referencia_valuation(rodadas, scv.POR_CHAVE["ke"], "moderado", "dcf", "mediana")
    assert ref.valor == 0.20 and ref.n == 3
    assert ref.sem_rodada == ("DDDD3",)
    media = scv.referencia_valuation(
        rodadas, scv.POR_CHAVE["ke"], "moderado", "dcf", "media_simples"
    )
    assert math.isclose(media.valor, (0.16 + 0.20 + 0.30) / 3)


def test_indicador_do_perfil_so_conta_rodada_do_mesmo_perfil(tmp_path: Path) -> None:
    _rodada(tmp_path, "AAAA3", perfil="moderado", upside=0.10, ke=0.16)
    _rodada(tmp_path, "BBBB3", perfil="arrojado", upside=0.50, ke=0.20)
    rodadas = scv.ler_rodadas(["AAAA3", "BBBB3"], BR, tmp_path)
    upside = scv.referencia_valuation(
        rodadas, scv.POR_CHAVE["upside"], "moderado", "dcf", "mediana"
    )
    assert (upside.valor, upside.n, upside.outro_perfil) == (0.10, 1, ("BBBB3",))
    ke = scv.referencia_valuation(rodadas, scv.POR_CHAVE["ke"], "moderado", "dcf", "mediana")
    assert ke.n == 2 and math.isclose(ke.valor, 0.18)  # Ke não depende do perfil


def test_dcf_e_ddm_nao_se_misturam(tmp_path: Path) -> None:
    _rodada(tmp_path, "AAAA3", modelo="dcf", ke=0.16, wacc=0.13)
    _rodada(tmp_path, "BANC4", modelo="ddm", ke=0.22)
    rodadas = scv.ler_rodadas(["AAAA3", "BANC4"], BR, tmp_path)
    assert (
        scv.referencia_valuation(rodadas, scv.POR_CHAVE["ke"], "", "dcf", "mediana").valor == 0.16
    )
    # WACC não existe no DDM: sem referência, em vez de um número de outro modelo.
    ddm = scv.referencia_valuation(rodadas, scv.POR_CHAVE["wacc"], "", "ddm", "mediana")
    assert math.isnan(ddm.valor) and ddm.n == 0


def test_grupos_de_comparacao() -> None:
    universo = [
        EmpresaUniverso("WEGE3", MAQ, "nao_financeira"),
        EmpresaUniverso("ROMI3", MAQ, "nao_financeira"),
        EmpresaUniverso("ITUB4", SetorCVM.BANCOS, "financeira"),
        EmpresaUniverso("PETR4", SetorCVM.PETROLEO_E_GAS, "nao_financeira"),
        EmpresaUniverso("ITSA4", SetorCVM.BANCOS, "holding"),
    ]
    premissas = pm.premissas_padrao("WEGE3", "nao_financeira", ("WEGE3",))
    setor = Setor(
        descricao="x", tipo_modelo="nao_financeira", commodity=False, pares=("WEGE3", "TUPY3")
    )
    g = scv.grupos_de_comparacao("WEGE3", ("WEGE3",), premissas, setor, universo)
    assert g[scv.GRUPO_PARES] == ["TUPY3"]
    assert g[scv.GRUPO_SETOR] == ["ROMI3"]  # mesmo setor CVM e mesmo tipo
    assert g[scv.GRUPO_MERCADO] == ["ROMI3", "PETR4"]  # sem financeiras, holdings e o próprio
    fora = scv.grupos_de_comparacao("XXXX3", ("XXXX3",), premissas, None, universo)
    assert fora[scv.GRUPO_SETOR] == [] and fora[scv.GRUPO_MERCADO] == []
