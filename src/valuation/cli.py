"""Interface de linha de comando (`valuation`)."""

from __future__ import annotations

import datetime as dt
import logging
import platform
from dataclasses import dataclass, replace
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
from valuation.contabil import financeiras as fin
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
from valuation.modelos import ErroModelo, dcf, ddm
from valuation.modelos import multiplos as mt
from valuation.modelos import ponte as pt
from valuation.perfil import ErroPerfil, NomePerfil
from valuation.perfil import registro as reg
from valuation.perfil.parametros import parametros_do_perfil
from valuation.perfil.questionario import QUESTIONARIO
from valuation.projecao import ErroProjecao
from valuation.projecao import escrita as esc
from valuation.projecao import financeira as pf
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
    com_pares: bool = typer.Option(
        False, "--com-pares", help="Inclui os pares de cada ticker (YAML da empresa e setores)."
    ),
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
        if com_pares:
            for par in dict.fromkeys(x for t in lista for x in _pares_do_yaml(t)):
                try:
                    e = cad.empresa_por_ticker(cadastro, par)
                except cad.ErroCadastro as erro:
                    console.print(f"[yellow]Aviso:[/] par {par} ignorado: {erro}")
                    continue
                empresas.setdefault(e.cnpj, e)
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
    precos, cap = _cotacoes(empresa, settings, base, yf, brapi)
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
    return _Mercado(empresa, precos, ibov, macro, cap, yf)


def _cotacoes(
    empresa: cad.Empresa,
    settings: Settings,
    base: dt.date,
    yf: prc.PrecosProvider,
    brapi: prc.PrecosProvider,
) -> tuple[dict[str, Validado], prc.MarketCap]:
    """Preço de cada classe (2 fontes) e market cap na data-base."""
    precos: dict[str, Validado] = {}
    for classe in empresa.classes:
        try:
            precos[classe.ticker] = prc.preco_validado(
                classe.ticker, base, yf, brapi, tolerancia_rel=settings.validacao_cruzada.preco_rel
            )
        except ErroDadosExternos as e:
            console.print(f"[yellow]Aviso:[/] {classe.ticker} sem preço: {e}")
    if not precos:
        raise ErroDadosExternos(f"Nenhum preço disponível para {', '.join(empresa.tickers)}.")
    try:
        composicao = pd.read_parquet(
            DIR_PROCESSED / "cvm" / str(empresa.cd_cvm) / "composicao_capital.parquet"
        )
    except FileNotFoundError as e:
        raise ErroDadosExternos(
            f"{e.filename} não existe. Rode `valuation atualizar --tickers {empresa.tickers[0]}`."
        ) from e
    cap = prc.market_cap(empresa, composicao, {t: p.valor for t, p in precos.items()}, base)
    return precos, cap


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


def _padronizar(
    ticker: str, settings: Settings, cadastro: pd.DataFrame | None = None
) -> _Padronizada:
    """Padroniza as demonstrações de `ticker` e grava `contas_padronizadas.parquet`.

    Usa `config/empresas/{TICKER}.yaml` se existir (mapeamento extra, consolidado, moeda); senão,
    as premissas padrão. `cadastro` evita remontar o cadastro (pares).
    """
    if cadastro is None:
        data_base = settings.resolver_data_base(dt.date.today())
        cadastro = _carregar_cadastro(settings, data_base, False)
    empresa = cad.empresa_por_ticker(cadastro, ticker)
    tipo = empresa.tipo_modelo
    if tipo not in ("nao_financeira", "financeira"):
        raise ErroContabil(
            f"{', '.join(empresa.tickers)} é {tipo}: a v1 não avalia esse tipo "
            "(holdings exigem NAV/SOTP; ver seção 1 do CLAUDE.md)."
        )
    normalizado = cad.normalizar_ticker(ticker)
    caminho = pm.caminho_premissas(normalizado, DIR_EMPRESAS)
    if caminho.is_file():
        premissas = pm.carregar_premissas(caminho)
        pm.conferir_cadastro(premissas, empresa.tickers, tipo)
    else:
        premissas = pm.premissas_padrao(normalizado, tipo, empresa.tickers)
    plano = pad.carregar_mapeamento(tipo=tipo, extra=premissas.ajustes.mapeamento_extra)
    try:
        demonstracoes = pad.ler_demonstracoes(DIR_PROCESSED, empresa.cd_cvm)
    except FileNotFoundError as e:
        raise ErroContabil(
            f"{e.filename} não existe. Rode `valuation atualizar --tickers {ticker}`."
        ) from e
    consolidado = premissas.ajustes.consolidado
    if consolidado and not demonstracoes["consolidado"].any():
        console.print(
            f"[yellow]Aviso:[/] {normalizado} só publica demonstrações individuais: usadas no "
            "lugar das consolidadas."
        )
        consolidado = False
    selecionadas = pad.selecionar_reapresentacoes(demonstracoes, consolidado=consolidado)
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
_LINHAS_HISTORICO_FINANCEIRA = (
    ("receitas", "Receitas (3.01)", "mi"),
    ("resultado_bruto", "Resultado bruto (3.03)", "mi"),
    ("lucro_liquido", "Lucro líquido", "mi"),
    ("lucro_liquido_controladora", "Lucro controladora", "mi"),
    ("aliquota_efetiva", "Alíquota efetiva", "%"),
    ("patrimonio_liquido", "PL controladora", "mi"),
    ("roe", "ROE (PL inicial)", "%"),
    ("dividendos_pagos", "Dividendos pagos", "mi"),
    ("payout", "Payout", "%"),
    ("ativo_total", "Ativo total", "mi"),
    ("alavancagem", "Ativo / PL", "x"),
    ("roa", "ROA", "%"),
)


