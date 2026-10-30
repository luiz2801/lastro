"""Adaptador dos dados abertos da CVM: DFP, ITR e composição do capital.

Formato validado em `docs/fontes.md`. Os CSVs vêm em latin-1, separados por `;`, sem aspas de
delimitação (aspas aparecem literais dentro de `DS_CONTA`, por isso `QUOTE_NONE`).

Saída por companhia, em `data/processed/cvm/{cd_cvm}/`:

- `demonstracoes.parquet`: tabela longa, uma linha por conta e período, com `valor` já em
  unidades da moeda (escala `MIL` multiplicada na ingestão);
- `composicao_capital.parquet`: quantidade de ações por data de referência.

Nenhuma escolha entre exercícios/reapresentações é feita aqui (isso é da camada `contabil`),
exceto manter a maior `VERSAO` de cada documento.
"""

from __future__ import annotations

import csv
import datetime as dt
import logging
import zipfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pandas as pd

from valuation.data.http import ArquivoNaoEncontrado, ErroDownload, SessaoHttp, baixar

logger = logging.getLogger(__name__)

URL_BASE = "https://dados.cvm.gov.br/dados/CIA_ABERTA"

TipoDocumento = Literal["DFP", "ITR"]
TIPOS_DOCUMENTO: tuple[TipoDocumento, ...] = ("DFP", "ITR")
DEMONSTRACOES = ("BPA", "BPP", "DRE", "DFC_MD", "DFC_MI", "DVA", "DMPL", "DRA")
FATOR_ESCALA = {"MIL": 1000, "UNIDADE": 1}

COLUNAS_DEMONSTRACOES = [
    "cnpj",
    "cd_cvm",
    "denom_cia",
    "fonte",
    "dt_refer",
    "versao",
    "demonstracao",
    "consolidado",
    "moeda",
    "escala_moeda",
    "ordem_exerc",
    "dt_ini",
    "dt_fim",
    "coluna_df",
    "cd_conta",
    "ds_conta",
    "valor",
    "st_conta_fixa",
    "arquivo",
]

COLUNAS_ACOES = [
    "qt_acao_ordin_cap_integr",
    "qt_acao_pref_cap_integr",
    "qt_acao_total_cap_integr",
    "qt_acao_ordin_tesouro",
    "qt_acao_pref_tesouro",
    "qt_acao_total_tesouro",
]


class ErroDadosCVM(Exception):
    """Arquivo da CVM com formato inesperado."""


def url_documento(tipo: TipoDocumento, ano: int) -> str:
    return f"{URL_BASE}/DOC/{tipo}/DADOS/{tipo.lower()}_cia_aberta_{ano}.zip"


def url_cadastro() -> str:
    return f"{URL_BASE}/CAD/DADOS/cad_cia_aberta.csv"


def url_fca(ano: int) -> str:
    return f"{URL_BASE}/DOC/FCA/DADOS/fca_cia_aberta_{ano}.zip"


def nome_csv_demonstracao(
    tipo: TipoDocumento, demonstracao: str, consolidado: bool, ano: int
) -> str:
    sufixo = "con" if consolidado else "ind"
    return f"{tipo.lower()}_cia_aberta_{demonstracao}_{sufixo}_{ano}.csv"


def nome_csv_composicao(tipo: TipoDocumento, ano: int) -> str:
    return f"{tipo.lower()}_cia_aberta_composicao_capital_{ano}.csv"


def validar_zip(caminho: Path) -> None:
    """Rejeita conteúdo que não seja zip (o portal devolve HTML em alguns erros)."""
    if not zipfile.is_zipfile(caminho):
        raise ErroDownload(f"Conteúdo baixado não é um arquivo zip: {caminho.name}")


