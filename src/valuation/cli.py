"""Interface de linha de comando (`valuation`)."""

from __future__ import annotations

import datetime as dt
import logging
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pandas as pd
import typer
from rich.console import Console
from rich.table import Table

from valuation import __version__
from valuation.analise import cenarios as cen
from valuation.analise import sensibilidade as sens
from valuation.config import (
    CAMINHO_CADASTRO_MANUAL,
    CAMINHO_PERFIL,
    CAMINHO_SETORES,
    CAMINHO_UNIVERSO,
    DIR_EMPRESAS,
    DIR_PROCESSED,
    DIR_RAW,
    DIR_SAIDA,
    ErroConfiguracao,
    Setor,
    Settings,
    carregar_setores,
    carregar_settings,
)
from valuation.contabil import ErroContabil
from valuation.contabil import nao_financeiras as nf
from valuation.contabil import padronizacao as pad
from valuation.contabil import periodos as per
from valuation.contabil import qa as qa_mod
from valuation.contabil.moeda import detectar_moeda
from valuation.custo_capital import ErroCustoCapital, capm
from valuation.custo_capital import beta as bt
from valuation.custo_capital import kd as kd_mod
from valuation.custo_capital import wacc as wc
from valuation.data import cadastro as cad
from valuation.data import cvm
from valuation.data import macro as mac
from valuation.data import precos as prc
from valuation.data.http import ErroDownload, criar_sessao
from valuation.data.validacao import ErroDadosExternos, Leitura, Validado
from valuation.modelos import ErroModelo, dcf
from valuation.modelos import ponte as pt
from valuation.perfil import ErroPerfil, NomePerfil
from valuation.perfil import registro as reg
from valuation.perfil.parametros import parametros_do_perfil
from valuation.perfil.questionario import QUESTIONARIO
from valuation.projecao import ErroProjecao
from valuation.projecao import escrita as esc
from valuation.projecao import premissas as pm
from valuation.projecao import projetor as pj
from valuation.projecao import sugestor as sg
from valuation.saida.csv import FormatoCsv, gravar_csv, gravar_matriz

app = typer.Typer(
    help="Valuation de ações da B3. Uso pessoal e educacional; não é recomendação de investimento.",
    no_args_is_help=True,
    add_completion=False,
)
cadastro_app = typer.Typer(help="Consulta ao cadastro de companhias abertas.", no_args_is_help=True)
app.add_typer(cadastro_app, name="cadastro")
premissas_app = typer.Typer(
    help="Premissas de projeção por empresa (config/empresas/).", no_args_is_help=True
)
app.add_typer(premissas_app, name="premissas")
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


@dataclass(frozen=True)
class _Mercado:
    empresa: cad.Empresa
    precos: dict[str, Validado]
    ibov: Validado
    macro: mac.Macro
    cap: prc.MarketCap
    yf: prc.YFinanceProvider

    @property
    def avisos(self) -> list[str]:
        validados = (*self.precos.values(), self.ibov)
        return [*self.cap.avisos, *self.macro.avisos, *(a for v in validados if (a := v.aviso))]


def _mercado(
    ticker: str, settings: Settings, base: dt.date, agora: dt.datetime, forcar: bool
) -> _Mercado:
    """Preço por classe, Ibovespa, macro e market cap na data-base, cada um em 2 fontes."""
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
        d, v = prc.fechamento_ate(yf.historico("BRL=X", base - dt.timedelta(days=15), base), base)
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
    try:
        composicao = pd.read_parquet(
            DIR_PROCESSED / "cvm" / str(empresa.cd_cvm) / "composicao_capital.parquet"
        )
    except FileNotFoundError as e:
        raise _erro(
            f"{e.filename} não existe. Rode `valuation atualizar --tickers {ticker}`."
        ) from e
    cap = prc.market_cap(empresa, composicao, {t: p.valor for t, p in precos.items()}, base)
    return _Mercado(empresa, precos, ibov, macro, cap, yf)


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
        m = _mercado(ticker, settings, base, agora, forcar)
    except (ErroConfiguracao, ErroDownload, cad.ErroCadastro, ErroDadosExternos) as e:
        raise _erro(str(e)) from e
    macro, cap = m.macro, m.cap

    tabela = Table(title=f"Mercado — {', '.join(m.empresa.tickers)} em {base}")
    for coluna in ("Dado", "Valor", "Fonte principal", "Segunda fonte", "Validação", "Data"):
        tabela.add_column(coluna)
    for preco in m.precos.values():
        tabela.add_row(*_linha_validada(preco, ".2f"))
    tabela.add_row(*_linha_validada(m.ibov, ".0f"))
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
    for aviso in m.avisos:
        console.print(f"[yellow]Aviso:[/] {aviso}")


@dataclass(frozen=True)
class _Padronizada:
    empresa: cad.Empresa
    plano: pad.PlanoContas
    selecionadas: pd.DataFrame
    contas: pd.DataFrame
    moeda: str
    premissas: pm.PremissasEmpresa
    caminho_premissas: Path

    @property
    def ajustes(self) -> nf.AjustesContabeis:
        return pm.ajustes_contabeis(self.premissas.ajustes)


def _padronizar(ticker: str, settings: Settings) -> _Padronizada:
    """Padroniza as demonstrações de `ticker` e grava `contas_padronizadas.parquet`.

    Usa `config/empresas/{TICKER}.yaml` se existir (mapeamento extra, consolidado, moeda); senão,
    as premissas padrão.
    """
    data_base = settings.resolver_data_base(dt.date.today())
    empresa = cad.empresa_por_ticker(_carregar_cadastro(settings, data_base, False), ticker)
    if empresa.tipo_modelo != "nao_financeira":
        raise ErroContabil(
            f"{', '.join(empresa.tickers)} é {empresa.tipo_modelo}: só o plano de contas "
            "não financeiro existe por enquanto (financeiras na Fase 10)."
        )
    normalizado = cad.normalizar_ticker(ticker)
    caminho = pm.caminho_premissas(normalizado, DIR_EMPRESAS)
    if caminho.is_file():
        premissas = pm.carregar_premissas(caminho)
        pm.conferir_cadastro(premissas, empresa.tickers, empresa.tipo_modelo)
    else:
        premissas = pm.premissas_padrao(normalizado, "nao_financeira", empresa.tickers)
    plano = pad.carregar_mapeamento(extra=premissas.ajustes.mapeamento_extra)
    try:
        demonstracoes = pad.ler_demonstracoes(DIR_PROCESSED, empresa.cd_cvm)
    except FileNotFoundError as e:
        raise ErroContabil(
            f"{e.filename} não existe. Rode `valuation atualizar --tickers {ticker}`."
        ) from e
    selecionadas = pad.selecionar_reapresentacoes(
        demonstracoes, consolidado=premissas.ajustes.consolidado
    )
    moeda = detectar_moeda(selecionadas, premissas.moeda_relatorio)
    contas = pad.padronizar(selecionadas, plano, ticker=normalizado)
    contas.to_parquet(pad.caminho_padronizadas(DIR_PROCESSED, empresa.cd_cvm), index=False)
    return _Padronizada(empresa, plano, selecionadas, contas, moeda, premissas, caminho)