def _formatar(valor: float, unidade: str) -> str:
    if pd.isna(valor):
        return "—"
    if unidade == "%":
        return f"{valor:.1%}".replace(".", ",")
    if unidade == "x":
        return f"{valor:.1f}x".replace(".", ",")
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
        financeira = p.plano.tipo == "financeira"
        linhas = _LINHAS_HISTORICO_FINANCEIRA if financeira else _LINHAS_HISTORICO
        if trimestral and financeira:
            tabela_m = (
                per.trimestral(p.contas)
                .tail(8)
                .reindex(columns=["lucro_liquido_controladora", "dividendos_pagos"])
            )
            tabela_m["dividendos_pagos"] = -tabela_m["dividendos_pagos"]
            colunas = [f"{d.month // 3}T{d:%y}" for d in tabela_m.index]
        elif financeira:
            m = fin.metricas(per.anual(p.contas)).tail(anos)
            ltm = fin.metricas_ltm(p.contas)
            tabela_m = pd.concat([m, ltm.to_frame().T])
            colunas = [*map(str, m.index), f"LTM {pd.Timestamp(str(ltm.name)):%m/%Y}"]
        elif trimestral:
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
    for chave, rotulo, unidade in linhas:
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
        celulas = [
            "—" if pd.isna(f) else f"[{'green' if f >= 0.95 else 'red'}]{f:.0%}[/]" for f in linha
        ]
        tabela.add_row(str(conta), *celulas)
    console.print(tabela)
    console.print(f"Média geral: {pd.Series(matriz.to_numpy().ravel()).mean():.1%}")
    if matriz.isna().to_numpy().any():
        console.print("— = conta crítica de outro plano (financeira x não financeira).")


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
    limite = p.premissas.projecao_dcf.aliquota_imposto.limite_superior
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
        g_terminal=pj.g_terminal(p.premissas.projecao_dcf.terminal, settings.terminal),
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
        p.premissas.projecao_dcf,
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
            _no_yaml(p.premissas.projecao_dcf, coluna),
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
        if p.plano.tipo == "financeira":
            _premissas_sugerir_financeira(p, settings, base, hoje, override, escrever)
            return
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

    _escrever_premissas(p, esc.renderizar(p.premissas, sugestoes, data_base=base), escrever)


def _escrever_premissas(p: _Padronizada, texto: str, escrever: bool) -> None:
    """Grava o YAML da empresa (o anterior vira .bak) ou avisa que ele não existe."""
    if escrever:
        caminho = p.caminho_premissas
        if caminho.is_file():
            caminho.replace(caminho.with_suffix(".yaml.bak"))
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(texto, encoding="utf-8")
        console.print(f"Gravado em {caminho}")
    elif not p.caminho_premissas.is_file():
        console.print(f"{p.caminho_premissas} não existe; use --escrever para criá-lo.")


def _sugerir_financeira(
    p: _Padronizada, settings: Settings, base: dt.date
) -> tuple[pd.DataFrame, pf.SugestoesFinanceira]:
    """Métricas dos exercícios encerrados antes da data-base e premissas do DDM sugeridas."""
    historico = fin.metricas(per.anual(p.contas))
    historico = historico[historico.index < pj.primeiro_ano_aberto(base)]
    g = pj.g_terminal(p.premissas.projecao_ddm.terminal, settings.terminal)
    return historico, pf.sugerir(historico, g_terminal=g)


def _pl_inicial(p: _Padronizada, base: dt.date) -> tuple[float, dt.date]:
    """PL da controladora no último balanço até a data-base (ponto de partida do DDM)."""
    data = _data_balanco(p.contas, base)
    bal = cast(pd.Series, per.saldos(p.contas).loc[data])
    minoritarios = float(cast(float, bal.get("minoritarios", 0.0)))
    pl = float(cast(float, bal["patrimonio_liquido_total"]))
    return pl - (0.0 if pd.isna(minoritarios) else minoritarios), data.date()


def _mostrar_sugestoes_financeira(p: _Padronizada, s: pf.SugestoesFinanceira) -> None:
    def e(linha: str, coluna: str) -> str:
        return sg.pct(cast(float, s.estatisticas.at[linha, coluna]))

    pr = p.premissas.projecao_ddm
    tabela = Table(
        title=f"Premissas sugeridas x histórico — {p.premissas.ticker} (DDM, até {s.ano_base})"
    )
    for coluna in ("Premissa", str(s.ano_base), "Mediana 5a", "Mediana 10a", "Sugerido", "No YAML"):
        tabela.add_column(coluna, justify="left" if coluna in ("Premissa", "No YAML") else "right")
    roe_yaml = (
        "lista: " + ", ".join(sg.pct(x) for x in pr.roe)
        if isinstance(pr.roe, tuple)
        else " → ".join(
            str(x) if x == pm.SUGERIDO else sg.pct(float(x)) for x in (pr.roe.inicio, pr.roe.fim)
        )
    )
    payout_yaml = (
        str(pr.payout_inicio)
        if pr.payout_inicio == pm.SUGERIDO
        else sg.pct(float(pr.payout_inicio))
    )
    tabela.add_row(
        "ROE (início → longo prazo)",
        e("ultimo", "roe"),
        e("mediana_5a", "roe"),
        e("mediana_10a", "roe"),
        f"{sg.pct(s.roe_inicio.valor)} → {sg.pct(s.roe_fim.valor)}",
        roe_yaml,
    )
    tabela.add_row(
        "Payout inicial",
        e("ultimo", "payout"),
        e("mediana_5a", "payout"),
        e("mediana_10a", "payout"),
        sg.pct(s.payout_inicio.valor),
        payout_yaml,
    )
    console.print(tabela)
    g = s.g_terminal.valor
    final = sg.pct(pf.payout_final(s.roe_fim.valor, g)) if s.roe_fim.valor > g else "—"
    console.print(
        f"g terminal {sg.pct(g)} ({s.g_terminal.origem}); payout de longo prazo sugerido "
        f"1 - g / ROE = {final}. Delta dos cenários: ROE ±{sg.pp(s.delta_roe.valor)} "
        "(pessimista -)."
    )


_LINHAS_PROJECAO_FINANCEIRA = (
    ("fracao", "Fração do ano por vir", "%"),
    ("roe", "ROE", "%"),
    ("payout", "Payout", "%"),
    ("pl_inicial", "PL inicial", "mi"),
    ("lucro", "Lucro (parte por vir)", "mi"),
    ("dividendos", "Dividendos", "mi"),
    ("pl_final", "PL final", "mi"),
)


