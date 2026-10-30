import datetime as dt
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml
from typer.testing import CliRunner

from conftest import DIR_FIXTURES_CVM, SessaoFalsa
from sintetico import dfp_banco, dfp_completa, juntar
from valuation import __version__, cli
from valuation.cli import app
from valuation.config import Settings, carregar_settings
from valuation.data import cadastro as cad
from valuation.data import macro as mac
from valuation.data import precos as prc
from valuation.data.cvm import url_cadastro, url_documento, url_fca
from valuation.data.validacao import manual
from valuation.perfil import registro as reg
from valuation.perfil.questionario import QUESTIONARIO
from valuation.projecao import premissas as pm


def test_versao() -> None:
    resultado = CliRunner().invoke(app, ["versao"])
    assert resultado.exit_code == 0
    assert __version__ in resultado.stdout


@pytest.fixture
def ambiente_offline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sessao_falsa: SessaoFalsa,
    zip_cvm: Callable[[str], Path],
) -> Path:
    """CLI apontando para diretórios temporários e um servidor CVM em memória."""
    settings = carregar_settings().model_copy(
        update={"data_base": dt.date(2026, 10, 30), "historico_anos": 1}
    )

    def carregar() -> Settings:
        return settings

    monkeypatch.setattr(cli, "carregar_settings", carregar)
    monkeypatch.setattr(cli, "criar_sessao", lambda: sessao_falsa)
    monkeypatch.setattr(cli, "DIR_RAW", tmp_path / "raw")
    monkeypatch.setattr(cli, "DIR_PROCESSED", tmp_path / "processed")
    monkeypatch.setattr(cli, "CAMINHO_CADASTRO_MANUAL", tmp_path / "manual.csv")
    monkeypatch.setattr(cli, "CAMINHO_UNIVERSO", tmp_path / "universo.csv")
    monkeypatch.setattr(cli, "DIR_EMPRESAS", tmp_path / "empresas")

    rotas = sessao_falsa.rotas
    rotas[url_cadastro()] = (200, (DIR_FIXTURES_CVM / "cad_cia_aberta.csv").read_bytes(), {})
    for ano in (2025, 2026):
        rotas[url_fca(ano)] = (200, zip_cvm(f"fca_cia_aberta_{ano}").read_bytes(), {})
    rotas[url_documento("DFP", 2025)] = (200, zip_cvm("dfp_cia_aberta_2025").read_bytes(), {})
    rotas[url_documento("ITR", 2026)] = (200, zip_cvm("itr_cia_aberta_2026").read_bytes(), {})
    # ITR 2025 publicado, mas sem as companhias da fixture.
    rotas[url_documento("ITR", 2025)] = (200, zip_cvm("fca_cia_aberta_2025").read_bytes(), {})
    return tmp_path


def test_cadastro_buscar(ambiente_offline: Path) -> None:
    resultado = CliRunner().invoke(app, ["cadastro", "buscar", "petrobras"])
    assert resultado.exit_code == 0, resultado.output
    assert "PETR4" in resultado.output
    assert "9512" in resultado.output


def test_cadastro_buscar_sem_resultado(ambiente_offline: Path) -> None:
    resultado = CliRunner().invoke(app, ["cadastro", "buscar", "zzzzzz"])
    assert resultado.exit_code == 1
    assert "Nada encontrado" in resultado.output


def test_atualizar(ambiente_offline: Path) -> None:
    resultado = CliRunner().invoke(app, ["atualizar", "--tickers", "PETR4,PETR3,WEGE3"])
    assert resultado.exit_code == 0, resultado.output
    assert "DFP: 2025 a 2025 (ainda não publicado: 2026)" in resultado.output
    processado = ambiente_offline / "processed" / "cvm"
    assert sorted(p.name for p in processado.iterdir()) == ["5410", "9512"]
    weg = pd.read_parquet(processado / "5410" / "demonstracoes.parquet")
    assert not weg.empty


def test_atualizar_ticker_inexistente(ambiente_offline: Path) -> None:
    resultado = CliRunner().invoke(app, ["atualizar", "--tickers", "XPTO3"])
    assert resultado.exit_code == 1
    assert "XPTO3 não encontrado" in resultado.output