def ler_csv(origem: Path | zipfile.ZipFile, membro: str | None = None) -> pd.DataFrame | None:
    """Lê um CSV da CVM como texto. Devolve `None` se o membro não existir no zip."""
    opcoes = {
        "sep": ";",
        "encoding": "latin-1",
        "dtype": str,
        "keep_default_na": False,
        "quoting": csv.QUOTE_NONE,
    }
    df: pd.DataFrame
    if isinstance(origem, Path):
        df = pd.read_csv(origem, **opcoes)  # type: ignore[call-overload]
        return df
    if membro not in origem.namelist():
        return None
    with origem.open(membro) as f:
        df = pd.read_csv(f, **opcoes)  # type: ignore[call-overload]
    return df


def normalizar_cd_cvm(serie: pd.Series) -> pd.Series:
    """`CD_CVM` vem com zeros à esquerda na DFP/ITR (`009512`) e sem eles no cadastro."""
    return pd.to_numeric(serie, errors="raise").astype("int64")


def _manter_maior_versao(df: pd.DataFrame, chaves: list[str]) -> pd.DataFrame:
    if df.empty:
        return df
    maior = df.groupby(chaves)["versao"].transform("max")
    descartadas = int((df["versao"] != maior).sum())
    if descartadas:
        logger.debug("Descartadas %d linhas de versões antigas", descartadas)
    return df.loc[df["versao"] == maior]


def _converter_demonstracao(
    bruto: pd.DataFrame, tipo: TipoDocumento, demonstracao: str, consolidado: bool, membro: str
) -> pd.DataFrame:
    escalas = set(bruto["ESCALA_MOEDA"].unique())
    desconhecidas = escalas - FATOR_ESCALA.keys()
    if desconhecidas:
        raise ErroDadosCVM(f"{membro}: ESCALA_MOEDA desconhecida {sorted(desconhecidas)}")

    df = pd.DataFrame(
        {
            "cnpj": bruto["CNPJ_CIA"],
            "cd_cvm": normalizar_cd_cvm(bruto["CD_CVM"]),
            "denom_cia": bruto["DENOM_CIA"],
            "fonte": tipo,
            "dt_refer": pd.to_datetime(bruto["DT_REFER"], format="%Y-%m-%d"),
            "versao": pd.to_numeric(bruto["VERSAO"]).astype("int64"),
            "demonstracao": demonstracao,
            "consolidado": consolidado,
            "moeda": bruto["MOEDA"],
            "escala_moeda": bruto["ESCALA_MOEDA"],
            "ordem_exerc": bruto["ORDEM_EXERC"],
            # Balanço (BPA/BPP) não tem DT_INI_EXERC: saldo numa data.
            "dt_ini": (
                pd.to_datetime(bruto["DT_INI_EXERC"], format="%Y-%m-%d")
                if "DT_INI_EXERC" in bruto
                else pd.NaT
            ),
            "dt_fim": pd.to_datetime(bruto["DT_FIM_EXERC"], format="%Y-%m-%d"),
            # Só a DMPL tem COLUNA_DF (coluna do patrimônio líquido).
            "coluna_df": bruto.get("COLUNA_DF", ""),
            "cd_conta": bruto["CD_CONTA"],
            "ds_conta": bruto["DS_CONTA"],
            "valor": pd.to_numeric(bruto["VL_CONTA"]) * bruto["ESCALA_MOEDA"].map(FATOR_ESCALA),
            "st_conta_fixa": bruto["ST_CONTA_FIXA"],
            "arquivo": membro,
        }
    )
    chaves = ["cnpj", "dt_refer", "demonstracao", "consolidado"]
    return _manter_maior_versao(df, chaves)


def ler_demonstracoes(
    caminho_zip: Path,
    tipo: TipoDocumento,
    ano: int,
    cnpjs: Iterable[str],
    demonstracoes: Sequence[str] = DEMONSTRACOES,
) -> pd.DataFrame:
    """Lê as demonstrações (consolidadas e individuais) das companhias em `cnpjs`."""
    alvo = set(cnpjs)
    partes: list[pd.DataFrame] = []
    with zipfile.ZipFile(caminho_zip) as zf:
        for demonstracao in demonstracoes:
            for consolidado in (True, False):
                membro = nome_csv_demonstracao(tipo, demonstracao, consolidado, ano)
                bruto = ler_csv(zf, membro)
                if bruto is None:
                    logger.warning("%s: arquivo %s ausente", caminho_zip.name, membro)
                    continue
                bruto = bruto.loc[bruto["CNPJ_CIA"].isin(alvo)]
                if bruto.empty:
                    continue
                partes.append(
                    _converter_demonstracao(bruto, tipo, demonstracao, consolidado, membro)
                )
    if not partes:
        return pd.DataFrame(columns=COLUNAS_DEMONSTRACOES)
    return pd.concat(partes, ignore_index=True)[COLUNAS_DEMONSTRACOES]