def _mostrar_projecao_financeira(tabela_p: pd.DataFrame, titulo: str) -> None:
    tabela = Table(title=titulo)
    tabela.add_column("Métrica")
    for ano in tabela_p.index:
        tabela.add_column(str(ano), justify="right")
    for chave, rotulo, unidade in _LINHAS_PROJECAO_FINANCEIRA:
        tabela.add_row(rotulo, *(_formatar(v, unidade) for v in tabela_p[chave]))
    console.print(tabela)


def _premissas_sugerir_financeira(
    p: _Padronizada,
    settings: Settings,
    base: dt.date,
    hoje: dt.date,
    override: NomePerfil | None,
    escrever: bool,
) -> None:
    """`premissas sugerir` de uma financeira: ROE e payout x histórico e a projeção do DDM."""
    _, sugestoes = _sugerir_financeira(p, settings, base)
    _mostrar_sugestoes_financeira(p, sugestoes)
    if p.premissas.pares.setor is None:
        console.print("[yellow]Aviso:[/] pares.setor não definido no YAML.")
    try:
        horizonte, origem = _horizonte(p.premissas, settings, hoje, override)
    except ErroPerfil as e:
        console.print(f"[yellow]Projeção não mostrada:[/] {e}")
    else:
        resolvidas = pf.resolver(
            p.premissas.projecao_ddm, sugestoes, anos=pf.anos_projetados(base, horizonte)
        )
        pl, data = _pl_inicial(p, base)
        _mostrar_projecao_financeira(
            pf.projetar(pl, resolvidas, data_base=base),
            f"Projeção base (DDM) — {p.premissas.ticker} (R$ milhões; PL da controladora em "
            f"{data}; data-base {base}; {horizonte} anos pelo {origem})",
        )
    for aviso in sugestoes.avisos:
        console.print(f"[yellow]Aviso:[/] {aviso}")
    texto = esc.renderizar_financeira(p.premissas, sugestoes, data_base=base)
    _escrever_premissas(p, texto, escrever)


# Prazo do ITR é de 45 dias após o trimestre: até ~140 dias de defasagem é o normal.
DEFASAGEM_AVISO_DIAS = 140


def _data_balanco(contas: pd.DataFrame, base: dt.date) -> pd.Timestamp:
    """Última data até a data-base com fluxos acumulados e balanço (ponto do LTM)."""
    comuns = per.acumulado_no_ano(contas).index.intersection(per.saldos(contas).index)
    comuns = comuns[comuns <= pd.Timestamp(base)]
    if comuns.empty:
        raise ErroContabil(f"Nenhuma demonstração até {base}.")
    return pd.Timestamp(comuns.max())


def _tickers_pares(premissas: pm.PremissasEmpresa, proprios: tuple[str, ...]) -> list[str]:
    """Pares do setor + `pares.incluir` - `pares.excluir`, sem as classes da própria empresa."""
    setor = _setor(premissas.pares.setor)
    candidatos = [*(setor.pares if setor else ()), *premissas.pares.incluir]
    fora = {cad.normalizar_ticker(t) for t in (*premissas.pares.excluir, *proprios)}
    unicos = dict.fromkeys(cad.normalizar_ticker(t) for t in candidatos)
    return [t for t in unicos if t not in fora]


def _pares_do_yaml(ticker: str) -> list[str]:
    """Pares de `ticker` pelo YAML da empresa (sem YAML, nenhum)."""
    normalizado = cad.normalizar_ticker(ticker)
    caminho = pm.caminho_premissas(normalizado, DIR_EMPRESAS)
    if not caminho.is_file():
        return []
    return _tickers_pares(pm.carregar_premissas(caminho), (normalizado,))


@dataclass(frozen=True)
class _Par:
    padronizada: _Padronizada
    cap: prc.MarketCap
    fundamentos: mt.Fundamentos


@dataclass(frozen=True)
class _Comparaveis:
    pares: tuple[_Par, ...]
    avisos: tuple[str, ...]


def _fundamentos(
    p: _Padronizada, cap: prc.MarketCap, settings: Settings, base: dt.date, dolar: float
) -> mt.Fundamentos:
    """Métricas LTM no último balanço até a data-base e market cap, em BRL."""
    data_bal = _data_balanco(p.contas, base)
    ltm = nf.metricas_ltm(
        p.contas,
        aliquota_nominal=settings.impostos.aliquota_nominal,
        dt_fim=data_bal,
        ajustes=p.ajustes,
    )
    itens = pt.itens_do_balanco(
        ltm,
        acoes=sum(c.acoes for c in cap.classes),
        data_balanco=data_bal.date(),
        coligadas=p.premissas.ajustes.coligadas,
        minoritarios="contabil",
    )
    cambio = 1.0 if p.moeda == "BRL" else dolar
    return mt.fundamentos(p.premissas.ticker, ltm, itens=itens, market_cap=cap.valor, cambio=cambio)


def _mercado_par(
    ticker: str,
    settings: Settings,
    base: dt.date,
    cadastro: pd.DataFrame,
    yf: prc.PrecosProvider,
    brapi: prc.PrecosProvider,
) -> prc.MarketCap:
    """Market cap de um par na data-base (sem macro nem Ibovespa)."""
    return _cotacoes(cad.empresa_por_ticker(cadastro, ticker), settings, base, yf, brapi)[1]