def test_atualizar_tudo_sem_universo(ambiente_offline: Path) -> None:
    resultado = CliRunner().invoke(app, ["atualizar", "--tudo"])
    assert resultado.exit_code == 1
    assert "não existe" in " ".join(resultado.output.split())


def test_atualizar_tudo_com_universo(ambiente_offline: Path) -> None:
    (ambiente_offline / "universo.csv").write_text("ticker;setor\nWEGE3;industria\n")
    resultado = CliRunner().invoke(app, ["atualizar", "--tudo"])
    assert resultado.exit_code == 0, resultado.output
    assert (ambiente_offline / "processed" / "cvm" / "5410").is_dir()


def test_atualizar_exige_uma_opcao() -> None:
    resultado = CliRunner().invoke(app, ["atualizar"])
    assert resultado.exit_code == 1
    assert "--tickers ou --tudo" in resultado.output


@pytest.fixture
def weg_sintetica(ambiente_offline: Path) -> Path:
    """WEGE3 baixada pela fixture e com as demonstrações trocadas por uma DFP sintética completa."""
    assert CliRunner().invoke(app, ["atualizar", "--tickers", "WEGE3"]).exit_code == 0
    pasta = ambiente_offline / "processed" / "cvm" / "5410"
    dados = juntar(dfp_completa(2024, cd_cvm=5410), dfp_completa(2025, cd_cvm=5410))
    dados.to_parquet(pasta / "demonstracoes.parquet", index=False)
    return ambiente_offline


def test_qa(weg_sintetica: Path) -> None:
    resultado = CliRunner().invoke(app, ["qa", "WEGE3"])
    assert resultado.exit_code == 0, resultado.output
    assert "Nenhum problema encontrado" in resultado.output
    assert "100%" in resultado.output
    assert (weg_sintetica / "processed" / "qa" / "qa_WEGE3.json").is_file()
    assert (weg_sintetica / "processed" / "cvm" / "5410" / "contas_padronizadas.parquet").is_file()


def test_qa_com_erro_sai_com_1(weg_sintetica: Path) -> None:
    pasta = weg_sintetica / "processed" / "cvm" / "5410"
    dados = juntar(dfp_completa(2024, cd_cvm=5410), dfp_completa(2025, cd_cvm=5410, BPA={"1": 999}))
    dados.to_parquet(pasta / "demonstracoes.parquet", index=False)
    resultado = CliRunner().invoke(app, ["qa", "WEGE3"])
    assert resultado.exit_code == 1
    assert "balanco_fecha" in resultado.output


def test_qa_sem_dados(ambiente_offline: Path) -> None:
    resultado = CliRunner().invoke(app, ["qa", "WEGE3"])
    assert resultado.exit_code == 1
    assert "valuation atualizar --tickers WEGE3" in " ".join(resultado.output.split())


def test_historico(weg_sintetica: Path) -> None:
    resultado = CliRunner().invoke(app, ["historico", "WEGE3", "--anos", "2"])
    assert resultado.exit_code == 0, resultado.output
    assert "LTM 12/2025" in resultado.output
    assert "Receita líquida" in resultado.output
    trimestral = CliRunner().invoke(app, ["historico", "WEGE3", "--trimestral"])
    assert trimestral.exit_code == 0, trimestral.output
    assert "4T25" in trimestral.output


def test_cobertura(weg_sintetica: Path) -> None:
    resultado = CliRunner().invoke(app, ["cobertura", "--tickers", "WEGE3"])
    assert resultado.exit_code == 0, resultado.output
    assert "Média geral: 100.0%" in resultado.output
    assert CliRunner().invoke(app, ["cobertura"]).exit_code == 1


@pytest.fixture
def banco_sintetico(ambiente_offline: Path) -> Path:
    """WEGE3 reclassificada como financeira (cadastro manual) e com DFPs de banco sintéticas:
    PL da controladora 90 em 2024 e 100 em 2025, lucro da controladora 22 em 2025."""
    (ambiente_offline / "manual.csv").write_text(
        "ticker;cnpj;especie;tipo_modelo;escala_acoes;observacao\nWEGE3;;;financeira;;teste\n",
        encoding="utf-8",
    )
    assert CliRunner().invoke(app, ["atualizar", "--tickers", "WEGE3"]).exit_code == 0
    pasta = ambiente_offline / "processed" / "cvm" / "5410"
    dados = juntar(
        dfp_banco(
            2024,
            cd_cvm=5410,
            BPP={
                "2.03": ("Passivos Financeiros ao Custo Amortizado", 890),
                "2.08": ("Patrimônio Líquido Consolidado", 110),
            },
        ),
        dfp_banco(2025, cd_cvm=5410),
    )
    dados.to_parquet(pasta / "demonstracoes.parquet", index=False)
    return ambiente_offline