def ler_composicao_capital(
    caminho_zip: Path, tipo: TipoDocumento, ano: int, cnpjs: Iterable[str]
) -> pd.DataFrame:
    """Quantidade de ações por classe e em tesouraria, como publicada (sem escala).

    O arquivo não tem coluna de escala e algumas companhias informam em milhares (ver
    `corrigir_escala_acoes`). As DFP até 2019 não trazem este arquivo.
    """
    colunas = ["cnpj", "fonte", "dt_refer", "versao", *COLUNAS_ACOES]
    with zipfile.ZipFile(caminho_zip) as zf:
        membro = nome_csv_composicao(tipo, ano)
        bruto = ler_csv(zf, membro)
    if bruto is None:
        logger.info("%s: sem arquivo de composição do capital", caminho_zip.name)
        return pd.DataFrame(columns=colunas)
    bruto = bruto.loc[bruto["CNPJ_CIA"].isin(set(cnpjs))]
    df = pd.DataFrame(
        {
            "cnpj": bruto["CNPJ_CIA"],
            "fonte": tipo,
            "dt_refer": pd.to_datetime(bruto["DT_REFER"], format="%Y-%m-%d"),
            "versao": pd.to_numeric(bruto["VERSAO"]).astype("int64"),
            **{c: pd.to_numeric(bruto[c.upper()]).astype("int64") for c in COLUNAS_ACOES},
        }
    )
    return _manter_maior_versao(df, ["cnpj", "dt_refer"])[colunas]


def corrigir_escala_acoes(acoes: pd.DataFrame, escala_base: int) -> pd.DataFrame:
    """Aplica a escala das quantidades de ações de uma companhia.

    `escala_base` vem do cadastro manual (a Vale informa tudo em milhares). Depois disso, datas
    com ~1000x menos ações que a data mais recente são tratadas como informadas em milhares
    (ex.: Petrobras na DFP 2020) e multiplicadas, com aviso. Desdobramentos reais têm razões
    pequenas (2:1, 10:1) e não caem na faixa.
    """
    df = acoes.sort_values("dt_refer").reset_index(drop=True)
    escala = pd.Series(escala_base, index=df.index, dtype="int64")
    if not df.empty:
        referencia = df["qt_acao_total_cap_integr"].iloc[-1] * escala_base
        razao = referencia / (df["qt_acao_total_cap_integr"] * escala_base).replace(0, pd.NA)
        em_milhares = razao.between(500, 2000).fillna(False).astype(bool)
        if em_milhares.any():
            logger.warning(
                "%s: quantidade de ações aparentemente em milhares em %s; multiplicada por 1000",
                df["cnpj"].iloc[0],
                [d.date().isoformat() for d in df.loc[em_milhares, "dt_refer"]],
            )
        escala = escala.mask(em_milhares, escala_base * 1000)
    for coluna in COLUNAS_ACOES:
        df[coluna] = df[coluna].astype("int64") * escala
    df["escala_acoes_aplicada"] = escala
    return df


@dataclass(frozen=True)
class AlvoCVM:
    """Companhia a coletar. `escala_acoes` corrige a composição do capital (1 ou 1000)."""

    cnpj: str
    cd_cvm: int
    escala_acoes: int = 1


@dataclass
class ResumoColeta:
    anos_baixados: dict[TipoDocumento, list[int]] = field(default_factory=dict)
    anos_indisponiveis: dict[TipoDocumento, list[int]] = field(default_factory=dict)
    linhas_por_cd_cvm: dict[int, int] = field(default_factory=dict)
    periodos_por_cd_cvm: dict[int, list[dt.date]] = field(default_factory=dict)