def _coletar_pares(p: _Padronizada, m: _Mercado, settings: Settings, base: dt.date) -> _Comparaveis:
    """Padroniza cada par e mede-o como o alvo; par sem dados vira aviso, não erro."""
    tickers = _tickers_pares(p.premissas, p.empresa.tickers)
    if not tickers:
        return _Comparaveis(
            (),
            (
                f"{p.premissas.ticker} sem pares: defina pares.setor (com pares em "
                f"{CAMINHO_SETORES.name}) ou pares.incluir no YAML da empresa.",
            ),
        )
    cadastro = _carregar_cadastro(settings, base, False)
    brapi = prc.BrapiProvider(criar_sessao())
    vistos = {p.empresa.cnpj}
    pares: list[_Par] = []
    avisos: list[str] = []
    for t in tickers:
        try:
            par = _padronizar(t, settings, cadastro)
            if par.empresa.cnpj in vistos:
                continue
            vistos.add(par.empresa.cnpj)
            cap = _mercado_par(t, settings, base, cadastro, m.yf, brapi)
            f = _fundamentos(par, cap, settings, base, m.macro.cambio.valor)
        except (
            ErroConfiguracao,
            ErroDownload,
            cad.ErroCadastro,
            ErroDadosExternos,
            ErroContabil,
            ErroModelo,
        ) as e:
            avisos.append(f"Par {t} ignorado: {e}")
            continue
        pares.append(_Par(par, cap, f))
    return _Comparaveis(tuple(pares), tuple(avisos))


def _multiplos(
    p: _Padronizada, m: _Mercado, comps: _Comparaveis, settings: Settings, base: dt.date
) -> mt.ResultadoMultiplos | None:
    """Múltiplos dos pares e valores implícitos do alvo; None se nenhum par foi medido."""
    if not comps.pares:
        return None
    alvo = _fundamentos(p, m.cap, settings, base, m.macro.cambio.valor)
    cfg = settings.multiplos
    return mt.avaliar(
        alvo,
        [x.fundamentos for x in comps.pares],
        inferior=cfg.winsorizar.inferior,
        superior=cfg.winsorizar.superior,
        min_pares=cfg.min_pares,
    )


def _metodo_beta(p: _Padronizada, settings: Settings) -> str:
    empresa = p.premissas.custo_capital
    return (
        empresa.beta.metodo
        if "beta" in empresa.model_fields_set
        else settings.custo_capital.beta.metodo
    )


def _precisa_pares(p: _Padronizada, settings: Settings) -> bool:
    """Custo de capital ou ponte dependem dos pares (beta, estrutura ou minoritários)?"""
    return (
        _metodo_beta(p, settings) == "comparaveis"
        or settings.custo_capital.estrutura_alvo.metodo == "setor"
        or p.premissas.ajustes.minoritarios == "multiplo_pvp"
    )


def _regressao(
    tickers: list[str], yf: prc.PrecosProvider, settings: Settings, base: dt.date
) -> bt.ResultadoBeta:
    """Beta da classe mais líquida contra o Ibovespa."""
    cfg = settings.custo_capital.beta
    inicio = base - dt.timedelta(weeks=cfg.janela_semanas + 2)
    historicos = {t: yf.historico(prc.simbolo_yahoo(t), inicio, base) for t in tickers}
    ticker = bt.classe_mais_liquida(historicos, base, cfg.janela_semanas)
    ibov = yf.historico("^BVSP", inicio, base)
    return bt.regressao(
        historicos[ticker]["adj_close"],
        ibov["adj_close"],
        data_base=base,
        janela_semanas=cfg.janela_semanas,
        ajuste_blume=cfg.ajuste_blume,
        min_r2_aviso=cfg.min_r2_aviso,
        ticker=ticker,
    )


def _beta(
    p: _Padronizada,
    m: _Mercado,
    settings: Settings,
    base: dt.date,
    aliquota: float,
    est: wc.Estrutura,
    pares: tuple[_Par, ...],
) -> bt.ResultadoBeta:
    """Beta pelo método do YAML da empresa (se declarado) ou do `settings`.

    Comparáveis: beta de cada par (regressão, com Blume se configurado) e D/E dele, mediana
    desalavancada e realavancada na estrutura `est` do alvo.
    """
    empresa = p.premissas.custo_capital
    metodo = _metodo_beta(p, settings)
    if metodo == "manual":
        if empresa.beta.valor is None:
            raise ErroConfiguracao("beta manual exige custo_capital.beta.valor no YAML da empresa.")
        return bt.manual(empresa.beta.valor)
    if metodo == "comparaveis":
        betas: dict[str, tuple[float, float]] = {}
        avisos: list[str] = []
        for par in pares:
            f = par.fundamentos
            try:
                r = _regressao([c.ticker for c in par.cap.classes], m.yf, settings, base)
            except (ErroCustoCapital, ErroDadosExternos) as e:
                avisos.append(f"Beta de {f.ticker} ignorado: {e}")
                continue
            betas[f.ticker] = (r.beta, f.itens.divida_bruta / f.market_cap)
        resultado = bt.comparaveis(
            betas, divida_sobre_equity_alvo=est.divida_sobre_equity, aliquota=aliquota
        )
        return replace(resultado, avisos=(*resultado.avisos, *avisos))
    return _regressao(list(m.precos), m.yf, settings, base)


def _divida_sobre_capital_setor(pares: tuple[_Par, ...]) -> float:
    """Mediana de D/(D+E) dos pares (dívida bruta contábil, market cap)."""
    if not pares:
        raise ErroCustoCapital(
            "estrutura_alvo.metodo = setor sem pares medidos: confira os pares e rode "
            "`valuation atualizar --tickers ... --com-pares`."
        )
    pesos = [
        x.fundamentos.itens.divida_bruta
        / (x.fundamentos.itens.divida_bruta + x.fundamentos.market_cap)
        for x in pares
    ]
    return float(pd.Series(pesos).median())