_COR_SEVERIDADE = {"erro": "red", "aviso": "yellow", "info": "cyan"}


@app.command()
def qa(ticker: str = typer.Argument(..., help="Ex.: PETR4.")) -> None:
    """Padroniza as demonstrações e roda os controles de qualidade (sai com 1 se houver erro)."""
    try:
        settings = carregar_settings()
        p = _padronizar(ticker, settings)
        resultado = qa_mod.verificar(
            p.selecionadas,
            p.contas,
            p.plano,
            ticker=cad.normalizar_ticker(ticker),
            moeda=p.moeda,
            historico_anos=settings.historico_anos,
        )
    except (ErroConfiguracao, ErroDownload, cad.ErroCadastro, ErroContabil) as e:
        raise _erro(str(e)) from e
    caminho = qa_mod.gravar(
        resultado, DIR_PROCESSED / "qa" / f"qa_{cad.normalizar_ticker(ticker)}.json"
    )

    tabela = Table(title=f"QA — {', '.join(p.empresa.tickers)} ({p.moeda})")
    for coluna in ("Severidade", "Verificação", "Mensagem", "Períodos"):
        tabela.add_column(coluna)
    for v in resultado.verificacoes:
        periodos = ", ".join(v.periodos[:6]) + (" …" if len(v.periodos) > 6 else "")
        cor = _COR_SEVERIDADE[v.severidade]
        tabela.add_row(f"[{cor}]{v.severidade}[/]", v.codigo, v.mensagem, periodos)
    if resultado.verificacoes:
        console.print(tabela)
    else:
        console.print("[green]Nenhum problema encontrado.[/]")

    incompletas = {c: f for c, f in resultado.cobertura.items() if f < 1}
    if incompletas:
        texto = ", ".join(f"{c} {f:.0%}" for c, f in incompletas.items())
        console.print(f"Cobertura das contas críticas abaixo de 100%: {texto}")
    else:
        console.print(f"Cobertura das {len(resultado.cobertura)} contas críticas: 100%.")
    for item in resultado.nao_mapeadas:
        console.print(
            f"Não mapeada relevante: {item['demonstracao']} {item['cd_conta']} "
            f"{item['ds_conta']} = {item['valor'] / 1e6:,.0f} mi "
            f"({item['fracao_da_base']:.1%} da base) em {item['data']}"
        )
    console.print(f"Gravado em {caminho}")
    if resultado.erros:
        raise typer.Exit(code=1)


_LINHAS_HISTORICO = (
    ("receita_liquida", "Receita líquida", "mi"),
    ("ebitda", "EBITDA", "mi"),
    ("margem_ebitda", "Margem EBITDA", "%"),
    ("ebit_ajustado", "EBIT ajustado", "mi"),
    ("lucro_liquido_controladora", "Lucro controladora", "mi"),
    ("aliquota_efetiva", "Alíquota efetiva", "%"),
    ("da", "D&A", "mi"),
    ("capex", "Capex", "mi"),
    ("delta_nwc", "ΔNWC", "mi"),
    ("fcff", "FCFF", "mi"),
    ("divida_financeira", "Dívida financeira", "mi"),
    ("arrendamento", "Arrendamento", "mi"),
    ("caixa_e_aplicacoes", "Caixa e aplicações", "mi"),
    ("divida_liquida", "Dívida líquida", "mi"),
    ("roic", "ROIC", "%"),
    ("dividendos_pagos", "Dividendos pagos", "mi"),
)


def _formatar(valor: float, unidade: str) -> str:
    if pd.isna(valor):
        return "—"
    if unidade == "%":
        return f"{valor:.1%}".replace(".", ",")
    return f"{valor / 1e6:,.0f}".replace(",", ".")


@app.command()
def historico(
    ticker: str = typer.Argument(..., help="Ex.: PETR4."),
    anos: int = typer.Option(5, "--anos", min=1, help="Quantos exercícios mostrar."),
    trimestral: bool = typer.Option(
        False, "--trimestral", help="Últimos 8 trimestres em vez dos exercícios."
    ),
) -> None:
    """Métricas históricas padronizadas (R$ milhões), com a coluna LTM."""
    try:
        settings = carregar_settings()
        p = _padronizar(ticker, settings)
        aliquota = settings.impostos.aliquota_nominal
        if trimestral:
            tabela_m = (
                per.trimestral(p.contas)
                .tail(8)
                .reindex(
                    columns=[
                        "receita_liquida",
                        "ebit",
                        "da",
                        "lucro_liquido_controladora",
                        "capex",
                        "dividendos_pagos",
                    ]
                )
            )
            tabela_m["ebitda"] = tabela_m["ebit"] + tabela_m["da"]
            # Mesma convenção das métricas: saídas de caixa positivas.
            tabela_m["capex"] = -tabela_m["capex"]
            tabela_m["dividendos_pagos"] = -tabela_m["dividendos_pagos"]
            colunas = [f"{d.month // 3}T{d:%y}" for d in tabela_m.index]
        else:
            m = nf.metricas(per.anual(p.contas), aliquota_nominal=aliquota, ajustes=p.ajustes)
            m = m.tail(anos)
            ltm = nf.metricas_ltm(p.contas, aliquota_nominal=aliquota, ajustes=p.ajustes)
            tabela_m = pd.concat([m, ltm.to_frame().T])
            fim = pd.Timestamp(str(ltm.name))
            colunas = [*map(str, m.index), f"LTM {fim:%m/%Y}"]
    except (ErroConfiguracao, ErroDownload, cad.ErroCadastro, ErroContabil) as e:
        raise _erro(str(e)) from e

    tabela = Table(title=f"Histórico — {', '.join(p.empresa.tickers)} (R$ milhões, {p.moeda})")
    tabela.add_column("Métrica")
    for coluna in colunas:
        tabela.add_column(coluna, justify="right")
    for chave, rotulo, unidade in _LINHAS_HISTORICO:
        if chave in tabela_m.columns:
            tabela.add_row(rotulo, *(_formatar(v, unidade) for v in tabela_m[chave]))
    console.print(tabela)


