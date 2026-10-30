"""Interface de linha de comando (`valuation`)."""

from __future__ import annotations

import datetime as dt
import logging
import platform
from pathlib import Path

import pandas as pd
import typer
from rich.console import Console
from rich.table import Table

from valuation import __version__
from valuation.config import (
    CAMINHO_CADASTRO_MANUAL,
    CAMINHO_UNIVERSO,
    DIR_PROCESSED,
    DIR_RAW,
    ErroConfiguracao,
    Settings,
    carregar_settings,
)
from valuation.data import cadastro as cad
from valuation.data import cvm
from valuation.data.http import ErroDownload, criar_sessao

app = typer.Typer(
    help="Valuation de ações da B3. Uso pessoal e educacional; não é recomendação de investimento.",
    no_args_is_help=True,
    add_completion=False,
)
cadastro_app = typer.Typer(help="Consulta ao cadastro de companhias abertas.", no_args_is_help=True)
app.add_typer(cadastro_app, name="cadastro")
console = Console()


@app.callback()
def principal(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log em nível DEBUG."),
) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@app.command()
def versao() -> None:
    """Mostra a versão do programa e do Python."""
    console.print(f"valuation {__version__} (Python {platform.python_version()})")


def _erro(mensagem: str) -> typer.Exit:
    console.print(f"[bold red]Erro:[/] {mensagem}")
    return typer.Exit(code=1)


def _carregar_cadastro(settings: Settings, data_base: dt.date, forcar: bool) -> pd.DataFrame:
    return cad.atualizar_cadastro(
        ano=data_base.year,
        data_ref=data_base,
        dir_raw=DIR_RAW,
        dir_processed=DIR_PROCESSED,
        caminho_manual=CAMINHO_CADASTRO_MANUAL,
        ttl=dt.timedelta(hours=settings.cache_ttl_horas.cvm),
        sessao=criar_sessao(),
        agora=dt.datetime.now(dt.UTC),
        forcar=forcar,
    )


def _tickers_do_universo(caminho: Path) -> list[str]:
    if not caminho.is_file():
        raise ErroConfiguracao(
            f"{caminho} não existe. Crie-o (coluna `ticker`, separador `;`) ou use --tickers."
        )
    universo = pd.read_csv(caminho, sep=";", dtype=str, comment="#")
    if "ticker" not in universo.columns:
        raise ErroConfiguracao(f"{caminho} precisa de uma coluna `ticker`")
    return list(universo["ticker"].dropna())


@cadastro_app.command("buscar")
def cadastro_buscar(
    texto: str = typer.Argument(..., help="Parte do ticker, razão social, nome ou CNPJ."),
    forcar: bool = typer.Option(False, "--forcar", help="Ignora o cache e baixa de novo."),
) -> None:
    """Procura companhias no cadastro (CVM + FCA + cadastro manual)."""
    try:
        settings = carregar_settings()
        data_base = settings.resolver_data_base(dt.date.today())
        resultado = cad.buscar(_carregar_cadastro(settings, data_base, forcar), texto)
    except (ErroConfiguracao, ErroDownload, cad.ErroCadastro) as e:
        raise _erro(str(e)) from e

    if resultado.empty:
        console.print(f"Nada encontrado para “{texto}”.")
        raise typer.Exit(code=1)
    tabela = Table(title=f"Cadastro — “{texto}”")
    for coluna in ("Ticker", "Espécie", "Companhia", "CNPJ", "CD_CVM", "Setor CVM", "Modelo"):
        tabela.add_column(coluna)
    for r in resultado.itertuples(index=False):
        tabela.add_row(
            str(r.ticker),
            str(r.especie),
            str(r.nome_comercial or r.razao_social),
            str(r.cnpj),
            str(r.cd_cvm),
            str(r.setor_cvm),
            str(r.tipo_modelo),
        )
    console.print(tabela)


@app.command()
def atualizar(
    tickers: str | None = typer.Option(
        None, "--tickers", help="Lista separada por vírgula, ex.: PETR4,VALE3."
    ),
    tudo: bool = typer.Option(False, "--tudo", help="Todos os tickers do universo configurado."),
    forcar: bool = typer.Option(False, "--forcar", help="Ignora o cache e baixa de novo."),
) -> None:
    """Baixa cadastro, DFP e ITR da CVM e grava os dados por companhia."""
    if bool(tickers) == tudo:
        raise _erro("Informe --tickers ou --tudo (um dos dois).")
    try:
        settings = carregar_settings()
        data_base = settings.resolver_data_base(dt.date.today())
        lista = (
            [t for t in tickers.split(",") if t.strip()]
            if tickers
            else _tickers_do_universo(CAMINHO_UNIVERSO)
        )
        cadastro = _carregar_cadastro(settings, data_base, forcar)
        empresas = {e.cnpj: e for e in (cad.empresa_por_ticker(cadastro, t) for t in lista)}
        for empresa in empresas.values():
            if empresa.tipo_modelo in ("holding", "nao_suportada"):
                console.print(
                    f"[yellow]Aviso:[/] {', '.join(empresa.tickers)} é {empresa.tipo_modelo}; "
                    "os dados serão baixados, mas a v1 não avalia esse tipo."
                )
        anos = cvm.anos_a_coletar(data_base.year, settings.historico_anos)
        resumo = cvm.coletar(
            [cvm.AlvoCVM(x.cnpj, x.cd_cvm, x.escala_acoes) for x in empresas.values()],
            anos,
            dir_raw=DIR_RAW,
            dir_processed=DIR_PROCESSED,
            ttl=dt.timedelta(hours=settings.cache_ttl_horas.cvm),
            sessao=criar_sessao(),
            agora=dt.datetime.now(dt.UTC),
            forcar=forcar,
        )
    except (ErroConfiguracao, ErroDownload, cad.ErroCadastro, cvm.ErroDadosCVM) as e:
        raise _erro(str(e)) from e

    for tipo in cvm.TIPOS_DOCUMENTO:
        obtidos = resumo.anos_baixados.get(tipo, [])
        faltam = resumo.anos_indisponiveis.get(tipo, [])
        texto = f"{min(obtidos)} a {max(obtidos)}" if obtidos else "nenhum"
        if faltam:
            texto += f" (ainda não publicado: {', '.join(map(str, faltam))})"
        console.print(f"{tipo}: {texto}")

    tabela = Table(title="Dados CVM por companhia")
    for coluna in ("Tickers", "Companhia", "CD_CVM", "Linhas", "Datas de referência", "Última"):
        tabela.add_column(coluna)
    for empresa in empresas.values():
        periodos = resumo.periodos_por_cd_cvm.get(empresa.cd_cvm, [])
        tabela.add_row(
            ", ".join(empresa.tickers),
            empresa.nome_comercial or empresa.razao_social,
            str(empresa.cd_cvm),
            f"{resumo.linhas_por_cd_cvm.get(empresa.cd_cvm, 0):,}".replace(",", "."),
            str(len(periodos)),
            periodos[-1].isoformat() if periodos else "—",
        )
    console.print(tabela)
    console.print(f"Gravado em {DIR_PROCESSED / 'cvm'}")


if __name__ == "__main__":  # pragma: no cover
    app()