def _custo_capital(
    p: _Padronizada,
    m: _Mercado,
    settings: Settings,
    base: dt.date,
    comps: _Comparaveis | None = None,
) -> wc.CustoCapital:
    """Beta, Ke, Kd, estrutura e WACC na moeda de reporte da empresa.

    `comps` (pares medidos) é exigido pelo beta por comparáveis e pela estrutura do setor.
    """
    cfg = settings.custo_capital
    aliquota = settings.impostos.aliquota_nominal
    moeda = cast(capm.Moeda, p.moeda)
    data_bal = _data_balanco(p.contas, base)
    avisos = _aviso_defasagem(data_bal, base)
    ltm = nf.metricas_ltm(p.contas, aliquota_nominal=aliquota, dt_fim=data_bal, ajustes=p.ajustes)
    equity = m.cap.valor if moeda == "BRL" else m.cap.valor / m.macro.cambio.valor
    pares = comps.pares if comps else ()
    alvo_dc = (
        _divida_sobre_capital_setor(pares)
        if cfg.estrutura_alvo.metodo == "setor"
        else cfg.estrutura_alvo.divida_sobre_capital
    )
    est = wc.estrutura(
        metodo=cfg.estrutura_alvo.metodo,
        divida=float(ltm["divida_bruta"]),
        equity=equity,
        divida_sobre_capital_alvo=alvo_dc,
    )

    beta_bruto = _beta(p, m, settings, base, aliquota, est, pares)
    beta = wc.beta_na_estrutura(beta_bruto, est, aliquota)
    ke = _ke(moeda, beta.beta, m, settings, avisos)

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
    g = pj.g_terminal(p.premissas.projecao_dcf.terminal, settings.terminal)
    wc.validar_g(cc.wacc, g.valor)
    return cc


def _aviso_defasagem(data_bal: pd.Timestamp, base: dt.date) -> list[str]:
    defasagem = (base - data_bal.date()).days
    if defasagem > DEFASAGEM_AVISO_DIAS:
        return [f"Balanço de {data_bal.date()} ({defasagem} dias antes da data-base)."]
    return []


def _ke(
    moeda: capm.Moeda, beta: float, m: _Mercado, settings: Settings, avisos: list[str]
) -> capm.CustoCapitalProprio:
    """Ke pelo método do settings (empresa em USD usa `usd_crp`; o aviso vai para `avisos`)."""
    cfg = settings.custo_capital
    metodo, aviso = capm.metodo_efetivo(cfg.metodo, moeda)
    if aviso:
        avisos.append(aviso)
    inflacao_brl = (
        m.macro.ipca_esperado[max(m.macro.ipca_esperado)] if m.macro.ipca_esperado else None
    )
    return capm.custo_capital_proprio(
        metodo=metodo,
        moeda=moeda,
        beta=beta,
        erp=cfg.erp,
        rf_brl=m.macro.rf_brl.valor,
        rf_usd=cfg.rf_usd,
        crp=cfg.crp,
        inflacao_usd=cfg.inflacao_usd_lp,
        inflacao_brl=inflacao_brl,
    )


def _custo_capital_financeira(
    p: _Padronizada,
    m: _Mercado,
    settings: Settings,
    base: dt.date,
    comps: _Comparaveis | None = None,
) -> wc.CustoCapitalFinanceira:
    """Beta e Ke de uma financeira (sem Kd, estrutura nem WACC; seção 10.4).

    Beta por comparáveis = mediana dos betas dos pares, sem Hamada (dívida de banco é operação).
    """
    moeda = cast(capm.Moeda, p.moeda)
    data_bal = _data_balanco(p.contas, base)
    avisos = _aviso_defasagem(data_bal, base)
    sem_divida = wc.estrutura(metodo="mercado_atual", divida=0.0, equity=m.cap.valor)
    aliquota = settings.impostos.aliquota_nominal
    beta = _beta(p, m, settings, base, aliquota, sem_divida, comps.pares if comps else ())
    ke = _ke(moeda, beta.beta, m, settings, avisos)
    g = pj.g_terminal(p.premissas.projecao_ddm.terminal, settings.terminal)
    wc.validar_g(ke.ke, g.valor, "Ke")
    return wc.montar_financeira(
        data_base=base, beta=beta, ke=ke, data_balanco=data_bal.date(), avisos=tuple(avisos)
    )


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
        comps = _coletar_pares(p, m, settings, base) if _precisa_pares(p, settings) else None
        if p.plano.tipo == "financeira":
            cc_fin = _custo_capital_financeira(p, m, settings, base, comps)
            tab, moeda_ke, avisos_cc = wc.tabela_financeira(cc_fin), cc_fin.ke.moeda, cc_fin.avisos
        else:
            cc = _custo_capital(p, m, settings, base, comps)
            tab, moeda_ke, avisos_cc = wc.tabela(cc), cc.ke.moeda, cc.avisos
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

    tabela = Table(title=f"Custo de capital — {p.premissas.ticker} em {base} ({moeda_ke})")
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
    for aviso in [*avisos_cc, *(comps.avisos if comps else ()), *m.avisos]:
        console.print(f"[yellow]Aviso:[/] {aviso}")
    console.print(f"Gravado em {caminho}")


def _dados_avaliacao(
    p: _Padronizada,
    m: _Mercado,
    cc: wc.CustoCapital,
    settings: Settings,
    base: dt.date,
    historico: pd.DataFrame,
    pvp_pares: float | None = None,
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
        pvp_pares=pvp_pares,
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
    escolha = p.premissas.projecao_dcf.terminal.ronic
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
    r: cen.ResultadoCenarios[dcf.Avaliacao],
    referencia: pj.NomeCenario,
    multiplos: mt.ResultadoMultiplos | None,
    g_saida: float | None,
    avisos: list[str],
) -> pd.DataFrame:
    """Linha única de `resumo.csv` (seção 13 do CLAUDE.md)."""
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
        "ev_ebitda_pares": multiplos.mediana("ev_ebitda") if multiplos else None,
        "g_implicito_saida": g_saida,
        "n_pares": float(len(multiplos.pares)) if multiplos else None,
        **{
            f"valor_{n}": multiplos.implicitos.loc[n, "valor_mediana"] if multiplos else None
            for n in mt.MULTIPLOS
        },
        "data_balanco": cc.data_balanco.isoformat(),
        "avisos": " | ".join(avisos),
    }
    df = pd.DataFrame([linha])
    numericas = [c for c, v in linha.items() if v is None or isinstance(v, float | int)]
    df[numericas] = df[numericas].astype("float64")
    return df