@app.command()
def cobertura(
    tickers: str | None = typer.Option(
        None, "--tickers", help="Lista separada por vírgula, ex.: PETR4,VALE3."
    ),
    tudo: bool = typer.Option(False, "--tudo", help="Todos os tickers do universo configurado."),
) -> None:
    """Fração dos exercícios com cada conta crítica mapeada, por companhia."""
    if bool(tickers) == tudo:
        raise _erro("Informe --tickers ou --tudo (um dos dois).")
    try:
        settings = carregar_settings()
        lista = (
            [t.strip() for t in tickers.split(",") if t.strip()]
            if tickers
            else _tickers_do_universo(CAMINHO_UNIVERSO)
        )
        colunas = {}
        for t in lista:
            p = _padronizar(t, settings)
            colunas[cad.normalizar_ticker(t)] = pad.cobertura(p.contas, p.plano.criticas)
    except (ErroConfiguracao, ErroDownload, cad.ErroCadastro, ErroContabil) as e:
        raise _erro(str(e)) from e

    matriz = pd.DataFrame(colunas)
    tabela = Table(title="Cobertura das contas críticas (fração dos exercícios)")
    tabela.add_column("Conta")
    for t in matriz.columns:
        tabela.add_column(t, justify="right")
    for conta, linha in matriz.iterrows():
        celulas = [f"[{'green' if f >= 0.95 else 'red'}]{f:.0%}[/]" for f in linha]
        tabela.add_row(str(conta), *celulas)
    console.print(tabela)
    console.print(f"Média geral: {matriz.to_numpy().mean():.1%}")


def _perguntar_questionario() -> dict[str, int]:
    console.print(
        "[bold]Questionário de perfil do investidor[/] — responda com o número da alternativa.\n"
        "Uso pessoal: o perfil só ajusta margem de segurança, pesos dos cenários, horizonte e "
        "retorno mínimo; não é recomendação de investimento.\n"
    )
    respostas: dict[str, int] = {}
    for i, pergunta in enumerate(QUESTIONARIO, start=1):
        console.print(f"[bold]{i}/{len(QUESTIONARIO)}. {pergunta.enunciado}[/]")
        for n, alternativa in enumerate(pergunta.alternativas, start=1):
            console.print(f"  {n}) {alternativa.texto}")
        while True:
            texto = typer.prompt("Resposta").strip()
            if texto.isdigit() and 1 <= int(texto) <= len(pergunta.alternativas):
                break
            console.print(f"[yellow]Digite um número de 1 a {len(pergunta.alternativas)}.[/]")
        respostas[pergunta.chave] = int(texto)
        console.print()
    return respostas


def _mostrar_perfil(registro: reg.RegistroPerfil, settings: Settings, hoje: dt.date) -> None:
    situacao = (
        f"[red]vencido em {registro.valido_ate}[/]"
        if registro.vencido(hoje)
        else f"válido até {registro.valido_ate}"
    )
    console.print(
        f"Perfil: [bold]{registro.perfil}[/] (pontuação {registro.pontuacao} de 50; "
        f"respondido em {registro.data}; {situacao})"
    )
    if registro.vetos_aplicados:
        console.print(f"Vetos aplicados: {', '.join(registro.vetos_aplicados)}")
    p = parametros_do_perfil(registro.perfil, settings.perfil)
    tabela = Table(title=f"Parâmetros do perfil {p.perfil} (settings.yaml)")
    tabela.add_column("Parâmetro")
    tabela.add_column("Valor", justify="right")
    tabela.add_row("Margem de segurança", f"{p.margem_seguranca:.0%}")
    tabela.add_row(
        "Pesos dos cenários (pess./base/otim.)",
        f"{p.peso_pessimista:.0%} / {p.peso_base:.0%} / {p.peso_otimista:.0%}",
    )
    tabela.add_row("Horizonte de projeção explícita", f"{p.horizonte_anos} anos")
    spread = f"{p.hurdle_spread_selic * 100:.1f}".replace(".", ",")
    tabela.add_row("Retorno mínimo (hurdle)", f"Selic + {spread} p.p.")
    console.print(tabela)


@app.command()
def perfil(
    mostrar: bool = typer.Option(False, "--mostrar", help="Só mostra o perfil gravado."),
    refazer: bool = typer.Option(
        False, "--refazer", help="Refaz o questionário mesmo com perfil válido."
    ),
) -> None:
    """Questionário de perfil do investidor; grava perfil/perfil_investidor.json (12 meses)."""
    if mostrar and refazer:
        raise _erro("Use --mostrar ou --refazer, não os dois.")
    hoje = dt.date.today()
    try:
        settings = carregar_settings()
        atual: reg.RegistroPerfil | None = None
        try:
            atual = reg.ler(CAMINHO_PERFIL)
        except FileNotFoundError:
            pass
        except ErroPerfil as e:
            if not refazer:
                raise
            console.print(f"[yellow]Aviso:[/] {e}")
    except (ErroConfiguracao, ErroPerfil) as e:
        raise _erro(str(e)) from e

    if mostrar:
        if atual is None:
            raise _erro("Nenhum perfil gravado. Rode `valuation perfil`.")
        _mostrar_perfil(atual, settings, hoje)
        return
    if atual is not None and not atual.vencido(hoje) and not refazer:
        console.print("Já existe um perfil válido; use --refazer para responder de novo.")
        _mostrar_perfil(atual, settings, hoje)
        return
    if atual is not None and atual.vencido(hoje):
        console.print(f"[yellow]O perfil gravado venceu em {atual.valido_ate}.[/]")

    novo = reg.criar_registro(_perguntar_questionario(), hoje)
    caminho = reg.gravar(novo, CAMINHO_PERFIL)
    _mostrar_perfil(novo, settings, hoje)
    console.print(f"Gravado em {caminho}")