def test_qa_e_historico_de_financeira(banco_sintetico: Path) -> None:
    resultado = CliRunner().invoke(app, ["qa", "WEGE3"])
    assert resultado.exit_code == 0, resultado.output
    assert "Nenhum problema encontrado" in resultado.output
    assert "Cobertura das 7 contas críticas: 100%" in resultado.output
    historico = CliRunner().invoke(app, ["historico", "WEGE3"])
    assert historico.exit_code == 0, historico.output
    texto = " ".join(historico.output.split())
    assert "ROE" in texto and "24,4%" in texto  # 22 / 90
    assert "Payout" in texto and "50,0%" in texto
    cobertura = CliRunner().invoke(app, ["cobertura", "--tickers", "WEGE3"])
    assert cobertura.exit_code == 0, cobertura.output


def test_premissas_sugerir_financeira(banco_sintetico: Path, caminho_perfil: Path) -> None:
    resultado = CliRunner().invoke(
        app,
        ["premissas", "sugerir", "WEGE3", "--data-base", "2026-10-30", "--perfil", "moderado"],
    )
    assert resultado.exit_code == 0, resultado.output
    texto = " ".join(resultado.output.split())
    assert "(DDM, até 2025)" in texto
    assert "24,4%" in texto  # ROE 22 / 90, único exercício com PL inicial
    assert "PL da controladora em 2025-12-31" in texto
    assert "2032" in texto and "2033" not in texto  # 7 anos a partir de 2026
    escrito = CliRunner().invoke(
        app, ["premissas", "sugerir", "WEGE3", "--data-base", "2026-10-30", "--escrever"]
    )
    assert escrito.exit_code == 0, escrito.output
    yaml_banco = banco_sintetico / "empresas" / "WEGE3.yaml"
    assert pm.carregar_premissas(yaml_banco) == pm.premissas_padrao(
        "WEGE3", "financeira", ["WEGE3"]
    )
    gravado = yaml_banco.read_text(encoding="utf-8")
    assert "fim sugerido: 24,4% (mediana do ROE 2025-2025)" in gravado
    assert "sugerido: 50,0% (mediana do payout 2024-2025)" in gravado


def test_padronizar_usa_individual_quando_nao_ha_consolidado(banco_sintetico: Path) -> None:
    pasta = banco_sintetico / "processed" / "cvm" / "5410"
    dados = pd.read_parquet(pasta / "demonstracoes.parquet").assign(consolidado=False)
    dados.to_parquet(pasta / "demonstracoes.parquet", index=False)
    resultado = CliRunner().invoke(app, ["qa", "WEGE3"])
    assert resultado.exit_code == 0, resultado.output
    assert "só publica demonstrações individuais" in " ".join(resultado.output.split())


def test_holding_e_recusada(ambiente_offline: Path) -> None:
    (ambiente_offline / "manual.csv").write_text(
        "ticker;cnpj;especie;tipo_modelo;escala_acoes;observacao\nWEGE3;;;holding;;teste\n",
        encoding="utf-8",
    )
    assert CliRunner().invoke(app, ["atualizar", "--tickers", "WEGE3"]).exit_code == 0
    resultado = CliRunner().invoke(app, ["qa", "WEGE3"])
    assert resultado.exit_code == 1
    assert "NAV/SOTP" in " ".join(resultado.output.split())