def _mostrar_valuation(
    r: cen.ResultadoCenarios[dcf.Avaliacao],
    cc: wc.CustoCapital,
    settings: Settings,
    titulo: str,
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


def _multiplo_fmt(nome: mt.NomeMultiplo, valor: float) -> str:
    if pd.isna(valor):
        return "—"
    if nome == "dividend_yield":
        return f"{valor:.1%}".replace(".", ",")
    return f"{valor:.1f}x".replace(".", ",")


def _mostrar_pares(r: mt.ResultadoMultiplos) -> None:
    tabela = Table(title=f"Múltiplos LTM — {r.alvo.ticker} e pares")
    tabela.add_column("Ticker")
    tabela.add_column("Balanço")
    tabela.add_column("Market cap (R$ mi)", justify="right")
    for nome in mt.MULTIPLOS:
        tabela.add_column(mt.ROTULOS[nome], justify="right")
    todos = pd.concat([mt.tabela_pares([r.alvo]), r.pares])
    for ticker, linha in todos.iterrows():
        rotulo = f"[bold]{ticker}[/]" if ticker == r.alvo.ticker else str(ticker)
        tabela.add_row(
            rotulo,
            str(linha["data_balanco"]),
            _formatar(float(linha["market_cap"]), "mi"),
            *(_multiplo_fmt(n, float(linha[n])) for n in mt.MULTIPLOS),
        )
    console.print(tabela)


def _mostrar_implicitos(r: mt.ResultadoMultiplos, preco: float) -> None:
    tabela = Table(title=f"Valor implícito por múltiplo — {r.alvo.ticker} (R$/ação; pares P25-P75)")
    for coluna in (
        "Múltiplo",
        "Pares",
        "P25",
        "Mediana",
        "P75",
        "Alvo",
        "Valor P25-P75",
        "Mediana",
    ):
        tabela.add_column(coluna, justify="left" if coluna == "Múltiplo" else "right")
    impl = r.implicitos
    for nome in mt.MULTIPLOS:

        def x(coluna: str, nome: mt.NomeMultiplo = nome) -> float:
            return mt.celula(impl, nome, coluna)

        n = f"{x('n_pares'):.0f}" + (" (baixa)" if impl.at[nome, "confianca"] == "baixa" else "")
        faixa = sorted((x("valor_p25"), x("valor_p75")))
        tabela.add_row(
            mt.ROTULOS[nome],
            n,
            *(_multiplo_fmt(nome, x(f"multiplo_{s}")) for s in mt.ESTATISTICAS),
            _multiplo_fmt(nome, x("multiplo_alvo")),
            "—" if any(pd.isna(v) for v in faixa) else f"{_reais(faixa[0])} a {_reais(faixa[1])}",
            _reais(x("valor_mediana")),
        )
    console.print(tabela)
    console.print(f"Preço de mercado: {_reais(preco)}.")


def _gravar_multiplos(
    r: mt.ResultadoMultiplos, raiz: Path, settings: Settings, fmt: FormatoCsv
) -> None:
    """`multiplos_pares.csv` (alvo e pares) e `multiplos_implicitos.csv` (estatísticas)."""
    pares = pd.concat(
        [mt.tabela_pares([r.alvo]).assign(papel="alvo"), r.pares.assign(papel="par")]
    ).reset_index()
    gravar_csv(pares, raiz / "multiplos_pares.csv", settings.csv, fmt)
    estat = r.estatisticas.drop(columns=["n", "confianca"])
    implicitos = r.implicitos.join(estat).reset_index()
    gravar_csv(implicitos, raiz / "multiplos_implicitos.csv", settings.csv, fmt)


@app.command()
def comparar(
    ticker: str = typer.Argument(..., help="Ex.: PETR4."),
    data_base: str | None = typer.Option(
        None, "--data-base", help="AAAA-MM-DD (padrão: settings)."
    ),
    saida: str | None = typer.Option(
        None, "--saida", help="Diretório raiz da saída (padrão: saida/)."
    ),
    formato_csv: str = typer.Option("br", "--formato-csv", help="br | intl."),
    forcar: bool = typer.Option(False, "--forcar", help="Ignora o cache e consulta as APIs."),
) -> None:
    """Múltiplos LTM do alvo e dos pares e valores implícitos por múltiplo (sem DCF)."""
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
        comps = _coletar_pares(p, m, settings, base)
        r = _multiplos(p, m, comps, settings, base)
    except ValueError as e:
        raise _erro(f"--data-base inválida: {e}") from e
    except (
        ErroConfiguracao,
        ErroDownload,
        cad.ErroCadastro,
        ErroDadosExternos,
        ErroContabil,
        ErroModelo,
    ) as e:
        raise _erro(str(e)) from e
    for aviso in comps.avisos:
        console.print(f"[yellow]Aviso:[/] {aviso}")
    if r is None:
        raise _erro(f"Nenhum par de {p.premissas.ticker} pôde ser medido.")

    _mostrar_pares(r)
    preco = (m.precos.get(cad.normalizar_ticker(ticker)) or next(iter(m.precos.values()))).valor
    _mostrar_implicitos(r, preco)
    raiz = (Path(saida) if saida else DIR_SAIDA) / p.premissas.ticker / base.isoformat()
    _gravar_multiplos(r, raiz, settings, cast(FormatoCsv, formato_csv))
    for aviso in [*r.avisos, *m.avisos]:
        console.print(f"[yellow]Aviso:[/] {aviso}")
    console.print("Estudo pessoal; não é recomendação de investimento.")
    console.print(f"Gravado em {raiz}")


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
        if p.plano.tipo == "financeira":
            raiz = (Path(saida) if saida else DIR_SAIDA) / p.premissas.ticker / base.isoformat()
            execucao = _Execucao(base, hoje, agora, override, efetivo, cenarios, referencia, forcar)
            _rodar_financeira(p, settings, execucao, raiz, cast(FormatoCsv, formato_csv))
            return
        historico, _, sugestoes = _sugerir(p, settings, base)
        horizonte, origem = _horizonte(p.premissas, settings, hoje, override)
        resolvidas = _resolver(p, settings, sugestoes, base, horizonte)
        deltas = pj.resolver_cenarios(p.premissas.cenarios_dcf, sugestoes)
        m = _mercado(ticker, settings, base, agora, forcar)
        comps = _coletar_pares(p, m, settings, base)
        cc = _custo_capital(p, m, settings, base, comps)
        multiplos = _multiplos(p, m, comps, settings, base)
        pvp = multiplos.mediana("p_vp") if multiplos else None
        dados = _dados_avaliacao(p, m, cc, settings, base, historico, pvp)
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
        av_ref = r.avaliacoes[referencia]
        ref = av_ref.premissas
        ultimo = av_ref.projecao.iloc[-1]
        g_saida = (
            dcf.g_implicito(
                multiplos.mediana("ev_ebitda"),
                ebitda_t=float(ultimo["ebitda"]),
                nopat_t=float(ultimo["nopat"]),
                wacc=av_ref.dcf.wacc,
                ronic=ronic,
            )
            if multiplos
            else None
        )
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
    if settings.terminal.checagem_multiplo_saida and multiplos:
        implicito = (
            f"g de {_taxa(g_saida)}"
            if g_saida is not None
            else "nenhum g abaixo do WACC (múltiplo fora do alcance do terminal com esse RONIC)"
        )
        console.print(
            f"Múltiplo de saída: EV/EBITDA mediano dos pares "
            f"{_multiplo_fmt('ev_ebitda', multiplos.mediana('ev_ebitda'))} implica {implicito} "
            f"na perpetuidade ({referencia}; g usado {_taxa(av_ref.dcf.g)})."
        )
    _mostrar_projecao(
        av_ref.projecao,
        f"Projeção {referencia} — {p.premissas.ticker} (R$ milhões, {p.moeda})",
    )
    if multiplos:
        _mostrar_implicitos(multiplos, preco)
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
    if multiplos:
        _gravar_multiplos(multiplos, raiz, settings, fmt)
    avisos = [
        *r.avisos,
        *cc.avisos,
        *comps.avisos,
        *(multiplos.avisos if multiplos else ()),
        *m.avisos,
        *sugestoes.avisos,
    ]
    resumo = _resumo(
        p.premissas.ticker, base, efetivo, p.moeda, cc, r, referencia, multiplos, g_saida, avisos
    )
    gravar_csv(resumo, raiz / "resumo.csv", settings.csv, fmt)

    for aviso in avisos:
        console.print(f"[yellow]Aviso:[/] {aviso}")
    console.print(cen.mensagem(r, normalizado))
    console.print("Estudo pessoal; não é recomendação de investimento.")
    console.print(f"Gravado em {raiz}")


@dataclass(frozen=True)
class _Execucao:
    """Parâmetros de uma execução do `rodar` (datas, perfil e cenários)."""

    base: dt.date
    hoje: dt.date
    agora: dt.datetime
    override: NomePerfil | None
    efetivo: reg.PerfilEfetivo
    cenarios: tuple[pj.NomeCenario, ...]
    referencia: pj.NomeCenario
    forcar: bool


def _rodar_financeira(
    p: _Padronizada, settings: Settings, e: _Execucao, raiz: Path, fmt: FormatoCsv
) -> None:
    """`rodar` de uma financeira: DDM por cenário, Ke implícito e sensibilidades (seção 11.3)."""
    ticker = p.premissas.ticker
    try:
        parametros = parametros_do_perfil(e.efetivo.perfil, settings.perfil)
        _, sugestoes = _sugerir_financeira(p, settings, e.base)
        horizonte, origem = _horizonte(p.premissas, settings, e.hoje, e.override)
        anos = pf.anos_projetados(e.base, horizonte)
        resolvidas = pf.resolver(p.premissas.projecao_ddm, sugestoes, anos=anos)
        deltas = pf.resolver_cenarios(p.premissas.cenarios_ddm, sugestoes)
        m = _mercado(ticker, settings, e.base, e.agora, e.forcar)
        comps = _coletar_pares(p, m, settings, e.base) if _precisa_pares(p, settings) else None
        cc = _custo_capital_financeira(p, m, settings, e.base, comps)
        pl, data_bal = _pl_inicial(p, e.base)
        dados = ddm.DadosDDM(
            pl_inicial=pl,
            acoes=float(sum(c.acoes for c in m.cap.classes)),
            data_balanco=data_bal,
            data_base=e.base,
            alerta_vt_sobre_valor=settings.dcf.alerta_tv_sobre_ev,
        )
        preco = (m.precos.get(ticker) or next(iter(m.precos.values()))).valor
        r = cen.analisar_ddm(
            resolvidas,
            deltas,
            dados,
            ke=cc.ke.ke,
            perfil=parametros,
            preco=preco,
            selic=m.macro.selic.valor,
            cenarios=e.cenarios,
        )
        ref = r.avaliacoes[e.referencia].premissas
        s = settings.sensibilidade
        ke_g = sens.ke_x_g(
            ref,
            dados,
            ke=cc.ke.ke,
            passo_ke=s.wacc_passo,
            faixa_ke=s.wacc_faixa,
            passo_g=s.g_passo,
            faixa_g=s.g_faixa,
        )
        roe_ke = sens.roe_x_ke(
            ref,
            dados,
            ke=cc.ke.ke,
            passo_roe=s.roe_passo,
            faixa_roe=s.roe_faixa,
            passo_ke=s.wacc_passo,
            faixa_ke=s.wacc_faixa,
        )
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
    ) as erro:
        raise _erro(str(erro)) from erro

    _mostrar_valuation_ddm(
        r,
        cc,
        settings,
        e.referencia,
        f"DDM — {ticker} em {e.base} (R$ milhões; PL da controladora em {data_bal}; "
        f"{horizonte} anos pelo {origem})",
    )
    av_ref = r.avaliacoes[e.referencia]
    _mostrar_projecao_financeira(
        av_ref.projecao, f"Projeção {e.referencia} — {ticker} (R$ milhões)"
    )
    tabela = Table(title=f"Sensibilidade Ke x g — valor por ação ({e.referencia})")
    tabela.add_column("Ke \\ g")
    for g in ke_g.columns:
        tabela.add_column(_taxa(cast(float, g)), justify="right")
    for k, linha in ke_g.iterrows():
        tabela.add_row(_taxa(cast(float, k)), *(_reais(v) for v in linha))
    console.print(tabela)

    gravar_csv(wc.tabela_financeira(cc), raiz / "wacc.csv", settings.csv, fmt)
    for c, av in r.avaliacoes.items():
        gravar_csv(ddm.tabela(av), raiz / f"projecao_{c}.csv", settings.csv, fmt)
    gravar_matriz(ke_g, raiz / "sensibilidade_ke_g.csv", settings.csv, fmt)
    gravar_matriz(roe_ke, raiz / "sensibilidade_roe_ke.csv", settings.csv, fmt)
    avisos = [
        *r.avisos,
        *cc.avisos,
        *(comps.avisos if comps else ()),
        *m.avisos,
        *sugestoes.avisos,
    ]
    resumo = _resumo_financeira(ticker, e, cc, r, avisos)
    gravar_csv(resumo, raiz / "resumo.csv", settings.csv, fmt)
    for aviso in avisos:
        console.print(f"[yellow]Aviso:[/] {aviso}")
    console.print(cen.mensagem(r, ticker))
    console.print("Estudo pessoal; não é recomendação de investimento.")
    console.print(f"Gravado em {raiz}")