def _setor(chave: str | None) -> Setor | None:
    if chave is None:
        return None
    setores = carregar_setores(CAMINHO_SETORES)
    if chave not in setores:
        raise ErroConfiguracao(
            f"pares.setor {chave!r} não está em {CAMINHO_SETORES.name} "
            f"(disponíveis: {', '.join(sorted(setores))})."
        )
    return setores[chave]


def _horizonte(
    premissas: pm.PremissasEmpresa, settings: Settings, hoje: dt.date, override: NomePerfil | None
) -> tuple[int, str]:
    """Anos de projeção explícita: o número do YAML ou o do perfil do investidor."""
    h = premissas.projecao.horizonte_anos
    if h != "perfil":
        return h, "YAML da empresa"
    efetivo = reg.resolver_perfil(CAMINHO_PERFIL, hoje, override)
    anos = parametros_do_perfil(efetivo.perfil, settings.perfil).horizonte_anos
    return anos, f"perfil {efetivo.perfil} ({efetivo.origem})"


def _limite_aliquota(p: _Padronizada, settings: Settings) -> float:
    limite = p.premissas.projecao.aliquota_imposto.limite_superior
    return settings.impostos.aliquota_nominal if limite is None else limite


def _sugerir(
    p: _Padronizada, settings: Settings, base: dt.date
) -> tuple[pd.DataFrame, Setor | None, sg.Sugestoes]:
    """Métricas dos exercícios encerrados antes da data-base, setor e premissas sugeridas."""
    aliquota = settings.impostos.aliquota_nominal
    historico = nf.metricas(per.anual(p.contas), aliquota_nominal=aliquota, ajustes=p.ajustes)
    historico = historico[historico.index < pj.primeiro_ano_aberto(base)]
    setor = _setor(p.premissas.pares.setor)
    sugestoes = sg.sugerir(
        historico,
        g_terminal=pj.g_terminal(p.premissas.projecao.terminal, settings.terminal),
        aliquota_limite=_limite_aliquota(p, settings),
        commodity=setor.commodity if setor else False,
        setor=p.premissas.pares.setor,
    )
    return historico, setor, sugestoes


def _resolver(
    p: _Padronizada, settings: Settings, sugestoes: sg.Sugestoes, base: dt.date, horizonte: int
) -> pj.PremissasResolvidas:
    """Premissas numéricas do cenário base."""
    ajustes = p.premissas.ajustes
    return pj.resolver(
        p.premissas.projecao,
        sugestoes,
        anos=pj.anos_projetados(sugestoes.ano_base, base, horizonte),
        aliquota_limite=_limite_aliquota(p, settings),
        descontar_arrendamento=ajustes.ifrs16 == "divida"
        and ajustes.capex_equivalente_arrendamento,
    )


# (rótulo, coluna em sugestor.razoes, sugestões, campo no YAML)
_LINHAS_SUGESTAO = (
    ("Crescimento da receita", "crescimento", ("crescimento_inicio", "crescimento_fim")),
    ("Margem EBITDA ajustada", "margem_ebitda_ajustada", ("margem_inicio", "margem_fim")),
    ("D&A / receita", "da_sobre_receita", ("da_sobre_receita",)),
    ("Capex / receita", "capex_sobre_receita", ("capex_sobre_receita",)),
    ("NWC / receita", "nwc_sobre_receita", ("nwc_sobre_receita",)),
    ("Arrendamento / receita", "arrendamento_sobre_receita", ("arrendamento_sobre_receita",)),
    ("Alíquota", "aliquota_efetiva", ("aliquota",)),
)


def _no_yaml(config: pm.ConfigProjecao, coluna: str) -> str:
    valor: object = {
        "crescimento": config.receita.crescimento,
        "margem_ebitda_ajustada": config.margens.ebitda,
        "aliquota_efetiva": config.aliquota_imposto.valor,
    }.get(coluna, getattr(config, coluna, None))
    if isinstance(valor, pm.Trajetoria):
        partes = [x if x == pm.SUGERIDO else sg.pct(float(x)) for x in (valor.inicio, valor.fim)]
        return " → ".join(str(x) for x in partes)
    if isinstance(valor, tuple):
        return "lista: " + ", ".join(sg.pct(x) for x in valor)
    return str(valor) if valor == pm.SUGERIDO else sg.pct(float(str(valor)))


def _mostrar_sugestoes(p: _Padronizada, s: sg.Sugestoes) -> None:
    def e(linha: str, coluna: str) -> str:
        return sg.pct(cast(float, s.estatisticas.at[linha, coluna]))

    tabela = Table(
        title=f"Premissas sugeridas x histórico — {p.premissas.ticker} (até {s.ano_base})"
    )
    for coluna in ("Premissa", str(s.ano_base), "Mediana 5a", "Mediana 10a", "Sugerido", "No YAML"):
        tabela.add_column(coluna, justify="left" if coluna in ("Premissa", "No YAML") else "right")
    for rotulo, coluna, campos in _LINHAS_SUGESTAO:
        sugerido = " → ".join(sg.pct(getattr(s, c).valor) for c in campos)
        tabela.add_row(
            rotulo,
            e("ultimo", coluna),
            e("mediana_5a", coluna),
            e("mediana_10a", coluna),
            sugerido,
            _no_yaml(p.premissas.projecao, coluna),
        )
    console.print(tabela)
    cagrs = ", ".join(f"{n}a {e(f'cagr_{n}a', 'crescimento')}" for n in (3, 5, 10))
    console.print(f"CAGR da receita: {cagrs}.")
    console.print(
        f"Deltas sugeridos dos cenários: crescimento ±{sg.pp(s.delta_crescimento.valor)}, "
        f"margem ±{sg.pp(s.delta_margem.valor)}, capex ±{sg.pp(s.delta_capex.valor)} "
        "(pessimista: -, -, +)."
    )


_LINHAS_PROJECAO = (
    ("fracao", "Fração do ano por vir", "%"),
    ("crescimento", "Crescimento", "%"),
    ("receita_liquida", "Receita líquida", "mi"),
    ("ebitda", "EBITDA", "mi"),
    ("margem_ebitda", "Margem EBITDA", "%"),
    ("ebit", "EBIT", "mi"),
    ("imposto", "Imposto sobre EBIT", "mi"),
    ("nopat", "NOPAT", "mi"),
    ("da", "D&A", "mi"),
    ("capex", "Capex", "mi"),
    ("delta_nwc", "ΔNWC", "mi"),
    ("arrendamento", "Arrendamento", "mi"),
    ("fcff", "FCFF (ano inteiro)", "mi"),
)