def anos_a_coletar(ano_base: int, historico_anos: int) -> dict[TipoDocumento, list[int]]:
    """DFP: `historico_anos` exercícios encerrados + o ano corrente; ITR: os 2 últimos anos."""
    return {
        "DFP": list(range(ano_base - historico_anos, ano_base + 1)),
        "ITR": [ano_base - 1, ano_base],
    }


def coletar(
    alvos: Sequence[AlvoCVM],
    anos: dict[TipoDocumento, list[int]],
    *,
    dir_raw: Path,
    dir_processed: Path,
    ttl: dt.timedelta,
    sessao: SessaoHttp,
    agora: dt.datetime,
    forcar: bool = False,
) -> ResumoColeta:
    """Baixa DFP/ITR, extrai as companhias de `alvos` e grava um parquet por companhia.

    404 é tolerado só no ano mais recente de cada tipo (documento ainda não publicado).
    """
    cnpjs = {a.cnpj for a in alvos}
    resumo = ResumoColeta()
    demonstracoes: list[pd.DataFrame] = []
    acoes: list[pd.DataFrame] = []

    for tipo, lista in anos.items():
        resumo.anos_baixados[tipo] = []
        resumo.anos_indisponiveis[tipo] = []
        for ano in lista:
            url = url_documento(tipo, ano)
            destino = dir_raw / "cvm" / tipo / url.rsplit("/", 1)[1]
            try:
                arquivo = baixar(
                    url,
                    destino,
                    ttl=ttl,
                    sessao=sessao,
                    agora=agora,
                    forcar=forcar,
                    validar=validar_zip,
                )
            except ArquivoNaoEncontrado:
                if ano != max(lista):
                    raise
                logger.info("%s %d ainda não publicado", tipo, ano)
                resumo.anos_indisponiveis[tipo].append(ano)
                continue
            resumo.anos_baixados[tipo].append(ano)
            demonstracoes.append(ler_demonstracoes(arquivo.caminho, tipo, ano, cnpjs))
            acoes.append(ler_composicao_capital(arquivo.caminho, tipo, ano, cnpjs))

    todas_dem = pd.concat(demonstracoes, ignore_index=True) if demonstracoes else None
    todas_acoes = pd.concat(acoes, ignore_index=True) if acoes else None
    for alvo in alvos:
        pasta = dir_processed / "cvm" / str(alvo.cd_cvm)
        pasta.mkdir(parents=True, exist_ok=True)

        dem = (
            todas_dem.loc[todas_dem["cnpj"] == alvo.cnpj]
            if todas_dem is not None
            else pd.DataFrame(columns=COLUNAS_DEMONSTRACOES)
        )
        if dem.empty:
            logger.warning("Nenhuma demonstração encontrada para %s", alvo.cnpj)
        else:
            outros = set(dem["cd_cvm"].unique()) - {alvo.cd_cvm}
            if outros:
                raise ErroDadosCVM(
                    f"CNPJ {alvo.cnpj} aparece com CD_CVM {sorted(outros)} nas demonstrações, "
                    f"mas o cadastro indica {alvo.cd_cvm}"
                )
        dem.to_parquet(pasta / "demonstracoes.parquet", index=False)

        ac = (
            todas_acoes.loc[todas_acoes["cnpj"] == alvo.cnpj]
            if todas_acoes is not None
            else pd.DataFrame(columns=["cnpj", "fonte", "dt_refer", "versao", *COLUNAS_ACOES])
        )
        ac = corrigir_escala_acoes(ac, alvo.escala_acoes)
        ac.to_parquet(pasta / "composicao_capital.parquet", index=False)

        resumo.linhas_por_cd_cvm[alvo.cd_cvm] = len(dem)
        resumo.periodos_por_cd_cvm[alvo.cd_cvm] = sorted(
            {d.date() for d in pd.to_datetime(dem["dt_refer"])}
        )
    return resumo