@pytest.fixture
def caminho_perfil(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    caminho = tmp_path / "perfil" / "perfil_investidor.json"
    monkeypatch.setattr(cli, "CAMINHO_PERFIL", caminho)
    return caminho


def test_perfil_questionario_grava_json(caminho_perfil: Path) -> None:
    # "9" é inválido e deve ser perguntado de novo; depois, alternativa 3 em tudo (30 pontos).
    entrada = "9\n" + "3\n" * 10
    resultado = CliRunner().invoke(app, ["perfil"], input=entrada)
    assert resultado.exit_code == 0, resultado.output
    assert "Digite um número de 1 a 5" in resultado.output
    assert "Perfil: moderado (pontuação 30 de 50" in resultado.output
    assert "Selic + 5,0 p.p." in resultado.output
    registro = reg.ler(caminho_perfil)
    assert registro.perfil == "moderado"
    assert registro.data == dt.date.today()


def test_perfil_valido_nao_repergunta(caminho_perfil: Path) -> None:
    respostas = {p.chave: 5 for p in QUESTIONARIO}
    reg.gravar(reg.criar_registro(respostas, dt.date.today()), caminho_perfil)
    resultado = CliRunner().invoke(app, ["perfil"])
    assert resultado.exit_code == 0, resultado.output
    assert "Já existe um perfil válido" in resultado.output
    assert "arrojado" in resultado.output
    mostrar = CliRunner().invoke(app, ["perfil", "--mostrar"])
    assert mostrar.exit_code == 0
    assert "Margem de segurança" in mostrar.output


def test_perfil_refazer_e_vencido(caminho_perfil: Path) -> None:
    respostas = {p.chave: 5 for p in QUESTIONARIO}
    antigo = dt.date.today() - dt.timedelta(days=800)
    reg.gravar(reg.criar_registro(respostas, antigo), caminho_perfil)
    assert "vencido em" in CliRunner().invoke(app, ["perfil", "--mostrar"]).output
    resultado = CliRunner().invoke(app, ["perfil"], input="1\n" * 10)
    assert resultado.exit_code == 0, resultado.output
    assert "venceu em" in resultado.output
    assert reg.ler(caminho_perfil).perfil == "conservador"
    refeito = CliRunner().invoke(app, ["perfil", "--refazer"], input="5\n" * 10)
    assert refeito.exit_code == 0, refeito.output
    assert reg.ler(caminho_perfil).perfil == "arrojado"


def test_perfil_erros(caminho_perfil: Path) -> None:
    assert CliRunner().invoke(app, ["perfil", "--mostrar"]).exit_code == 1
    assert CliRunner().invoke(app, ["perfil", "--mostrar", "--refazer"]).exit_code == 1
    caminho_perfil.parent.mkdir(parents=True)
    caminho_perfil.write_text("{", encoding="utf-8")
    quebrado = CliRunner().invoke(app, ["perfil"])
    assert quebrado.exit_code == 1
    assert "--refazer" in quebrado.output
    refeito = CliRunner().invoke(app, ["perfil", "--refazer"], input="3\n" * 10)
    assert refeito.exit_code == 0, refeito.output


def _sugerir(*args: str) -> tuple[int, str]:
    resultado = CliRunner().invoke(
        app, ["premissas", "sugerir", "WEGE3", "--data-base", "2026-10-30", *args]
    )
    return resultado.exit_code, " ".join(resultado.output.split())


def test_premissas_sugerir_e_escrever(weg_sintetica: Path, caminho_perfil: Path) -> None:
    yaml_weg = weg_sintetica / "empresas" / "WEGE3.yaml"
    codigo, saida = _sugerir("--perfil", "moderado")
    assert codigo == 0, saida
    assert "Premissas sugeridas x histórico" in saida
    assert "7 anos pelo perfil moderado (override)" in saida
    assert "use --escrever para criá-lo" in saida
    assert not yaml_weg.exists()

    codigo, saida = _sugerir("--perfil", "moderado", "--escrever")
    assert codigo == 0, saida
    p = pm.carregar_premissas(yaml_weg)
    assert p == pm.premissas_padrao("WEGE3", "nao_financeira", ["WEGE3"])

    # Valor manual e setor sobrevivem à regeneração; o arquivo anterior vira .bak.
    texto = yaml_weg.read_text(encoding="utf-8")
    texto = texto.replace("capex_sobre_receita: sugerido", "capex_sobre_receita: 0.2")
    texto = texto.replace("horizonte_anos: perfil", "horizonte_anos: 3")
    yaml_weg.write_text(texto.replace("setor: null", "setor: maquinas_equipamentos"), "utf-8")
    codigo, saida = _sugerir("--escrever")
    assert codigo == 0, saida
    assert "3 anos pelo YAML da empresa" in saida
    assert "2028" in saida and "2029" not in saida
    novo = yaml_weg.read_text(encoding="utf-8")
    assert "capex_sobre_receita: 0.2" in novo
    assert "manual; sugerido seria 12,0%" in novo  # capex 12 / receita 100 da DFP sintética
    assert pm.carregar_premissas(yaml_weg).pares.setor == "maquinas_equipamentos"
    assert yaml_weg.with_suffix(".yaml.bak").read_text(encoding="utf-8") == texto.replace(
        "setor: null", "setor: maquinas_equipamentos"
    )


def test_premissas_sugerir_sem_perfil_mostra_so_sugestoes(
    weg_sintetica: Path, caminho_perfil: Path
) -> None:
    codigo, saida = _sugerir()
    assert codigo == 0, saida
    assert "Premissas sugeridas" in saida
    assert "Projeção não mostrada" in saida
    assert "valuation perfil" in saida


def test_premissas_sugerir_erros(weg_sintetica: Path, caminho_perfil: Path) -> None:
    assert _sugerir("--perfil", "ousado")[0] == 1
    resultado = CliRunner().invoke(app, ["premissas", "sugerir", "WEGE3", "--data-base", "30/10"])
    assert resultado.exit_code == 1
    assert "--data-base inválida" in resultado.output
    yaml_weg = weg_sintetica / "empresas" / "WEGE3.yaml"
    yaml_weg.parent.mkdir()
    base = {"ticker": "WEGE3", "tipo_modelo": "nao_financeira"}
    yaml_weg.write_text(yaml.safe_dump({**base, "classes_acao": ["WEGE4"]}), "utf-8")
    codigo, saida = _sugerir()
    assert codigo == 1
    assert "classes_acao de WEGE3 (WEGE4) diferem do cadastro" in saida
    setor = {**base, "classes_acao": ["WEGE3"], "pares": {"setor": "inexistente"}}
    yaml_weg.write_text(yaml.safe_dump(setor), "utf-8")
    codigo, saida = _sugerir()
    assert codigo == 1
    assert "pares.setor 'inexistente'" in saida


class _PrecosFalsos:
    """Provedor com preços semanais sintéticos: ação com beta 1,2 exato contra o índice."""

    nome = "falso"

    def __init__(self) -> None:
        datas = pd.date_range(end="2026-10-30", periods=301, freq="W-FRI")
        rm = np.random.default_rng(3).normal(0.002, 0.03, 300)
        self._indice = 100 * np.cumprod(np.r_[1.0, 1 + rm])
        self._acao = 100 * np.cumprod(np.r_[1.0, 1 + 1.2 * rm])
        self._datas = datas

    def historico(self, simbolo: str, inicio: dt.date, fim: dt.date) -> pd.DataFrame:
        valores = self._indice if simbolo == "^BVSP" else self._acao
        return pd.DataFrame(
            {"close": valores, "adj_close": valores, "volume": 1e6}, index=self._datas
        )


@pytest.fixture
def mercado_falso(weg_sintetica: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """WEGE3 sintética com dívida 100, despesa financeira 12 e market cap 900 (90 ações a R$ 10;
    D/(D+E) = 10%)."""
    pasta = weg_sintetica / "processed" / "cvm" / "5410"
    dados = juntar(
        dfp_completa(2024, cd_cvm=5410, DRE={"3.06.02": -12}),
        dfp_completa(2025, cd_cvm=5410, DRE={"3.06.02": -12}),
    )
    dados.to_parquet(pasta / "demonstracoes.parquet", index=False)

    def mercado(
        ticker: str, settings: Settings, base: dt.date, agora: dt.datetime, forcar: bool
    ) -> cli._Mercado:
        empresa = cad.empresa_por_ticker(cli._carregar_cadastro(settings, base, False), ticker)
        macro = mac.Macro(
            base,
            selic=manual("Selic", 0.15),
            ipca_12m=manual("IPCA", 0.05),
            cambio=manual("Dólar", 5.0),
            rf_brl=manual("Rf", 0.13),
            ipca_esperado={2027: 0.04, 2030: 0.035},
            data_focus=base,
        )
        cap = prc.MarketCap(900.0, (prc.ClasseMarketCap("WEGE3", "ON", 90, 10.0),), base, ())
        precos = {"WEGE3": manual("Preço WEGE3", 10.0)}
        return cli._Mercado(empresa, precos, manual("^BVSP", 1.0), macro, cap, _PrecosFalsos())  # type: ignore[arg-type]

    monkeypatch.setattr(cli, "_mercado", mercado)
    return weg_sintetica


def test_wacc(mercado_falso: Path) -> None:
    saida = mercado_falso / "saida"
    resultado = CliRunner().invoke(app, ["wacc", "WEGE3", "--saida", str(saida)])
    assert resultado.exit_code == 0, resultado.output
    tab = pd.read_csv(
        saida / "WEGE3" / "2026-10-30" / "wacc.csv", sep=";", decimal=",", encoding="utf-8-sig"
    ).set_index("componente")
    valor = tab["valor"]
    assert valor["beta_bruto"] == pytest.approx(1.2)
    assert valor["beta"] == pytest.approx(0.67 * 1.2 + 0.33)
    assert valor["ke"] == pytest.approx(0.13 + valor["beta"] * 0.05)
    # Kd = 12 / 100 = 12%, abaixo do piso (Rf 13%): limitado a 13%.
    assert valor["kd_bruto"] == pytest.approx(0.12)
    assert valor["kd"] == pytest.approx(0.13)
    assert valor["peso_divida"] == pytest.approx(0.1)
    assert valor["wacc"] == pytest.approx(valor["ke"] * 0.9 + 0.13 * 0.66 * 0.1)
    assert "Kd histórico com só 1 exercício" in " ".join(resultado.output.split())


def test_wacc_menor_que_g_falha(mercado_falso: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = cli.carregar_settings()
    cfg = settings.custo_capital.model_copy(update={"erp": -0.2})
    monkeypatch.setattr(
        cli, "carregar_settings", lambda: settings.model_copy(update={"custo_capital": cfg})
    )
    resultado = CliRunner().invoke(app, ["wacc", "WEGE3", "--saida", str(mercado_falso)])
    assert resultado.exit_code == 1
    assert "não converge" in " ".join(resultado.output.split())


def test_wacc_beta_manual_e_formato_invalido(mercado_falso: Path) -> None:
    assert CliRunner().invoke(app, ["wacc", "WEGE3", "--formato-csv", "xx"]).exit_code == 1
    yaml_weg = mercado_falso / "empresas" / "WEGE3.yaml"
    yaml_weg.parent.mkdir()
    yaml_weg.write_text(
        yaml.safe_dump(
            {
                "ticker": "WEGE3",
                "tipo_modelo": "nao_financeira",
                "classes_acao": ["WEGE3"],
                "custo_capital": {"beta": {"metodo": "manual", "valor": 0.8}},
            }
        ),
        "utf-8",
    )
    resultado = CliRunner().invoke(
        app, ["wacc", "WEGE3", "--saida", str(mercado_falso), "--formato-csv", "intl"]
    )
    assert resultado.exit_code == 0, resultado.output
    texto = (mercado_falso / "WEGE3" / "2026-10-30" / "wacc.csv").read_text("utf-8")
    assert "beta,0.8," in texto


def ler_csv_br(caminho: Path) -> pd.DataFrame:
    return pd.read_csv(caminho, sep=";", decimal=",", encoding="utf-8-sig")


def test_rodar(mercado_falso: Path, caminho_perfil: Path) -> None:
    saida = mercado_falso / "saida"
    resultado = CliRunner().invoke(
        app, ["rodar", "WEGE3", "--perfil", "moderado", "--saida", str(saida)]
    )
    assert resultado.exit_code == 0, resultado.output
    pasta = saida / "WEGE3" / "2026-10-30"
    assert sorted(p.name for p in pasta.iterdir()) == [
        "ponte_ev_equity.csv",
        "projecao_base.csv",
        "projecao_otimista.csv",
        "projecao_pessimista.csv",
        "resumo.csv",
        "sensibilidade_margem_crescimento.csv",
        "sensibilidade_wacc_g.csv",
        "wacc.csv",
    ]
    r = ler_csv_br(pasta / "resumo.csv").iloc[0]
    assert r["perfil"] == "moderado"
    assert r["origem_perfil"] == "override"
    assert r["preco"] == 10.0
    assert r["valor_ponderado"] == pytest.approx(
        0.25 * r["valor_pessimista"] + 0.5 * r["valor_base"] + 0.25 * r["valor_otimista"]
    )
    assert r["preco_maximo_compra"] == pytest.approx(0.8 * r["valor_ponderado"])
    assert r["hurdle"] == pytest.approx(0.15 + 0.05)
    assert r["g"] == pytest.approx(0.05)
    assert r["ronic"] == pytest.approx(r["wacc"])
    wacc_csv = ler_csv_br(pasta / "wacc.csv").set_index("componente")["valor"]
    assert r["wacc"] == pytest.approx(wacc_csv["wacc"])

    ponte = ler_csv_br(pasta / "ponte_ev_equity.csv").set_index("item")
    assert list(ponte.columns) == ["pessimista", "base", "otimista"]
    assert ponte.loc["acoes", "base"] == 90
    assert ponte.loc["valor_por_acao", "base"] == pytest.approx(r["valor_base"])
    assert ponte.loc["equity", "base"] == pytest.approx(90 * r["valor_base"])

    sens = ler_csv_br(pasta / "sensibilidade_wacc_g.csv").set_index("wacc\\g")
    assert sens.shape == (9, 9)
    assert sens.loc[sens.index[4], "0,0500"] == pytest.approx(r["valor_base"])
    projecao = ler_csv_br(pasta / "projecao_base.csv")
    assert projecao["ano"].iloc[0] == 2026
    assert projecao["vp"].notna().all()
    texto = " ".join(resultado.output.split())
    assert "preço máximo de compra para o perfil moderado" in texto
    assert "não é recomendação" in texto


def test_rodar_um_cenario(mercado_falso: Path, caminho_perfil: Path) -> None:
    saida = mercado_falso / "saida"
    resultado = CliRunner().invoke(
        app,
        ["rodar", "WEGE3", "--perfil", "arrojado", "--cenario", "otimista", "--saida", str(saida)],
    )
    assert resultado.exit_code == 0, resultado.output
    r = ler_csv_br(saida / "WEGE3" / "2026-10-30" / "resumo.csv").iloc[0]
    assert r["cenarios"] == "otimista"
    assert pd.isna(r["valor_base"])
    assert r["valor_ponderado"] == pytest.approx(r["valor_otimista"])
    assert not (saida / "WEGE3" / "2026-10-30" / "projecao_base.csv").exists()


def test_rodar_erros(mercado_falso: Path, caminho_perfil: Path) -> None:
    for args in (["--cenario", "xx"], ["--formato-csv", "xx"], ["--perfil", "xx"]):
        assert CliRunner().invoke(app, ["rodar", "WEGE3", *args]).exit_code == 1
    resultado = CliRunner().invoke(app, ["rodar", "WEGE3", "--saida", str(mercado_falso)])
    assert resultado.exit_code == 1
    assert "valuation perfil" in " ".join(resultado.output.split())


def escrever_yaml_weg(pasta: Path, **extra: object) -> None:
    caminho = pasta / "empresas" / "WEGE3.yaml"
    caminho.parent.mkdir(exist_ok=True)
    base = {"ticker": "WEGE3", "tipo_modelo": "nao_financeira", "classes_acao": ["WEGE3"]}
    caminho.write_text(yaml.safe_dump({**base, **extra}), "utf-8")


@pytest.fixture
def com_par(mercado_falso: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """PETR4 como único par, com as mesmas demonstrações da WEGE3 sintética e market cap de
    1.800: todo múltiplo implica equity de 1.800 para a WEGE3, ou R$ 20 por ação (90 ações)."""
    assert CliRunner().invoke(app, ["atualizar", "--tickers", "PETR4"]).exit_code == 0
    origem = mercado_falso / "processed" / "cvm" / "5410" / "demonstracoes.parquet"
    destino = mercado_falso / "processed" / "cvm" / "9512" / "demonstracoes.parquet"
    destino.write_bytes(origem.read_bytes())
    escrever_yaml_weg(mercado_falso, pares={"incluir": ["PETR4", "ZZZZ3"]})

    def mercado_par(ticker: str, *args: object) -> prc.MarketCap:
        if ticker != "PETR4":
            raise cad.ErroCadastro(f"{ticker} não está no cadastro")
        classe = prc.ClasseMarketCap("PETR4", "PN", 90, 20.0)
        return prc.MarketCap(1800.0, (classe,), dt.date(2026, 10, 30), ())

    monkeypatch.setattr(cli, "_mercado_par", mercado_par)
    return mercado_falso


def test_comparar(com_par: Path) -> None:
    saida = com_par / "saida"
    resultado = CliRunner().invoke(app, ["comparar", "WEGE3", "--saida", str(saida)])
    assert resultado.exit_code == 0, resultado.output
    pasta = saida / "WEGE3" / "2026-10-30"
    pares = ler_csv_br(pasta / "multiplos_pares.csv").set_index("ticker")
    assert list(pares["papel"]) == ["alvo", "par"]
    assert pares.loc["PETR4", "market_cap"] == 1800
    assert pares.loc["PETR4", "p_l"] == pytest.approx(2 * pares.loc["WEGE3", "p_l"])
    impl = ler_csv_br(pasta / "multiplos_implicitos.csv").set_index("multiplo")
    validos = impl["valor_mediana"].dropna()
    assert len(validos) >= 5
    assert validos.tolist() == pytest.approx([20.0] * len(validos))
    assert (impl["confianca"] == "baixa").all()
    texto = " ".join(resultado.output.split())
    assert "Par ZZZZ3 ignorado" in texto
    assert "baixa confiança" in texto


def test_comparar_sem_pares(mercado_falso: Path) -> None:
    resultado = CliRunner().invoke(app, ["comparar", "WEGE3", "--saida", str(mercado_falso)])
    assert resultado.exit_code == 1
    assert "sem pares" in " ".join(resultado.output.split())


def test_rodar_com_pares(com_par: Path, caminho_perfil: Path) -> None:
    saida = com_par / "saida"
    resultado = CliRunner().invoke(
        app, ["rodar", "WEGE3", "--perfil", "moderado", "--saida", str(saida)]
    )
    assert resultado.exit_code == 0, resultado.output
    pasta = saida / "WEGE3" / "2026-10-30"
    assert (pasta / "multiplos_pares.csv").exists()
    assert (pasta / "multiplos_implicitos.csv").exists()
    r = ler_csv_br(pasta / "resumo.csv").iloc[0]
    assert r["n_pares"] == 1
    assert r["valor_p_l"] == pytest.approx(20.0)
    assert r["valor_ev_ebitda"] == pytest.approx(20.0)
    assert r["ev_ebitda_pares"] > 0
    assert "Múltiplo de saída" in " ".join(resultado.output.split())


def test_wacc_beta_e_estrutura_dos_pares(com_par: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    escrever_yaml_weg(
        com_par, pares={"incluir": ["PETR4"]}, custo_capital={"beta": {"metodo": "comparaveis"}}
    )
    settings = cli.carregar_settings()
    cfg = settings.custo_capital.model_copy(
        update={
            "estrutura_alvo": settings.custo_capital.estrutura_alvo.model_copy(
                update={"metodo": "setor"}
            )
        }
    )
    monkeypatch.setattr(
        cli, "carregar_settings", lambda: settings.model_copy(update={"custo_capital": cfg})
    )
    resultado = CliRunner().invoke(app, ["wacc", "WEGE3", "--saida", str(com_par)])
    assert resultado.exit_code == 0, resultado.output
    tab = ler_csv_br(com_par / "WEGE3" / "2026-10-30" / "wacc.csv").set_index("componente")
    assert tab.loc["beta_metodo", "detalhe"] == "comparaveis"
    assert tab.loc["estrutura_metodo", "detalhe"] == "setor"
    # D/(D+E) do par = 100 / (100 + 1.800); o alvo é realavancado na mesma estrutura do par,
    # então o beta é o do par: 0,67 x 1,2 + 0,33.
    assert tab.loc["peso_divida", "valor"] == pytest.approx(100 / 1900)
    assert tab.loc["beta", "valor"] == pytest.approx(0.67 * 1.2 + 0.33)
    assert "com só 1 par" in " ".join(resultado.output.split())


def test_atualizar_com_pares(ambiente_offline: Path) -> None:
    escrever_yaml_weg(ambiente_offline, pares={"incluir": ["PETR4", "ZZZZ3"]})
    resultado = CliRunner().invoke(app, ["atualizar", "--tickers", "WEGE3", "--com-pares"])
    assert resultado.exit_code == 0, resultado.output
    assert (ambiente_offline / "processed" / "cvm" / "9512" / "demonstracoes.parquet").exists()
    assert "par ZZZZ3 ignorado" in " ".join(resultado.output.split())