def _mostrar_valuation_ddm(
    r: cen.ResultadoCenarios[ddm.AvaliacaoDDM],
    cc: wc.CustoCapitalFinanceira,
    settings: Settings,
    referencia: pj.NomeCenario,
    titulo: str,
) -> None:
    tabela = Table(title=titulo)
    colunas = (
        "Cenário",
        "Peso",
        "VP dividendos",
        "VP terminal",
        "Valor (PL)",
        "VT/valor",
        "P/VP just.",
        "Lucro residual",
        "Valor por ação",
    )
    for coluna in colunas:
        tabela.add_column(coluna, justify="left" if coluna == "Cenário" else "right")
    for c, av in r.avaliacoes.items():
        d = av.ddm
        tabela.add_row(
            c,
            f"{r.pesos[c]:.0%}",
            _formatar(d.vp_dividendos, "mi"),
            _formatar(d.vp_terminal, "mi"),
            _formatar(d.valor, "mi"),
            _formatar(d.vt_sobre_valor, "%"),
            _formatar(d.pvp_justificado, "x"),
            _formatar(d.valor_lucro_residual, "mi"),
            _reais(av.valor_por_acao),
        )
    console.print(tabela)
    d = r.avaliacoes[referencia].ddm
    console.print(
        f"Checagens ({referencia}): Ke {_taxa(cc.ke.ke)} > g {_taxa(d.g)} (teto "
        f"{_taxa(settings.terminal.g_nominal_max)}); ROE de longo prazo "
        f"{_taxa(d.roe_longo_prazo)}; lucro residual / DDM - 1 = "
        f"{sg.pct(round(d.divergencia, 8), 4)}; alerta de VT/valor acima de "
        f"{settings.dcf.alerta_tv_sobre_ev:.0%}."
    )
    p = r.perfil
    console.print(
        f"Valor ponderado ({p.perfil}): [bold]{_reais(r.valor_ponderado)}[/]; margem de segurança "
        f"{p.margem_seguranca:.0%} ⇒ preço máximo de compra [bold]{_reais(r.preco_maximo_compra)}"
        f"[/]; preço {_reais(r.preco)} (upside {_taxa(r.upside)})."
    )
    console.print(
        f"Retorno implícito no preço: Ke {_taxa(r.ke_implicito)} contra hurdle "
        f"{_taxa(r.hurdle)} (Selic + {sg.pp(p.hurdle_spread_selic)}) e Ke de {_taxa(cc.ke.ke)}."
    )


