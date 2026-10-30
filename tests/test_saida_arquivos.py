import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from valuation.saida import arquivos as arq


@dataclass(frozen=True)
class _Exemplo:
    dia: dt.date
    taxas: tuple[float, ...]
    ruim: float


def test_serializavel_converte_tipos() -> None:
    dados = {
        "d": _Exemplo(dt.date(2026, 10, 30), (0.1, 0.2), float("nan")),
        "n": np.float64(1.5),
        "i": np.int64(3),
        "data": dt.datetime(2026, 10, 30, 12, tzinfo=dt.UTC),
        1: "chave numérica",
    }
    s = arq.serializavel(dados)
    assert s["d"] == {"dia": "2026-10-30", "taxas": [0.1, 0.2], "ruim": None}
    assert s["n"] == 1.5 and isinstance(s["n"], float)
    assert s["i"] == 3 and isinstance(s["i"], int)
    assert s["data"].startswith("2026-10-30T12:00")
    assert s["1"] == "chave numérica"
    json.dumps(s)


def test_gravar_json_e_yaml_ida_e_volta(tmp_path: Path) -> None:
    dados = {"a": dt.date(2026, 10, 30), "b": (1, 2), "c": "ação"}
    j = arq.gravar_json(dados, tmp_path / "x" / "m.json")
    assert json.loads(j.read_text("utf-8")) == {"a": "2026-10-30", "b": [1, 2], "c": "ação"}
    y = arq.gravar_yaml(dados, tmp_path / "p.yaml", "# cabeçalho\n")
    assert y.read_text("utf-8").startswith("# cabeçalho\n")
    assert yaml.safe_load(y.read_text("utf-8")) == {"a": "2026-10-30", "b": [1, 2], "c": "ação"}


def test_sha256_arquivo(tmp_path: Path) -> None:
    f = tmp_path / "a.bin"
    f.write_bytes(b"abc")
    assert arq.sha256_arquivo(f) == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
    assert arq.sha256_arquivo(tmp_path / "nao_existe") is None


def test_fontes_cvm_le_os_meta_json(tmp_path: Path) -> None:
    pasta = tmp_path / "DFP"
    pasta.mkdir()
    (pasta / "dfp_2025.zip.meta.json").write_text(
        json.dumps(
            {
                "url": "https://x/dfp.zip",
                "baixado_em": "2026-10-30",
                "sha256": "ab",
                "tamanho_bytes": 10,
                "outro": 1,
            }
        ),
        "utf-8",
    )
    (pasta / "estranho.meta.json").write_text(json.dumps({"simbolo": "PETR4.SA"}), "utf-8")
    assert arq.fontes_cvm(tmp_path) == [
        {
            "url": "https://x/dfp.zip",
            "baixado_em": "2026-10-30",
            "sha256": "ab",
            "tamanho_bytes": 10,
        }
    ]


def test_commit_git_fora_de_repositorio(tmp_path: Path) -> None:
    assert arq.commit_git(tmp_path) is None


def test_tabela_historico_junta_anual_e_ltm() -> None:
    anual = pd.DataFrame(
        {"receita_liquida": [100.0, 120.0]}, index=pd.Index([2024, 2025], name="ano")
    )
    ltm = pd.Series({"receita_liquida": 130.0}, name=pd.Timestamp("2026-06-30"))
    t = arq.tabela_historico(anual, ltm)
    assert list(t["periodo"]) == ["2024", "2025", "LTM 06/2026"]
    assert list(t["tipo"]) == ["anual", "anual", "ltm"]
    assert list(t["receita_liquida"]) == [100.0, 120.0, 130.0]


def test_faixa_52_semanas() -> None:
    datas = pd.date_range("2025-01-03", "2026-10-30", freq="W-FRI")
    hist = pd.DataFrame({"close": np.arange(len(datas), dtype=float) + 10}, index=datas)
    base = dt.date(2026, 10, 30)
    lo, hi = arq.faixa_52_semanas(hist, base) or (0.0, 0.0)
    na_janela = hist[hist.index > pd.Timestamp(base) - pd.Timedelta(weeks=52)]["close"]
    assert (lo, hi) == (na_janela.min(), na_janela.max())
    assert hi == hist["close"].iloc[-1]
    assert arq.faixa_52_semanas(hist.iloc[0:0], base) is None
    assert arq.faixa_52_semanas(hist, dt.date(2020, 1, 1)) is None


def test_faixas_football_sem_multiplos() -> None:
    matriz = pd.DataFrame([[10.0, 12.0], [14.0, np.nan]])
    f = arq.faixas_football(
        {"pessimista": 8.0, "base": 11.0, "otimista": 15.0},
        matriz,
        None,
        (9.0, 20.0),
        modelo="dcf",
        rotulo_matriz="faixa WACC/g",
    )
    assert [x.rotulo for x in f] == [
        "DCF (pess. a otim.)",
        "DCF (faixa WACC/g)",
        "Faixa de 52 semanas",
    ]
    assert (f[0].minimo, f[0].maximo, f[0].ponto) == (8.0, 15.0, 11.0)
    assert (f[1].minimo, f[1].maximo) == (10.0, 14.0)  # NaN ignorado
    assert (f[2].minimo, f[2].maximo) == (9.0, 20.0)


def test_faixas_football_um_cenario_nao_tem_barra_de_cenarios() -> None:
    f = arq.faixas_football(
        {"base": 11.0}, pd.DataFrame([[1.0]]), None, None, modelo="ddm", rotulo_matriz="faixa Ke/g"
    )
    assert [x.rotulo for x in f] == ["DDM (faixa Ke/g)"]


def test_montar_meta_tem_o_essencial() -> None:
    m = arq.montar_meta(
        versao="0.1.0",
        agora=dt.datetime(2026, 10, 30, tzinfo=dt.UTC),
        comando="valuation rodar X",
        commit="abc",
        ticker="X",
        data_base=dt.date(2026, 10, 30),
        modelo="dcf",
        perfil="moderado",
        origem_perfil="override",
        moeda_reporte="BRL",
        cambio=1.0,
        cenarios=["base"],
        referencia="base",
        taxa_desconto={"base": 0.15},
        fontes={"cvm": []},
        hash_contas="h",
        arquivos=["meta.json"],
        avisos=["a"],
    )
    assert m["codigo"]["commit"] == "abc"
    assert m["perfil"] == {"nome": "moderado", "origem": "override"}
    assert m["hash_contas_padronizadas"] == "h"
    json.dumps(arq.serializavel(m))
