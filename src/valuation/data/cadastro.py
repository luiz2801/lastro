"""Cadastro: ticker <-> CNPJ <-> `CD_CVM`, setor e classes de ação.

Ligação (ver `docs/fontes.md`):

    ticker --(FCA valor_mobiliario)--> CNPJ --(cad_cia_aberta.csv)--> CD_CVM

`config/cadastro_manual.csv` sobrescreve campos por ticker (tipo de modelo, escala da quantidade
de ações) ou acrescenta tickers que o FCA não traz.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
import unicodedata
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast, get_args

import pandas as pd

from valuation.data.cvm import ler_csv, normalizar_cd_cvm, url_cadastro, url_fca, validar_zip
from valuation.data.http import ArquivoNaoEncontrado, ErroDownload, SessaoHttp, baixar

logger = logging.getLogger(__name__)

TipoModelo = Literal["nao_financeira", "financeira", "holding", "nao_suportada"]
Especie = Literal["ON", "PN", "UNIT"]

ESPECIE_POR_VALOR_MOBILIARIO: dict[str, Especie] = {
    "Ações Ordinárias": "ON",
    "Ações Preferenciais": "PN",
    "Units": "UNIT",
}
# Setores CVM (sem o prefixo "Emp. Adm. Part. - ") avaliados pelo pipeline financeiro.
SETORES_FINANCEIROS = frozenset(
    {
        "Bancos",
        "Seguradoras e Corretoras",
        "Intermediação Financeira",
        "Arrendamento Mercantil",
        "Crédito Imobiliário",
    }
)
SETORES_NAO_SUPORTADOS = frozenset({"Securitização de Recebíveis"})
PREFIXO_HOLDING = "Emp. Adm. Part. - "
RE_TICKER = re.compile(r"^[A-Z][A-Z0-9]{3}\d{1,2}$")

COLUNAS_CADASTRO = [
    "ticker",
    "especie",
    "cnpj",
    "cd_cvm",
    "razao_social",
    "nome_comercial",
    "setor_cvm",
    "situacao",
    "tipo_modelo",
    "escala_acoes",
    "acoes_por_unit",
    "origem",
]


class ErroCadastro(Exception):
    """Ticker ou companhia não encontrado, ou cadastro inconsistente."""


@dataclass(frozen=True)
class ClasseAcao:
    ticker: str
    especie: Especie
    acoes_por_unit: int = 0  # só UNIT: ações (ON + PN) por unit; 0 = desconhecido


@dataclass(frozen=True)
class Empresa:
    cnpj: str
    cd_cvm: int
    razao_social: str
    nome_comercial: str
    setor_cvm: str
    tipo_modelo: TipoModelo
    escala_acoes: int
    classes: tuple[ClasseAcao, ...]

    @property
    def tickers(self) -> tuple[str, ...]:
        return tuple(c.ticker for c in self.classes)


def classificar_tipo_modelo(setor_cvm: str) -> TipoModelo:
    """Classificação automática pelo setor CVM.

    Holdings não são detectáveis pelo setor ("Emp. Adm. Part." inclui operacionais como a WEG);
    são marcadas em `cadastro_manual.csv`.
    """
    base = setor_cvm.removeprefix(PREFIXO_HOLDING)
    if base in SETORES_FINANCEIROS:
        return "financeira"
    if base in SETORES_NAO_SUPORTADOS:
        return "nao_suportada"
    return "nao_financeira"


def normalizar_ticker(ticker: str) -> str:
    return ticker.strip().upper().removesuffix(".SA")


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c)).upper()


def ler_cadastro_cvm(caminho: Path) -> pd.DataFrame:
    """Uma linha por CNPJ. Há várias linhas por companhia no arquivo (uma por mercado e
    registros cancelados com outro `CD_CVM`); prefere-se o registro ATIVO mais recente."""
    bruto = ler_csv(caminho)
    assert bruto is not None
    df = pd.DataFrame(
        {
            "cnpj": bruto["CNPJ_CIA"],
            "cd_cvm": normalizar_cd_cvm(bruto["CD_CVM"]),
            "razao_social": bruto["DENOM_SOCIAL"],
            "nome_comercial": bruto["DENOM_COMERC"],
            "setor_cvm": bruto["SETOR_ATIV"],
            "situacao": bruto["SIT"],
            "_ativo": bruto["SIT"] == "ATIVO",
            "_dt_ini_sit": bruto["DT_INI_SIT"],
        }
    )
    df = df.sort_values(["_ativo", "_dt_ini_sit"], ascending=False, kind="stable")
    df = df.drop_duplicates("cnpj", keep="first")
    return df.drop(columns=["_ativo", "_dt_ini_sit"]).reset_index(drop=True)


def ler_valores_mobiliarios(zips_fca: Sequence[Path], data_ref: dt.date) -> pd.DataFrame:
    """Ações negociadas em bolsa (ON, PN, units) por CNPJ, do FCA mais recente de cada companhia.

    Descarta códigos inválidos ("NÃO HÁ", "N/A") e negociação encerrada antes de `data_ref`.
    """
    partes: list[pd.DataFrame] = []
    for caminho in zips_fca:
        ano = re.search(r"(\d{4})\.zip$", caminho.name)
        if ano is None:
            raise ErroCadastro(f"Nome de arquivo FCA inesperado: {caminho.name}")
        with zipfile.ZipFile(caminho) as zf:
            parte = ler_csv(zf, f"fca_cia_aberta_valor_mobiliario_{ano.group(1)}.csv")
        if parte is None:
            raise ErroCadastro(f"{caminho.name} sem o arquivo valor_mobiliario")
        partes.append(parte)
    if not partes:
        return pd.DataFrame(columns=["ticker", "especie", "cnpj"])
    vm = pd.concat(partes, ignore_index=True)

    # Só o documento FCA mais recente de cada companhia (tickers antigos saem).
    vm["_versao"] = pd.to_numeric(vm["Versao"])
    ultimo = vm.groupby("CNPJ_Companhia")["Data_Referencia"].transform("max")
    vm = vm.loc[vm["Data_Referencia"] == ultimo]
    ultima_versao = vm.groupby("CNPJ_Companhia")["_versao"].transform("max")
    vm = vm.loc[vm["_versao"] == ultima_versao]

    ticker = vm["Codigo_Negociacao"].str.strip().str.upper()
    fim = pd.to_datetime(vm["Data_Fim_Negociacao"].replace("", None), format="%Y-%m-%d")
    filtro = (
        vm["Valor_Mobiliario"].isin(ESPECIE_POR_VALOR_MOBILIARIO.keys())
        & (vm["Mercado"] == "Bolsa")
        & ticker.str.match(RE_TICKER)
        & (fim.isna() | (fim >= pd.Timestamp(data_ref)))
    )
    df = pd.DataFrame(
        {
            "ticker": ticker[filtro],
            "especie": vm.loc[filtro, "Valor_Mobiliario"].map(ESPECIE_POR_VALOR_MOBILIARIO),
            "cnpj": vm.loc[filtro, "CNPJ_Companhia"],
        }
    ).drop_duplicates()

    # Há tickers repetidos no FCA, ex.: o mesmo código como ON e PN da mesma companhia.
    duplicados = df.loc[df["ticker"].duplicated(keep=False)]
    if not duplicados.empty:
        logger.warning(
            "Tickers repetidos no FCA (mantida a primeira linha): %s",
            sorted(duplicados["ticker"].unique()),
        )
        df = df.drop_duplicates("ticker", keep="first")
    return df.reset_index(drop=True)


def ler_cadastro_manual(caminho: Path) -> pd.DataFrame:
    """`ticker;cnpj;especie;tipo_modelo;escala_acoes;acoes_por_unit;observacao` (UTF-8). Linhas
    com `#` no início são comentários. Campos vazios não sobrescrevem nada. `acoes_por_unit` é
    opcional (arquivo sem a coluna = vazia) e só vale para units (ADR 0015)."""
    colunas = [
        "ticker",
        "cnpj",
        "especie",
        "tipo_modelo",
        "escala_acoes",
        "acoes_por_unit",
        "observacao",
    ]
    if not caminho.is_file():
        return pd.DataFrame(columns=colunas)
    df = pd.read_csv(
        caminho, sep=";", dtype=str, keep_default_na=False, comment="#", encoding="utf-8"
    )
    if "acoes_por_unit" not in df.columns and "escala_acoes" in df.columns:
        df.insert(list(df.columns).index("escala_acoes") + 1, "acoes_por_unit", "")
    if list(df.columns) != colunas:
        raise ErroCadastro(
            f"{caminho}: colunas esperadas {colunas}, encontradas {list(df.columns)}"
        )
    df["ticker"] = df["ticker"].map(normalizar_ticker)
    invalidos = df.loc[
        (df["tipo_modelo"] != "") & ~df["tipo_modelo"].isin(get_args(TipoModelo)), "ticker"
    ]
    if not invalidos.empty:
        raise ErroCadastro(f"{caminho}: tipo_modelo inválido para {list(invalidos)}")
    invalidos = df.loc[(df["especie"] != "") & ~df["especie"].isin(get_args(Especie)), "ticker"]
    if not invalidos.empty:
        raise ErroCadastro(f"{caminho}: especie inválida para {list(invalidos)}")
    invalidos = df.loc[~df["escala_acoes"].isin(["", "1", "1000"]), "ticker"]
    if not invalidos.empty:
        raise ErroCadastro(f"{caminho}: escala_acoes deve ser 1 ou 1000 para {list(invalidos)}")
    invalidos = df.loc[
        (df["acoes_por_unit"] != "")
        & ~df["acoes_por_unit"].map(lambda x: x.isdigit() and int(x) >= 2).astype(bool),
        "ticker",
    ]
    if not invalidos.empty:
        raise ErroCadastro(
            f"{caminho}: acoes_por_unit deve ser um inteiro >= 2 para {list(invalidos)}"
        )
    return df


def montar_cadastro(
    cadastro_cvm: pd.DataFrame, valores_mobiliarios: pd.DataFrame, manual: pd.DataFrame
) -> pd.DataFrame:
    """Uma linha por ticker com dados da companhia, tipo de modelo e escala das ações."""
    base = valores_mobiliarios.assign(origem="fca")

    novos = manual.loc[~manual["ticker"].isin(base["ticker"])]
    sem_cnpj = novos.loc[(novos["cnpj"] == "") | (novos["especie"] == ""), "ticker"]
    if not sem_cnpj.empty:
        raise ErroCadastro(
            f"Tickers do cadastro manual fora do FCA precisam de cnpj e especie: {list(sem_cnpj)}"
        )
    base = pd.concat(
        [base, novos[["ticker", "especie", "cnpj"]].assign(origem="manual")], ignore_index=True
    )

    df = base.merge(cadastro_cvm, on="cnpj", how="left", validate="many_to_one")
    sem_cvm = df.loc[df["cd_cvm"].isna(), "ticker"]
    if not sem_cvm.empty:
        logger.warning("Tickers sem companhia no cadastro CVM (ignorados): %s", list(sem_cvm))
        df = df.loc[df["cd_cvm"].notna()]
    df["cd_cvm"] = df["cd_cvm"].astype("int64")
    df["tipo_modelo"] = df["setor_cvm"].map(classificar_tipo_modelo)
    df["escala_acoes"] = 1
    df["acoes_por_unit"] = 0

    for linha in manual.to_dict("records"):
        ticker, cnpj = str(linha["ticker"]), str(linha["cnpj"])
        alvo = df["ticker"] == ticker
        if cnpj and ticker in set(valores_mobiliarios["ticker"]):
            cnpj_fca = str(df.loc[alvo, "cnpj"].iloc[0])
            if cnpj_fca != cnpj:
                raise ErroCadastro(
                    f"{ticker}: CNPJ do cadastro manual ({cnpj}) difere do FCA ({cnpj_fca})"
                )
        if linha["especie"]:
            df["especie"] = df["especie"].mask(alvo, linha["especie"])
        if linha["tipo_modelo"]:
            df["tipo_modelo"] = df["tipo_modelo"].mask(alvo, linha["tipo_modelo"])
        if linha["escala_acoes"]:
            df["escala_acoes"] = df["escala_acoes"].mask(alvo, int(linha["escala_acoes"]))
        if linha["acoes_por_unit"]:
            df["acoes_por_unit"] = df["acoes_por_unit"].mask(alvo, int(linha["acoes_por_unit"]))

    nao_units = df.loc[(df["acoes_por_unit"] > 0) & (df["especie"] != "UNIT"), "ticker"]
    if not nao_units.empty:
        raise ErroCadastro(f"acoes_por_unit só vale para units: {list(nao_units)}")

    return df[COLUNAS_CADASTRO].sort_values("ticker").reset_index(drop=True)


def buscar(cadastro: pd.DataFrame, texto: str) -> pd.DataFrame:
    """Busca por ticker, razão social, nome comercial ou CNPJ (sem acento, sem caixa)."""
    termo = _sem_acento(texto.strip())
    digitos = re.sub(r"\D", "", texto)
    campos = cadastro["ticker"] + " " + cadastro["razao_social"] + " " + cadastro["nome_comercial"]
    achou = campos.map(_sem_acento).str.contains(termo, regex=False)
    if len(digitos) >= 4:
        achou |= cadastro["cnpj"].str.replace(r"\D", "", regex=True).str.contains(digitos)
    return cadastro.loc[achou].reset_index(drop=True)


def empresa_por_ticker(cadastro: pd.DataFrame, ticker: str) -> Empresa:
    ticker = normalizar_ticker(ticker)
    linha = cadastro.loc[cadastro["ticker"] == ticker]
    if linha.empty:
        parecidos = cadastro.loc[cadastro["ticker"].str.startswith(ticker[:4]), "ticker"]
        dica = f" Parecidos: {', '.join(parecidos)}." if not parecidos.empty else ""
        raise ErroCadastro(
            f"Ticker {ticker} não encontrado no cadastro.{dica} "
            "Use `valuation cadastro buscar` ou acrescente-o em config/cadastro_manual.csv."
        )
    cnpj = linha["cnpj"].iloc[0]
    da_empresa = cadastro.loc[cadastro["cnpj"] == cnpj]
    for coluna in ("tipo_modelo", "escala_acoes"):
        valores = da_empresa[coluna].unique()
        if len(valores) > 1:
            raise ErroCadastro(
                f"{cnpj}: {coluna} diferente entre as classes {list(da_empresa['ticker'])}: "
                f"{list(valores)}. Corrija config/cadastro_manual.csv."
            )
    primeira = da_empresa.iloc[0]
    return Empresa(
        cnpj=cnpj,
        cd_cvm=int(primeira["cd_cvm"]),
        razao_social=str(primeira["razao_social"]),
        nome_comercial=str(primeira["nome_comercial"]),
        setor_cvm=str(primeira["setor_cvm"]),
        tipo_modelo=cast(TipoModelo, primeira["tipo_modelo"]),
        escala_acoes=int(primeira["escala_acoes"]),
        classes=tuple(
            ClasseAcao(str(t), cast(Especie, e), int(n))
            for t, e, n in zip(
                da_empresa["ticker"],
                da_empresa["especie"],
                da_empresa.get("acoes_por_unit", pd.Series(0, index=da_empresa.index)),
                strict=True,
            )
        ),
    )


def atualizar_cadastro(
    *,
    ano: int,
    data_ref: dt.date,
    dir_raw: Path,
    dir_processed: Path,
    caminho_manual: Path,
    ttl: dt.timedelta,
    sessao: SessaoHttp,
    agora: dt.datetime,
    forcar: bool = False,
) -> pd.DataFrame:
    """Baixa cadastro CVM e FCA (`ano` e `ano - 1`), monta e grava `cadastro.parquet`."""
    pasta = dir_raw / "cvm"

    def validar_cadastro(caminho: Path) -> None:
        with caminho.open("rb") as f:
            if not f.read(9) == b"CNPJ_CIA;":
                raise ErroDownload("cad_cia_aberta.csv com cabeçalho inesperado")

    cad = baixar(
        url_cadastro(),
        pasta / "CAD" / "cad_cia_aberta.csv",
        ttl=ttl,
        sessao=sessao,
        agora=agora,
        forcar=forcar,
        validar=validar_cadastro,
    )
    zips_fca: list[Path] = []
    for a in (ano - 1, ano):
        try:
            arquivo = baixar(
                url_fca(a),
                pasta / "FCA" / f"fca_cia_aberta_{a}.zip",
                ttl=ttl,
                sessao=sessao,
                agora=agora,
                forcar=forcar,
                validar=validar_zip,
            )
        except ArquivoNaoEncontrado:
            if a != ano:
                raise
            logger.info("FCA %d ainda não publicado", a)
            continue
        zips_fca.append(arquivo.caminho)

    cadastro = montar_cadastro(
        ler_cadastro_cvm(cad.caminho),
        ler_valores_mobiliarios(zips_fca, data_ref),
        ler_cadastro_manual(caminho_manual),
    )
    dir_processed.mkdir(parents=True, exist_ok=True)
    cadastro.to_parquet(dir_processed / "cadastro.parquet", index=False)
    return cadastro
