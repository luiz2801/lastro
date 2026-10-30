"""Interface de linha de comando (`valuation`)."""

from __future__ import annotations

import datetime as dt
import logging
import platform
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import typer
from rich.console import Console
from rich.table import Table

from valuation import __version__
from valuation.config import (
    CAMINHO_CADASTRO_MANUAL,
    CAMINHO_PERFIL,
    CAMINHO_UNIVERSO,
    DIR_PROCESSED,
    DIR_RAW,
    ErroConfiguracao,
    Settings,
    carregar_settings,
)
from valuation.contabil import ErroContabil
from valuation.contabil import nao_financeiras as nf
from valuation.contabil import padronizacao as pad
from valuation.contabil import periodos as per
from valuation.contabil import qa as qa_mod
from valuation.contabil.moeda import detectar_moeda
from valuation.data import cadastro as cad
from valuation.data import cvm
from valuation.data import macro as mac
from valuation.data import precos as prc
from valuation.data.http import ErroDownload, criar_sessao
from valuation.data.validacao import ErroDadosExternos, Leitura, Validado
from valuation.perfil import ErroPerfil
from valuation.perfil import registro as reg
from valuation.perfil.parametros import parametros_do_perfil
from valuation.perfil.questionario import QUESTIONARIO

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


@dataclass(frozen=True)
class _Padronizada:
    empresa: cad.Empresa
    plano: pad.PlanoContas
    selecionadas: pd.DataFrame
    contas: pd.DataFrame
    moeda: str


def _padronizar(ticker: str, settings: Settings) -> _Padronizada:
    """Padroniza as demonstrações de `ticker` e grava `contas_padronizadas.parquet`."""
    data_base = settings.resolver_data_base(dt.date.today())
    empresa = cad.empresa_por_ticker(_carregar_cadastro(settings, data_base, False), ticker)
    if empresa.tipo_modelo != "nao_financeira":
        raise ErroContabil(
            f"{', '.join(empresa.tickers)} é {empresa.tipo_modelo}: só o plano de contas "
            "não financeiro existe por enquanto (financeiras na Fase 10)."
        )
    plano = pad.carregar_mapeamento()
    try:
        demonstracoes = pad.ler_demonstracoes(DIR_PROCESSED, empresa.cd_cvm)
    except FileNotFoundError as e:
        raise ErroContabil(
            f"{e.filename} não existe. Rode `valuation atualizar --tickers {ticker}`."
        ) from e
    selecionadas = pad.selecionar_reapresentacoes(demonstracoes)
    moeda = detectar_moeda(selecionadas)
    contas = pad.padronizar(selecionadas, plano, ticker=cad.normalizar_ticker(ticker))
    contas.to_parquet(pad.caminho_padronizadas(DIR_PROCESSED, empresa.cd_cvm), index=False)
    return _Padronizada(empresa, plano, selecionadas, contas, moeda)


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
            m = nf.metricas(per.anual(p.contas), aliquota_nominal=aliquota).tail(anos)
            ltm = nf.metricas_ltm(p.contas, aliquota_nominal=aliquota)
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


if __name__ == "__main__":  # pragma: no cover
    app()
