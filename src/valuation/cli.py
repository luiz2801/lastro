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
from valuation.data import macro as mac
from valuation.data import precos as prc
from valuation.data.http import ErroDownload, criar_sessao
from valuation.data.validacao import ErroDadosExternos, Leitura, Validado

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


def _linha_validada(v: Validado, formato: str) -> tuple[str, ...]:
    alt = "—" if v.valor_alt is None else f"{format(v.valor_alt, formato)} ({v.fonte_alt})"
    cor = {"ok": "green", "divergente": "red", "sem_validacao": "yellow", "manual": "cyan"}[
        v.status
    ]
    return (
        v.nome,
        f"{format(v.valor, formato)}",
        v.fonte,
        alt,
        f"[{cor}]{v.status}[/]",
        v.data.isoformat() if v.data else "—",
    )


@app.command()
def mercado(
    ticker: str = typer.Argument(..., help="Ex.: PETR4."),
    data_base: str | None = typer.Option(
        None, "--data-base", help="AAAA-MM-DD (padrão: settings)."
    ),
    forcar: bool = typer.Option(False, "--forcar", help="Ignora o cache e consulta as APIs."),
) -> None:
    """Preço, market cap, Ibovespa, dólar, Selic, IPCA e Rf, cada um conferido em 2 fontes."""
    agora = dt.datetime.now(dt.UTC)
    try:
        settings = carregar_settings()
        base = (
            dt.date.fromisoformat(data_base)
            if data_base
            else settings.resolver_data_base(agora.date())
        )
        tol = settings.validacao_cruzada
        sessao = criar_sessao()
        cadastro = _carregar_cadastro(settings, base, forcar)
        empresa = cad.empresa_por_ticker(cadastro, ticker)
        yf = prc.YFinanceProvider(
            DIR_RAW / "precos",
            dt.timedelta(hours=settings.cache_ttl_horas.precos),
            agora,
            forcar=forcar,
        )
        brapi = prc.BrapiProvider(sessao)

        precos: dict[str, Validado] = {}
        for classe in empresa.classes:
            try:
                precos[classe.ticker] = prc.preco_validado(
                    classe.ticker, base, yf, brapi, tolerancia_rel=tol.preco_rel
                )
            except ErroDadosExternos as e:
                console.print(f"[yellow]Aviso:[/] {classe.ticker} sem preço: {e}")
        if not precos:
            raise _erro(f"Nenhum preço disponível para {', '.join(empresa.tickers)}.")
        ibov = prc.preco_validado("^BVSP", base, yf, brapi, tolerancia_rel=tol.preco_rel)

        cambio_yf: Leitura | None = None
        try:
            d, v = prc.fechamento_ate(
                yf.historico("BRL=X", base - dt.timedelta(days=15), base), base
            )
            cambio_yf = Leitura(v, "yfinance BRL=X", d)
        except ErroDadosExternos as e:
            console.print(f"[yellow]Aviso:[/] dólar sem segunda fonte: {e}")

        macro = mac.carregar_macro(
            base,
            tolerancias=tol,
            rf_override=settings.custo_capital.rf_brl.override,
            cambio_alternativo=cambio_yf,
            dir_raw=DIR_RAW,
            ttl=dt.timedelta(hours=settings.cache_ttl_horas.macro),
            sessao=sessao,
            agora=agora,
            forcar=forcar,
        )
        composicao = pd.read_parquet(
            DIR_PROCESSED / "cvm" / str(empresa.cd_cvm) / "composicao_capital.parquet"
        )
        cap = prc.market_cap(empresa, composicao, {t: p.valor for t, p in precos.items()}, base)
    except FileNotFoundError as e:
        raise _erro(
            f"{e.filename} não existe. Rode `valuation atualizar --tickers {ticker}`."
        ) from e
    except (ErroConfiguracao, ErroDownload, cad.ErroCadastro, ErroDadosExternos) as e:
        raise _erro(str(e)) from e

    tabela = Table(title=f"Mercado — {', '.join(empresa.tickers)} em {base}")
    for coluna in ("Dado", "Valor", "Fonte principal", "Segunda fonte", "Validação", "Data"):
        tabela.add_column(coluna)
    for preco in precos.values():
        tabela.add_row(*_linha_validada(preco, ".2f"))
    tabela.add_row(*_linha_validada(ibov, ".0f"))
    tabela.add_row(*_linha_validada(macro.cambio, ".4f"))
    for taxa in (macro.selic, macro.ipca_12m, macro.rf_brl):
        tabela.add_row(*_linha_validada(taxa, ".2%"))
    console.print(tabela)

    detalhe = ", ".join(
        f"{c.acoes:,} {c.especie} a {c.preco:.2f}".replace(",", ".") for c in cap.classes
    )
    console.print(
        f"Market cap: R$ {cap.valor / 1e9:,.1f} bi ({detalhe}); ações de {cap.data_acoes}"
    )
    if macro.ipca_esperado:
        focus = ", ".join(f"{ano}: {x:.2%}" for ano, x in macro.ipca_esperado.items())
        console.print(f"IPCA esperado (Focus de {macro.data_focus}): {focus}")
    avisos = [*cap.avisos, *macro.avisos, *(a for v in (*precos.values(), ibov) if (a := v.aviso))]
    for aviso in avisos:
        console.print(f"[yellow]Aviso:[/] {aviso}")


if __name__ == "__main__":  # pragma: no cover
    app()