def _mostrar_projecao(tabela_p: pd.DataFrame, titulo: str) -> None:
    tabela = Table(title=titulo)
    tabela.add_column("Métrica")
    for ano in tabela_p.index:
        tabela.add_column(str(ano), justify="right")
    for chave, rotulo, unidade in _LINHAS_PROJECAO:
        tabela.add_row(rotulo, *(_formatar(v, unidade) for v in tabela_p[chave]))
    console.print(tabela)


@premissas_app.command("sugerir")
def premissas_sugerir(
    ticker: str = typer.Argument(..., help="Ex.: PETR4."),
    escrever: bool = typer.Option(
        False,
        "--escrever",
        help="Grava config/empresas/{TICKER}.yaml comentado (anterior em .bak).",
    ),
    perfil_override: str | None = typer.Option(
        None, "--perfil", help="conservador|moderado|arrojado (horizonte, se o YAML usar perfil)."
    ),
    data_base: str | None = typer.Option(
        None, "--data-base", help="AAAA-MM-DD (padrão: settings)."
    ),
) -> None:
    """Sugere premissas a partir do histórico, compara com o YAML e mostra a projeção base."""
    hoje = dt.date.today()
    if perfil_override not in (None, "conservador", "moderado", "arrojado"):
        raise _erro("--perfil deve ser conservador, moderado ou arrojado.")
    override = cast(NomePerfil | None, perfil_override)
    try:
        settings = carregar_settings()
        base = dt.date.fromisoformat(data_base) if data_base else settings.resolver_data_base(hoje)
        p = _padronizar(ticker, settings)
        historico, setor, sugestoes = _sugerir(p, settings, base)
    except ValueError as e:
        raise _erro(f"--data-base inválida: {e}") from e
    except (ErroConfiguracao, ErroDownload, cad.ErroCadastro, ErroContabil, ErroProjecao) as e:
        raise _erro(str(e)) from e

    _mostrar_sugestoes(p, sugestoes)
    if setor is None:
        console.print(
            "[yellow]Aviso:[/] pares.setor não definido no YAML: sem checagem de commodity."
        )
    try:
        horizonte, origem = _horizonte(p.premissas, settings, hoje, override)
    except ErroPerfil as e:
        console.print(f"[yellow]Projeção não mostrada:[/] {e}")
    else:
        try:
            resolvidas = _resolver(p, settings, sugestoes, base, horizonte)
            tabela_p = pj.projetar(historico, resolvidas, data_base=base)
        except ErroProjecao as e:
            raise _erro(str(e)) from e
        _mostrar_projecao(
            tabela_p,
            f"Projeção base — {p.premissas.ticker} (R$ milhões, {p.moeda}; data-base {base}; "
            f"{horizonte} anos pelo {origem})",
        )
        fechados = [str(a) for a, f in tabela_p["fracao"].items() if f == 0]
        if fechados:
            console.print(
                f"[yellow]Aviso:[/] {', '.join(fechados)} já encerrado(s) sem DFP: projetado(s) "
                "só como ponte, sem fluxo a descontar."
            )
    for aviso in sugestoes.avisos:
        console.print(f"[yellow]Aviso:[/] {aviso}")

    if escrever:
        caminho = p.caminho_premissas
        if caminho.is_file():
            caminho.replace(caminho.with_suffix(".yaml.bak"))
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(esc.renderizar(p.premissas, sugestoes, data_base=base), encoding="utf-8")
        console.print(f"Gravado em {caminho}")
    elif not p.caminho_premissas.is_file():
        console.print(f"{p.caminho_premissas} não existe; use --escrever para criá-lo.")


# Prazo do ITR é de 45 dias após o trimestre: até ~140 dias de defasagem é o normal.
DEFASAGEM_AVISO_DIAS = 140


def _data_balanco(contas: pd.DataFrame, base: dt.date) -> pd.Timestamp:
    """Última data até a data-base com fluxos acumulados e balanço (ponto do LTM)."""
    comuns = per.acumulado_no_ano(contas).index.intersection(per.saldos(contas).index)
    comuns = comuns[comuns <= pd.Timestamp(base)]
    if comuns.empty:
        raise ErroContabil(f"Nenhuma demonstração até {base}.")
    return pd.Timestamp(comuns.max())


def _beta(
    p: _Padronizada, m: _Mercado, settings: Settings, base: dt.date, aliquota: float
) -> bt.ResultadoBeta:
    """Beta pelo método do YAML da empresa (se declarado) ou do `settings`."""
    cfg = settings.custo_capital.beta
    empresa = p.premissas.custo_capital
    metodo = empresa.beta.metodo if "beta" in empresa.model_fields_set else cfg.metodo
    if metodo == "manual":
        if empresa.beta.valor is None:
            raise ErroConfiguracao("beta manual exige custo_capital.beta.valor no YAML da empresa.")
        return bt.manual(empresa.beta.valor)
    if metodo == "comparaveis":
        setor = _setor(p.premissas.pares.setor)
        if setor is None or not setor.pares:
            return bt.comparaveis({}, divida_sobre_equity_alvo=0.0, aliquota=aliquota)
        raise ErroCustoCapital("Beta por comparáveis ainda não implementado (Fase 8).")
    inicio = base - dt.timedelta(weeks=cfg.janela_semanas + 2)
    historicos = {t: m.yf.historico(prc.simbolo_yahoo(t), inicio, base) for t in m.precos}
    ticker = bt.classe_mais_liquida(historicos, base, cfg.janela_semanas)
    ibov = m.yf.historico("^BVSP", inicio, base)
    return bt.regressao(
        historicos[ticker]["adj_close"],
        ibov["adj_close"],
        data_base=base,
        janela_semanas=cfg.janela_semanas,
        ajuste_blume=cfg.ajuste_blume,
        min_r2_aviso=cfg.min_r2_aviso,
        ticker=ticker,
    )