def _resumo_financeira(
    ticker: str,
    e: _Execucao,
    cc: wc.CustoCapitalFinanceira,
    r: cen.ResultadoCenarios[ddm.AvaliacaoDDM],
    avisos: list[str],
) -> pd.DataFrame:
    """Linha única de `resumo.csv` de uma financeira (DDM)."""
    av = r.avaliacoes[e.referencia]
    d = av.ddm
    linha: dict[str, object] = {
        "ticker": ticker,
        "data_base": e.base.isoformat(),
        "modelo": "ddm",
        "perfil": e.efetivo.perfil,
        "origem_perfil": e.efetivo.origem,
        "moeda_reporte": cc.ke.moeda,
        "preco": r.preco,
        **{
            f"valor_{c}": r.avaliacoes[c].valor_por_acao if c in r.avaliacoes else None
            for c in pj.CENARIOS
        },
        "cenarios": ",".join(r.pesos),
        "valor_ponderado": r.valor_ponderado,
        "margem_seguranca": r.perfil.margem_seguranca,
        "preco_maximo_compra": r.preco_maximo_compra,
        "upside": r.upside,
        "ke_implicito": r.ke_implicito,
        "hurdle": r.hurdle,
        "ke": cc.ke.ke,
        "g": d.g,
        "roe_longo_prazo": d.roe_longo_prazo,
        "pvp_justificado": d.pvp_justificado,
        "pvp_implicito": d.pvp_implicito,
        "vt_sobre_valor": d.vt_sobre_valor,
        "valor_lucro_residual": d.valor_lucro_residual / av.acoes,
        "divergencia_lucro_residual": d.divergencia,
        "pl_inicial": d.pl_inicial,
        "data_balanco": cc.data_balanco.isoformat(),
        "avisos": " | ".join(avisos),
    }
    df = pd.DataFrame([linha])
    numericas = [c for c, v in linha.items() if v is None or isinstance(v, float | int)]
    df[numericas] = df[numericas].astype("float64")
    return df


if __name__ == "__main__":  # pragma: no cover
    app()
