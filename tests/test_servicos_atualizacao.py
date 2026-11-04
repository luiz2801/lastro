"""`servicos/atualizacao.py` e `servicos/cache.py`: sem rede, com subprocessos triviais."""

import datetime as dt
import json
import os
import sys
from pathlib import Path

from valuation.servicos import atualizacao as atu
from valuation.servicos import cache as sc


def _py(codigo: str) -> atu.Comando:
    return (sys.executable, "-c", codigo)


def test_comandos_chamam_a_cli_pelo_mesmo_interpretador() -> None:
    assert atu.baixar_dados("PETR4") == [
        (sys.executable, "-m", "valuation", "atualizar", "--tickers", "PETR4")
    ]
    assert atu.atualizar_ativo("PETR4")[1][3:] == ("rodar", "PETR4")
    assert atu.atualizar_favoritas()[0][3:] == ("favoritos", "atualizar")


def test_executar_entrega_cada_linha_e_junta_stderr() -> None:
    vistas: list[str] = []
    codigo = "import sys; print('a'); print('b', file=sys.stderr)"
    r = atu.executar([_py(codigo)], vistas.append)
    assert r.ok and r.falhou_em is None
    assert sorted(vistas) == ["a", "b"] == sorted(r.saida)


def test_executar_para_no_primeiro_que_falha() -> None:
    r = atu.executar(
        [_py("print('um'); raise SystemExit(3)"), _py("print('dois')")],
    )
    assert not r.ok
    assert r.saida == ["um"]
    assert r.falhou_em is not None


def test_executar_comando_inexistente_nao_levanta(tmp_path: Path) -> None:
    r = atu.executar([(str(tmp_path / "nao_existe"), "-c", "x", "y")])
    assert not r.ok
    assert "Não foi possível iniciar" in r.saida[0]


def test_estado_fontes_sem_nada_em_disco(tmp_path: Path) -> None:
    fontes = sc.estado_fontes(
        "PETR4", None, dir_raw=tmp_path, dir_processed=tmp_path, dir_saida=tmp_path
    )
    assert [f.nome for f in fontes] == ["CVM", "Preços", "Macro", "Valuation"]
    assert all(f.atualizado_em is None for f in fontes)
    assert fontes[0].idade_dias(dt.datetime.now(dt.UTC)) is None


def test_estado_fontes_com_cache(tmp_path: Path) -> None:
    agora = dt.datetime(2026, 11, 4, 12, tzinfo=dt.UTC)
    baixado = (agora - dt.timedelta(days=3)).isoformat()
    precos = tmp_path / "precos"
    precos.mkdir()
    meta = {"simbolo": "PETR4.SA", "baixado_em": baixado}
    (precos / "yf_PETR4.SA_20261015_20261030.meta.json").write_text(json.dumps(meta))
    (precos / "yf_VALE3.SA_20261015_20261030.meta.json").write_text(
        json.dumps({"baixado_em": agora.isoformat()})
    )
    (precos / "yf_PETR4.SA_antigo.meta.json").write_text("{ quebrado")
    pasta = tmp_path / "cvm" / "9512"
    pasta.mkdir(parents=True)
    dem = pasta / "demonstracoes.parquet"
    dem.write_bytes(b"")
    instante = (agora - dt.timedelta(days=10)).timestamp()
    os.utime(dem, (instante, instante))
    fontes = {
        f.nome: f
        for f in sc.estado_fontes(
            "PETR4", 9512, dir_raw=tmp_path, dir_processed=tmp_path, dir_saida=tmp_path
        )
    }
    assert fontes["Preços"].idade_dias(agora) == 3
    assert fontes["CVM"].idade_dias(agora) == 10
    assert fontes["Macro"].atualizado_em is None