def _custo_capital(
    p: _Padronizada, m: _Mercado, settings: Settings, base: dt.date
) -> wc.CustoCapital:
    """Beta, Ke, Kd, estrutura e WACC na moeda de reporte da empresa."""
    cfg = settings.custo_capital
    aliquota = settings.impostos.aliquota_nominal
    moeda = cast(capm.Moeda, p.moeda)
    avisos: list[str] = []

    metodo, aviso = capm.metodo_efetivo(cfg.metodo, moeda)
    if aviso:
        avisos.append(aviso)
    inflacao_brl = (
        m.macro.ipca_esperado[max(m.macro.ipca_esperado)] if m.macro.ipca_esperado else None
    )

    data_bal = _data_balanco(p.contas, base)
    ltm = nf.metricas_ltm(p.contas, aliquota_nominal=aliquota, dt_fim=data_bal, ajustes=p.ajustes)
    defasagem = (base - data_bal.date()).days
    if defasagem > DEFASAGEM_AVISO_DIAS:
        avisos.append(f"Balanço de {data_bal.date()} ({defasagem} dias antes da data-base).")
    equity = m.cap.valor if moeda == "BRL" else m.cap.valor / m.macro.cambio.valor
    est = wc.estrutura(
        metodo=cfg.estrutura_alvo.metodo,
        divida=float(ltm["divida_bruta"]),
        equity=equity,
        divida_sobre_capital_alvo=cfg.estrutura_alvo.divida_sobre_capital,
    )

    beta = wc.beta_na_estrutura(_beta(p, m, settings, base, aliquota), est, aliquota)
    ke = capm.custo_capital_proprio(
        metodo=metodo,
        moeda=moeda,
        beta=beta.beta,
        erp=cfg.erp,
        rf_brl=m.macro.rf_brl.valor,
        rf_usd=cfg.rf_usd,
        crp=cfg.crp,
        inflacao_usd=cfg.inflacao_usd_lp,
        inflacao_brl=inflacao_brl,
    )

    kd_cfg = p.premissas.custo_capital.kd
    if kd_cfg.metodo == "manual" and kd_cfg.valor is not None:
        kd = kd_mod.manual(kd_cfg.valor)
    else:
        anual = per.anual(p.contas)
        if "despesas_financeiras" not in anual.columns:
            raise ErroCustoCapital(
                "Sem despesas financeiras na DRE para o Kd histórico: use "
                "custo_capital.kd: {metodo: manual, valor: ...} no YAML da empresa."
            )
        fechados = anual.index < pj.primeiro_ano_aberto(base)
        hist = nf.metricas(anual[fechados], aliquota_nominal=aliquota, ajustes=p.ajustes)
        rf = m.macro.rf_brl.valor if moeda == "BRL" else cfg.rf_usd
        kd = kd_mod.historico(
            anual.loc[fechados, "despesas_financeiras"],
            hist["divida_bruta"],
            piso=rf + cfg.kd.spread_min,
            teto=rf + cfg.kd.spread_max,
        )

    cc = wc.montar(
        data_base=base,
        beta=beta,
        ke=ke,
        kd=kd,
        aliquota=aliquota,
        estrutura=est,
        data_balanco=data_bal.date(),
        avisos=tuple(avisos),
    )
    g = pj.g_terminal(p.premissas.projecao.terminal, settings.terminal)
    wc.validar_g(cc.wacc, g.valor)
    return cc


def _formatar_componente(componente: str, valor: float) -> str:
    if pd.isna(valor):
        return ""
    if componente in ("divida_bruta", "market_cap"):
        return f"{_formatar(valor, 'mi')} mi"
    if componente == "beta_n_obs":
        return f"{valor:.0f}"
    if componente.startswith("beta"):
        return f"{valor:.3f}".replace(".", ",")
    return f"{valor:.2%}".replace(".", ",")


@app.command()
def wacc(
    ticker: str = typer.Argument(..., help="Ex.: PETR4."),
    data_base: str | None = typer.Option(
        None, "--data-base", help="AAAA-MM-DD (padrão: settings)."
    ),
    forcar: bool = typer.Option(False, "--forcar", help="Ignora o cache e consulta as APIs."),
    saida: str | None = typer.Option(
        None, "--saida", help="Diretório raiz da saída (padrão: saida/)."
    ),
    formato_csv: str = typer.Option("br", "--formato-csv", help="br | intl."),
) -> None:
    """Beta, Ke, Kd e WACC; grava saida/{TICKER}/{data-base}/wacc.csv."""
    agora = dt.datetime.now(dt.UTC)
    if formato_csv not in ("br", "intl"):
        raise _erro("--formato-csv deve ser br ou intl.")
    try:
        settings = carregar_settings()
        base = (
            dt.date.fromisoformat(data_base)
            if data_base
            else settings.resolver_data_base(agora.date())
        )
        p = _padronizar(ticker, settings)
        m = _mercado(ticker, settings, base, agora, forcar)
        cc = _custo_capital(p, m, settings, base)
    except ValueError as e:
        raise _erro(f"--data-base inválida: {e}") from e
    except (
        ErroConfiguracao,
        ErroDownload,
        cad.ErroCadastro,
        ErroDadosExternos,
        ErroContabil,
        ErroProjecao,
        ErroCustoCapital,
    ) as e:
        raise _erro(str(e)) from e

    tab = wc.tabela(cc)
    tabela = Table(title=f"Custo de capital — {p.premissas.ticker} em {base} ({cc.ke.moeda})")
    for coluna in ("Componente", "Valor", "Detalhe"):
        tabela.add_column(coluna)
    for componente, valor, detalhe in zip(
        tab["componente"], tab["valor"], tab["detalhe"], strict=True
    ):
        if componente != "aviso":
            tabela.add_row(str(componente), _formatar_componente(str(componente), valor), detalhe)
    console.print(tabela)
    raiz = Path(saida) if saida else DIR_SAIDA
    caminho = raiz / p.premissas.ticker / base.isoformat() / "wacc.csv"
    gravar_csv(tab, caminho, settings.csv, cast(FormatoCsv, formato_csv))
    for aviso in [*cc.avisos, *m.avisos]:
        console.print(f"[yellow]Aviso:[/] {aviso}")
    console.print(f"Gravado em {caminho}")


