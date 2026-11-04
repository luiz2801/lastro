"""`servicos/resultados.py`: leitura da última rodada, com os gravadores reais de `saida/csv.py`."""

import datetime as dt
import json
from pathlib import Path

import pandas as pd
import pytest

from valuation.config import ConfigCsv, carregar_settings
from valuation.saida.csv import gravar_csv, gravar_matriz
from valuation.servicos import resultados as res

BR = ConfigCsv(separador=";", decimal=",", encoding="utf-8-sig")


def _matriz() -> pd.DataFrame:
    return pd.DataFrame(
        [[100.5, 110.5], [90.5, 95.5]],
        index=pd.Index([0.12, 0.13], name="wacc"),
        columns=pd.Index([0.04, 0.05], name="g"),
    )


def _rodada(raiz: Path, data: str = "2026-10-30", formato: str = "br", **resumo: object) -> Path:
    pasta = raiz / "PETR4" / data
    linha = {"ticker": "PETR4", "data_base": data, "valor_ponderado": 40.5, **resumo}
    gravar_csv(pd.DataFrame([linha]), pasta / "resumo.csv", BR, formato)  # type: ignore[arg-type]
    return pasta


def _completa(pasta: Path, formato: str = "br") -> None:
    for cenario in ("base", "otimista"):
        gravar_csv(
            pd.DataFrame({"ano": [2027], "fcff": [10.5]}),
            pasta / f"projecao_{cenario}.csv",
            BR,
            formato,  # type: ignore[arg-type]
        )
    wacc = pd.DataFrame({"componente": ["wacc"], "valor": [0.13], "detalhe": ["x"]})
    gravar_csv(wacc, pasta / "wacc.csv", BR, formato)  # type: ignore[arg-type]
    ponte = pd.DataFrame({"item": ["equity"], "base": [1000.5]})
    gravar_csv(ponte, pasta / "ponte_ev_equity.csv", BR, formato)  # type: ignore[arg-type]
    gravar_matriz(_matriz(), pasta / "sensibilidade_wacc_g.csv", BR, formato)  # type: ignore[arg-type]
    (pasta / "qa.json").write_text(json.dumps({"n_erros": 0}), encoding="utf-8")
    (pasta / "meta.json").write_text(json.dumps({"modelo": "dcf"}), encoding="utf-8")


def test_sem_rodada(tmp_path: Path) -> None:
    assert res.ultimo_resultado("PETR4", BR, dir_saida=tmp_path) is None


def test_pasta_so_com_wacc_nao_e_rodada(tmp_path: Path) -> None:
    pasta = tmp_path / "PETR4" / "2026-10-30"
    gravar_csv(pd.DataFrame({"componente": ["wacc"], "valor": [0.1]}), pasta / "wacc.csv", BR)
    assert res.ultimo_resultado("PETR4", BR, dir_saida=tmp_path) is None


@pytest.mark.parametrize("formato", ["br", "intl"])
def test_le_a_rodada_completa_nos_dois_formatos(tmp_path: Path, formato: str) -> None:
    _completa(_rodada(tmp_path, formato=formato), formato)
    r = res.ultimo_resultado("PETR4", BR, dir_saida=tmp_path)
    assert r is not None
    assert r.data_base == dt.date(2026, 10, 30)
    assert r.modelo == "dcf"
    assert r.resumo["valor_ponderado"] == 40.5
    assert sorted(r.projecoes) == ["base", "otimista"]
    assert r.projecoes["base"]["fcff"].iloc[0] == 10.5
    assert r.wacc is not None and r.wacc["valor"].iloc[0] == 0.13
    assert r.ponte is not None and r.ponte["base"].iloc[0] == 1000.5
    assert r.qa == {"n_erros": 0}
    assert r.meta == {"modelo": "dcf"}
    assert r.avisos == []
    assert r.avisos_rodada == []
    pd.testing.assert_frame_equal(r.sensibilidades["wacc_g"], _matriz())


def test_usa_a_pasta_mais_recente_com_resumo(tmp_path: Path) -> None:
    _rodada(tmp_path, "2026-10-01", valor_ponderado=1.0)
    _rodada(tmp_path, "2026-10-30", valor_ponderado=2.0)
    (tmp_path / "PETR4" / "2026-11-02").mkdir()  # sem resumo.csv
    r = res.ultimo_resultado("PETR4", BR, dir_saida=tmp_path)
    assert r is not None
    assert r.data_base == dt.date(2026, 10, 30)
    assert r.resumo["valor_ponderado"] == 2.0


def test_rodada_incompleta_avisa_e_nao_inventa_dado(tmp_path: Path) -> None:
    _rodada(tmp_path, avisos="primeiro | segundo")
    r = res.ultimo_resultado("PETR4", BR, dir_saida=tmp_path)
    assert r is not None
    assert r.wacc is None and r.ponte is None and r.qa is None and r.meta is None
    assert r.avisos_rodada == ["primeiro", "segundo"]
    texto = " ".join(r.avisos)
    for nome in ("wacc.csv", "ponte_ev_equity.csv", "qa.json", "meta.json", "Nenhuma projeção"):
        assert nome in texto