def _dados_avaliacao(
    p: _Padronizada,
    m: _Mercado,
    cc: wc.CustoCapital,
    settings: Settings,
    base: dt.date,
    historico: pd.DataFrame,
) -> dcf.DadosAvaliacao:
    """Ponte com o balanço dos pesos do WACC, ações em circulação do market cap e câmbio."""
    balanco = nf.metricas_ltm(
        p.contas,
        aliquota_nominal=settings.impostos.aliquota_nominal,
        dt_fim=pd.Timestamp(cc.data_balanco),
        ajustes=p.ajustes,
    )
    itens = pt.itens_do_balanco(
        balanco,
        acoes=sum(c.acoes for c in m.cap.classes),
        data_balanco=cc.data_balanco,
        coligadas=p.premissas.ajustes.coligadas,
        minoritarios=p.premissas.ajustes.minoritarios,
    )
    return dcf.DadosAvaliacao(
        historico=historico,
        ponte=itens,
        data_base=base,
        meio_periodo=settings.dcf.convencao_meio_periodo,
        alerta_tv_sobre_ev=settings.dcf.alerta_tv_sobre_ev,
        cambio=1.0 if p.moeda == "BRL" else m.macro.cambio.valor,
    )


def _ronic(p: _Padronizada, settings: Settings, historico: pd.DataFrame) -> dcf.Ronic:
    """RONIC do YAML da empresa ou do settings; `roic_historico` = mediana dos 5 últimos anos."""
    escolha = p.premissas.projecao.terminal.ronic
    escolha = settings.terminal.ronic if escolha is None else escolha
    roic = historico["roic"].dropna().tail(sg.JANELA_CURTA)
    return dcf.resolver_ronic(escolha, roic_historico=float(roic.median()) if len(roic) else None)


def _reais(valor: float) -> str:
    return "—" if pd.isna(valor) else f"R$ {valor:,.2f}".translate(str.maketrans(",.", ".,"))


def _taxa(valor: float | None) -> str:
    return "sem solução" if valor is None or pd.isna(valor) else f"{valor:.2%}".replace(".", ",")


def _resumo(
    ticker: str,
    base: dt.date,
    efetivo: reg.PerfilEfetivo,
    moeda: str,
    cc: wc.CustoCapital,
    r: cen.ResultadoCenarios,
    referencia: pj.NomeCenario,
    avisos: list[str],
) -> pd.DataFrame:
    """Linha única de `resumo.csv` (seção 13 do CLAUDE.md; múltiplos entram na Fase 8)."""
    av = r.avaliacoes[referencia]
    valores = {
        c: r.avaliacoes[c].valor_por_acao if c in r.avaliacoes else None for c in pj.CENARIOS
    }
    linha: dict[str, object] = {
        "ticker": ticker,
        "data_base": base.isoformat(),
        "perfil": efetivo.perfil,
        "origem_perfil": efetivo.origem,
        "moeda_reporte": moeda,
        "cambio": av.cambio,
        "preco": r.preco,
        **{f"valor_{c}": v for c, v in valores.items()},
        "cenarios": ",".join(r.pesos),
        "valor_ponderado": r.valor_ponderado,
        "margem_seguranca": r.perfil.margem_seguranca,
        "preco_maximo_compra": r.preco_maximo_compra,
        "upside": r.upside,
        "ke_implicito": r.ke_implicito,
        "hurdle": r.hurdle,
        "wacc_implicito": r.wacc_implicito,
        "wacc": cc.wacc,
        "ke": cc.ke.ke,
        "g": av.dcf.g,
        "ronic": av.dcf.ronic,
        "vt_sobre_ev": av.dcf.tv_sobre_ev,
        "ev_ebitda_terminal": av.dcf.ev_ebitda_terminal,
        "data_balanco": cc.data_balanco.isoformat(),
        "avisos": " | ".join(avisos),
    }
    df = pd.DataFrame([linha])
    numericas = [c for c, v in linha.items() if v is None or isinstance(v, float | int)]
    df[numericas] = df[numericas].astype("float64")
    return df


def _mostrar_valuation(
    r: cen.ResultadoCenarios, cc: wc.CustoCapital, settings: Settings, titulo: str
) -> None:
    tabela = Table(title=titulo)
    colunas = ["Cenário", "Peso", "VP fluxos", "VP terminal", "EV", "VT/EV"]
    if settings.terminal.checagem_multiplo_saida:
        colunas.append("EV/EBITDA term.")
    for coluna in (*colunas, "Equity", "Valor por ação"):
        tabela.add_column(coluna, justify="left" if coluna == "Cenário" else "right")
    for c, av in r.avaliacoes.items():
        d = av.dcf
        linha = [
            c,
            f"{r.pesos[c]:.0%}",
            _formatar(d.vp_fluxos, "mi"),
            _formatar(d.vp_terminal, "mi"),
            _formatar(d.ev, "mi"),
            _formatar(d.tv_sobre_ev, "%"),
        ]
        if settings.terminal.checagem_multiplo_saida:
            x = d.ev_ebitda_terminal
            linha.append("—" if pd.isna(x) else f"{x:.1f}x".replace(".", ","))
        linha += [_formatar(av.ponte.equity, "mi"), _reais(av.valor_por_acao)]
        tabela.add_row(*linha)
    console.print(tabela)

    d = next(iter(r.avaliacoes.values())).dcf
    console.print(
        f"Checagens: WACC {_taxa(cc.wacc)} > g {_taxa(d.g)} "
        f"(teto {_taxa(settings.terminal.g_nominal_max)}); RONIC {_taxa(d.ronic)}; "
        f"alerta de VT/EV acima de {settings.dcf.alerta_tv_sobre_ev:.0%}."
    )
    p = r.perfil
    console.print(
        f"Valor ponderado ({p.perfil}): [bold]{_reais(r.valor_ponderado)}[/]; margem de segurança "
        f"{p.margem_seguranca:.0%} ⇒ preço máximo de compra [bold]{_reais(r.preco_maximo_compra)}"
        f"[/]; preço {_reais(r.preco)} (upside {_taxa(r.upside)})."
    )
    console.print(
        f"Retorno implícito no preço: Ke {_taxa(r.ke_implicito)} contra hurdle "
        f"{_taxa(r.hurdle)} (Selic + {sg.pp(p.hurdle_spread_selic)}); "
        f"WACC {_taxa(r.wacc_implicito)} contra WACC de {_taxa(cc.wacc)}."
    )


@app.command()
def rodar(
    ticker: str = typer.Argument(..., help="Ex.: PETR4."),
    cenario: str = typer.Option(
        "todos", "--cenario", help="base | pessimista | otimista | todos (ponderados pelo perfil)."
    ),
    data_base: str | None = typer.Option(
        None, "--data-base", help="AAAA-MM-DD (padrão: settings)."
    ),
    perfil_override: str | None = typer.Option(
        None, "--perfil", help="conservador|moderado|arrojado (sobrescreve o perfil gravado)."
    ),
    saida: str | None = typer.Option(
        None, "--saida", help="Diretório raiz da saída (padrão: saida/)."
    ),
    formato_csv: str = typer.Option("br", "--formato-csv", help="br | intl."),
    forcar: bool = typer.Option(False, "--forcar", help="Ignora o cache e consulta as APIs."),
) -> None:
    """Valuation por DCF: cenários ponderados pelo perfil, ponte EV -> equity e sensibilidade."""
    hoje = dt.date.today()
    agora = dt.datetime.now(dt.UTC)
    if cenario not in (*pj.CENARIOS, "todos"):
        raise _erro("--cenario deve ser base, pessimista, otimista ou todos.")
    if formato_csv not in ("br", "intl"):
        raise _erro("--formato-csv deve ser br ou intl.")
    if perfil_override not in (None, "conservador", "moderado", "arrojado"):
        raise _erro("--perfil deve ser conservador, moderado ou arrojado.")
    override = cast(NomePerfil | None, perfil_override)
    cenarios = pj.CENARIOS if cenario == "todos" else (cast(pj.NomeCenario, cenario),)
    referencia: pj.NomeCenario = "base" if cenario == "todos" else cenarios[0]
    try:
        settings = carregar_settings()
        base = dt.date.fromisoformat(data_base) if data_base else settings.resolver_data_base(hoje)
        efetivo = reg.resolver_perfil(CAMINHO_PERFIL, hoje, override)
        parametros = parametros_do_perfil(efetivo.perfil, settings.perfil)
        p = _padronizar(ticker, settings)
        historico, _, sugestoes = _sugerir(p, settings, base)
        horizonte, origem = _horizonte(p.premissas, settings, hoje, override)
        resolvidas = _resolver(p, settings, sugestoes, base, horizonte)
        deltas = pj.resolver_cenarios(p.premissas.cenarios, sugestoes)
        m = _mercado(ticker, settings, base, agora, forcar)
        cc = _custo_capital(p, m, settings, base)
        dados = _dados_avaliacao(p, m, cc, settings, base, historico)
        ronic = _ronic(p, settings, historico)
        normalizado = cad.normalizar_ticker(ticker)
        preco = (m.precos.get(normalizado) or next(iter(m.precos.values()))).valor
        r = cen.analisar(
            resolvidas,
            deltas,
            dados,
            custo_capital=cc,
            ronic=ronic,
            perfil=parametros,
            preco=preco,
            selic=m.macro.selic.valor,
            cenarios=cenarios,
        )
        ref = r.avaliacoes[referencia].premissas
        s = settings.sensibilidade
        wacc_g = sens.wacc_x_g(
            ref,
            dados,
            wacc=cc.wacc,
            ronic=ronic,
            passo_wacc=s.wacc_passo,
            faixa_wacc=s.wacc_faixa,
            passo_g=s.g_passo,
            faixa_g=s.g_faixa,
        )
        margem_g = sens.margem_x_crescimento(
            ref,
            dados,
            wacc=cc.wacc,
            ronic=ronic,
            passo_margem=s.margem_passo,
            faixa_margem=s.margem_faixa,
            passo_crescimento=s.crescimento_passo,
            faixa_crescimento=s.crescimento_faixa,
        )
    except ValueError as e:
        raise _erro(f"--data-base inválida: {e}") from e
    except (
        ErroConfiguracao,
        ErroDownload,
        cad.ErroCadastro,
        ErroDadosExternos,
        ErroContabil,
        ErroPerfil,
        ErroProjecao,
        ErroCustoCapital,
        ErroModelo,
    ) as e:
        raise _erro(str(e)) from e

    moeda = f"{p.moeda}" + ("" if p.moeda == "BRL" else f" convertido a {m.macro.cambio.valor:.4f}")
    _mostrar_valuation(
        r,
        cc,
        settings,
        f"DCF — {p.premissas.ticker} em {base} ({moeda}; R$ milhões; {horizonte} anos pelo "
        f"{origem})",
    )
    _mostrar_projecao(
        r.avaliacoes[referencia].projecao,
        f"Projeção {referencia} — {p.premissas.ticker} (R$ milhões, {p.moeda})",
    )
    tabela = Table(title=f"Sensibilidade WACC x g — valor por ação ({referencia})")
    tabela.add_column("WACC \\ g")
    for g in wacc_g.columns:
        tabela.add_column(_taxa(cast(float, g)), justify="right")
    for w, linha in wacc_g.iterrows():
        tabela.add_row(_taxa(cast(float, w)), *(_reais(v) for v in linha))
    console.print(tabela)

    raiz = (Path(saida) if saida else DIR_SAIDA) / p.premissas.ticker / base.isoformat()
    fmt = cast(FormatoCsv, formato_csv)
    gravar_csv(wc.tabela(cc), raiz / "wacc.csv", settings.csv, fmt)
    for c, av in r.avaliacoes.items():
        gravar_csv(dcf.tabela(av), raiz / f"projecao_{c}.csv", settings.csv, fmt)
    ponte_df = pd.concat(
        {c: pt.tabela(av.ponte).set_index("item")["valor"] for c, av in r.avaliacoes.items()},
        axis=1,
    ).reset_index()
    gravar_csv(ponte_df, raiz / "ponte_ev_equity.csv", settings.csv, fmt)
    gravar_matriz(wacc_g, raiz / "sensibilidade_wacc_g.csv", settings.csv, fmt)
    gravar_matriz(margem_g, raiz / "sensibilidade_margem_crescimento.csv", settings.csv, fmt)
    avisos = [*r.avisos, *cc.avisos, *m.avisos, *sugestoes.avisos]
    resumo = _resumo(p.premissas.ticker, base, efetivo, p.moeda, cc, r, referencia, avisos)
    gravar_csv(resumo, raiz / "resumo.csv", settings.csv, fmt)

    for aviso in avisos:
        console.print(f"[yellow]Aviso:[/] {aviso}")
    console.print(cen.mensagem(r, normalizado))
    console.print("Estudo pessoal; não é recomendação de investimento.")
    console.print(f"Gravado em {raiz}")


if __name__ == "__main__":  # pragma: no cover
    app()