def test_ddm_nao_espera_ponte(tmp_path: Path) -> None:
    _rodada(tmp_path, modelo="ddm")
    r = res.ultimo_resultado("PETR4", BR, dir_saida=tmp_path)
    assert r is not None
    assert r.modelo == "ddm"
    assert "ponte_ev_equity.csv" not in " ".join(r.avisos)


def test_arquivo_corrompido_vira_aviso(tmp_path: Path) -> None:
    pasta = _rodada(tmp_path)
    _completa(pasta)
    (pasta / "qa.json").write_text("{ quebrado", encoding="utf-8")
    (pasta / "meta.json").write_text("[1, 2]", encoding="utf-8")
    (pasta / "wacc.csv").write_text("sem separador\n", encoding="utf-8")
    (pasta / "sensibilidade_wacc_g.csv").write_text("a;b\nx;y\n", encoding="utf-8")
    r = res.ultimo_resultado("PETR4", BR, dir_saida=tmp_path)
    assert r is not None
    assert r.qa is None and r.meta is None and r.wacc is None
    assert "wacc_g" not in r.sensibilidades
    texto = " ".join(r.avisos)
    for nome in ("qa.json", "meta.json", "wacc.csv", "sensibilidade_wacc_g.csv"):
        assert f"{nome} não pôde ser lido" in texto


def _resumo_com(tmp_path: Path, **colunas: object) -> res.Resultado:
    _rodada(tmp_path, **colunas)
    r = res.ultimo_resultado("PETR4", BR, dir_saida=tmp_path)
    assert r is not None
    return r


def test_checagens_dcf(tmp_path: Path) -> None:
    r = _resumo_com(tmp_path, g=0.05, wacc=0.13, vt_sobre_ev=0.8)
    c = {x.nome: x for x in res.checagens(r, carregar_settings())}
    assert c["g < WACC"].ok is True
    assert c["g < WACC"].valor == "5,00% < 13,00%"
    assert c["g dentro do teto"].ok is True  # teto de 5%
    assert c["VT / EV"].ok is False


def test_checagens_sem_dado_nao_viram_ok(tmp_path: Path) -> None:
    r = _resumo_com(tmp_path)
    assert all(c.ok is None for c in res.checagens(r, carregar_settings()))


def test_checagens_ddm(tmp_path: Path) -> None:
    r = _resumo_com(tmp_path, modelo="ddm", g=0.05, ke=0.2, divergencia_lucro_residual=0.5)
    c = {x.nome: x for x in res.checagens(r, carregar_settings())}
    assert c["g < Ke"].ok is True
    assert c["Lucro residual x DDM"].ok is False


def test_faixas_football_dos_csvs(tmp_path: Path) -> None:
    pasta = _rodada(tmp_path, valor_pessimista=10.0, valor_base=20.0, valor_otimista=30.0)
    gravar_matriz(_matriz(), pasta / "sensibilidade_wacc_g.csv", BR)
    implicitos = pd.DataFrame(
        {
            "multiplo": ["p_l", "ev_ebit"],
            "valor_p25": [15.0, float("nan")],
            "valor_mediana": [18.0, float("nan")],
            "valor_p75": [12.0, float("nan")],
            "confianca": ["baixa", "normal"],
        }
    )
    gravar_csv(implicitos, pasta / "multiplos_implicitos.csv", BR)
    r = res.ultimo_resultado("PETR4", BR, dir_saida=tmp_path)
    assert r is not None
    f = {x.rotulo: x for x in res.faixas_football(r, (5.0, 9.0))}
    assert (f["DCF (pess. a otim.)"].minimo, f["DCF (pess. a otim.)"].maximo) == (10.0, 30.0)
    assert f["DCF (pess. a otim.)"].ponto == 20.0
    assert (f["DCF (faixa WACC/g)"].minimo, f["DCF (faixa WACC/g)"].maximo) == (90.5, 110.5)
    assert (f["P/L"].minimo, f["P/L"].maximo, f["P/L"].aviso) == (12.0, 15.0, True)
    assert "EV/EBIT" not in f  # sem valor implícito não há barra
    assert f["Faixa de 52 semanas"].maximo == 9.0


def test_ponte_de_cenario(tmp_path: Path) -> None:
    pasta = _rodada(tmp_path)
    _completa(pasta)
    r = res.ultimo_resultado("PETR4", BR, dir_saida=tmp_path)
    assert r is not None
    itens = res.ponte_de_cenario(r, "base")
    assert itens is not None and itens["equity"] == 1000.5
    assert res.ponte_de_cenario(r, "otimista") is None
