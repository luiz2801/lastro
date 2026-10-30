"""Padronização das demonstrações da CVM no plano de contas de `config/mapeamento_contas.yaml`.

Duas etapas:

1. `selecionar_reapresentacoes`: para cada demonstração e período (`dt_ini`, `dt_fim`), fica só
   o documento **mais recente** que o reporta (inclusive como `PENÚLTIMO`), porque ele traz as
   reclassificações. Todas as contas de um período vêm do mesmo documento, o que evita somar
   códigos que mudaram entre documentos.
2. `padronizar`: aplica as regras do plano de contas e devolve a tabela longa
   `contas_padronizadas` (seção 7.1 do guia).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

from valuation.config import DIR_CONFIG, ErroConfiguracao
from valuation.contabil import ErroContabil

logger = logging.getLogger(__name__)

CAMINHO_MAPEAMENTO = DIR_CONFIG / "mapeamento_contas.yaml"

Familia = Literal["BPA", "BPP", "DRE", "DFC", "DVA"]
TipoPlano = Literal["nao_financeira", "financeira"]
FAMILIAS: dict[str, Familia] = {
    "BPA": "BPA",
    "BPP": "BPP",
    "DRE": "DRE",
    "DFC_MI": "DFC",
    "DFC_MD": "DFC",
    "DVA": "DVA",
}
FAMILIAS_SALDO = frozenset({"BPA", "BPP"})

COLUNAS_PADRONIZADAS = [
    "cd_cvm",
    "ticker",
    "dt_refer",
    "dt_ini",
    "dt_fim",
    "periodicidade",
    "demonstracao",
    "conta_padrao",
    "valor",
    "moeda",
    "escala_aplicada",
    "versao",
    "fonte_arquivo",
    "regra",
    "cd_contas",
]


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c)).lower()


def _abaixo(codigo: str, prefixo: str) -> bool:
    return codigo.startswith(prefixo + ".")


class RegraMapeamento(BaseModel):
    """Uma regra do plano de contas. Ver o cabeçalho de `config/mapeamento_contas.yaml`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dem: Familia
    cd: str | None = None
    cd_prefixo: tuple[str, ...] = ()
    cd_excluir: tuple[str, ...] = ()
    ds_regex: str | None = None
    ds_excluir: str | None = None
    sinal: Literal[1, -1] = 1

    @field_validator("cd_prefixo", "cd_excluir", mode="before")
    @classmethod
    def _texto_vira_tupla(cls, v: object) -> object:
        return (v,) if isinstance(v, str) else v

    @field_validator("ds_regex", "ds_excluir")
    @classmethod
    def _regex_valida(cls, v: str | None) -> str | None:
        if v is not None:
            try:
                re.compile(v)
            except re.error as e:
                raise ValueError(f"regex inválida {v!r}: {e}") from e
        return v

    @model_validator(mode="after")
    def _algum_criterio(self) -> RegraMapeamento:
        if self.cd is None and self.ds_regex is None:
            raise ValueError("regra precisa de `cd` ou `ds_regex`")
        return self

    @property
    def eh_saldo(self) -> bool:
        return self.dem in FAMILIAS_SALDO

    def casar(self, df: pd.DataFrame) -> pd.Series:
        """Máscara das linhas de `df` (já com `familia`) que a regra casa."""
        mascara = df["familia"] == self.dem
        codigos = df["cd_conta"]
        if self.cd is not None:
            mascara &= codigos == self.cd
        if self.cd_prefixo:
            mascara &= codigos.map(lambda c: any(_abaixo(c, p) for p in self.cd_prefixo))
        if self.cd_excluir:
            mascara &= ~codigos.map(lambda c: any(c == p or _abaixo(c, p) for p in self.cd_excluir))
        if self.ds_regex is not None or self.ds_excluir is not None:
            descricoes = df["ds_conta"].map(_sem_acento)
            if self.ds_regex is not None:
                mascara &= descricoes.map(re.compile(self.ds_regex).search).notna()
            if self.ds_excluir is not None:
                mascara &= descricoes.map(re.compile(self.ds_excluir).search).isna()
        return mascara


@dataclass(frozen=True)
class PlanoContas:
    tipo: TipoPlano
    contas: Mapping[str, tuple[RegraMapeamento, ...]]
    criticas: tuple[str, ...]

    def eh_saldo(self, conta: str) -> bool:
        return self.contas[conta][0].eh_saldo


def _ler_regras(conta: str, regras: object) -> tuple[RegraMapeamento, ...]:
    if not isinstance(regras, list) or not regras:
        raise ErroConfiguracao(f"Conta {conta!r}: esperada lista não vazia de regras.")
    try:
        lidas = tuple(RegraMapeamento.model_validate(r) for r in regras)
    except ValidationError as e:
        raise ErroConfiguracao(f"Conta {conta!r}: regra inválida: {e}") from e
    if len({r.eh_saldo for r in lidas}) > 1:
        raise ErroConfiguracao(f"Conta {conta!r} mistura saldo (BPA/BPP) e fluxo nas regras.")
    return lidas


def carregar_mapeamento(
    caminho: Path = CAMINHO_MAPEAMENTO,
    tipo: TipoPlano = "nao_financeira",
    extra: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
) -> PlanoContas:
    """Lê o plano de contas `tipo`. Regras de `extra` (`mapeamento_extra` da empresa) vêm antes."""
    try:
        bruto = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise ErroConfiguracao(f"Não foi possível ler {caminho}: {e}") from e
    secao = bruto.get(tipo) if isinstance(bruto, dict) else None
    if not isinstance(secao, dict):
        raise ErroConfiguracao(f"{caminho}: seção {tipo!r} ausente.")
    contas = {conta: _ler_regras(conta, regras) for conta, regras in secao.items()}
    for conta, regras in (extra or {}).items():
        novas = _ler_regras(conta, list(regras))
        anteriores = contas.get(conta, ())
        if anteriores and anteriores[0].eh_saldo != novas[0].eh_saldo:
            raise ErroConfiguracao(f"mapeamento_extra de {conta!r} troca saldo por fluxo.")
        contas[conta] = novas + anteriores
    criticas = tuple((bruto.get("contas_criticas") or {}).get(tipo, ()))
    desconhecidas = sorted(set(criticas) - set(contas))
    if desconhecidas:
        raise ErroConfiguracao(f"contas_criticas sem regra: {', '.join(desconhecidas)}")
    return PlanoContas(tipo=tipo, contas=contas, criticas=criticas)


def periodicidade(dt_ini: pd.Timestamp, dt_fim: pd.Timestamp) -> str:
    """`S` (saldo), `A` (12 meses), `T` (3 meses) ou `YTD` (acumulado de 6 ou 9 meses)."""
    if pd.isna(dt_ini):
        return "S"
    meses = (dt_fim.year - dt_ini.year) * 12 + dt_fim.month - dt_ini.month + 1
    return {12: "A", 3: "T"}.get(meses, "YTD")


def selecionar_reapresentacoes(
    demonstracoes: pd.DataFrame, *, consolidado: bool = True
) -> pd.DataFrame:
    """Para cada família de demonstração e período, mantém só o documento mais recente.

    "Mais recente" = maior (`dt_refer`, `versao`). Documento que informa o período só com zeros
    não conta (os ITR de 2025 de BAZA3, BNBR3 e outros trazem o balanço comparativo zerado), a
    menos que nenhum outro o informe. Se o documento escolhido trouxer DFC pelos métodos indireto e
    direto, fica o indireto (os códigos `6.xx` coincidem).
    """
    df = demonstracoes[
        (demonstracoes["consolidado"] == consolidado)
        & demonstracoes["demonstracao"].isin(list(FAMILIAS))
    ].copy()
    if df.empty:
        tipo = "consolidadas" if consolidado else "individuais"
        raise ErroContabil(f"Nenhuma demonstração {tipo} encontrada.")
    df["familia"] = df["demonstracao"].map(FAMILIAS)

    chave = ["familia", "dt_ini", "dt_fim"]
    candidatos = (
        df.assign(com_valor=df["valor"].fillna(0) != 0)
        .groupby([*chave, "dt_refer", "versao"], dropna=False)["com_valor"]
        .any()
        .reset_index()
    )
    documentos = candidatos.sort_values(["com_valor", "dt_refer", "versao"]).drop_duplicates(
        chave, keep="last"
    )[[*chave, "dt_refer", "versao"]]
    df = df.merge(documentos, on=[*chave, "dt_refer", "versao"], how="inner")

    tem_mi = df[df["demonstracao"] == "DFC_MI"][chave].drop_duplicates()
    md = df["demonstracao"] == "DFC_MD"
    if md.any() and not tem_mi.empty:
        md_com_mi = df[md].reset_index().merge(tem_mi, on=chave)["index"]
        df = df.drop(index=list(md_com_mi))
    return df.reset_index(drop=True)


def _somar_nivel_mais_alto(casadas: pd.DataFrame) -> pd.DataFrame:
    """Soma, por período, as contas casadas que não são subconta de outra casada."""
    linhas = []
    for (dt_ini, dt_fim), grupo in casadas.groupby(["dt_ini", "dt_fim"], dropna=False):
        codigos = grupo["cd_conta"].tolist()
        topo = grupo[[not any(_abaixo(c, o) for o in codigos) for c in codigos]]
        primeira = topo.iloc[0]
        linhas.append(
            {
                "dt_ini": dt_ini,
                "dt_fim": dt_fim,
                "valor": float(topo["valor"].sum()),
                "cd_contas": ";".join(sorted(topo["cd_conta"])),
                "dt_refer": primeira["dt_refer"],
                "versao": primeira["versao"],
                "demonstracao": primeira["demonstracao"],
                "moeda": primeira["moeda"],
                "escala_aplicada": primeira["escala_moeda"],
                "fonte_arquivo": primeira["arquivo"],
            }
        )
    return pd.DataFrame(linhas)


def avaliar_regra(selecionadas: pd.DataFrame, regra: RegraMapeamento) -> pd.DataFrame:
    """Valor da regra em cada período onde ela casa alguma conta (já com o sinal aplicado)."""
    casadas = selecionadas[regra.casar(selecionadas)]
    if casadas.empty:
        return pd.DataFrame()
    valores = _somar_nivel_mais_alto(casadas)
    valores["valor"] = valores["valor"] * regra.sinal
    return valores


def padronizar(selecionadas: pd.DataFrame, plano: PlanoContas, *, ticker: str) -> pd.DataFrame:
    """Aplica o plano de contas às demonstrações já selecionadas (`selecionar_reapresentacoes`).

    Em cada período vence a primeira regra que casa alguma conta. Conta sem regra que case num
    período simplesmente não aparece nele (o QA aponta as críticas que faltarem).
    """
    if selecionadas.empty:
        raise ErroContabil("Nada a padronizar.")
    cd_cvm = int(selecionadas["cd_cvm"].iloc[0])
    partes = []
    for conta, regras in plano.contas.items():
        ja: pd.DataFrame | None = None
        for i, regra in enumerate(regras):
            valores = avaliar_regra(selecionadas, regra)
            if valores.empty:
                continue
            valores["regra"] = i
            if ja is not None:
                usados = pd.MultiIndex.from_frame(ja[["dt_ini", "dt_fim"]])
                novos = ~pd.MultiIndex.from_frame(valores[["dt_ini", "dt_fim"]]).isin(usados)
                valores = valores[novos]
            ja = valores if ja is None else pd.concat([ja, valores], ignore_index=True)
        if ja is None:
            logger.debug("Conta %s sem nenhum período mapeado", conta)
            continue
        ja["conta_padrao"] = conta
        partes.append(ja)
    if not partes:
        raise ErroContabil("Nenhuma conta do plano casou com as demonstrações.")
    contas = pd.concat(partes, ignore_index=True)
    contas["cd_cvm"] = cd_cvm
    contas["ticker"] = ticker
    contas["periodicidade"] = [
        periodicidade(i, f) for i, f in zip(contas["dt_ini"], contas["dt_fim"], strict=True)
    ]
    contas["regra"] = contas["regra"].astype("int64")
    return (
        contas[COLUNAS_PADRONIZADAS]
        .sort_values(["conta_padrao", "dt_fim", "dt_ini"])
        .reset_index(drop=True)
    )


def cobertura(contas: pd.DataFrame, criticas: Sequence[str]) -> pd.Series:
    """Fração dos exercícios (DFP) em que cada conta crítica foi mapeada, por conta."""
    anuais = contas[contas["periodicidade"].isin(["A", "S"])]
    anuais = anuais[(anuais["dt_fim"].dt.month == 12) & (anuais["dt_fim"].dt.day == 31)]
    anos = anuais["dt_fim"].dt.year.nunique()
    if anos == 0:
        return pd.Series(0.0, index=list(criticas), name="cobertura")
    presentes = anuais.assign(ano=anuais["dt_fim"].dt.year).groupby("conta_padrao")["ano"].nunique()
    fracao: pd.Series = presentes.reindex(list(criticas)).fillna(0) / anos
    return fracao.rename("cobertura")


def caminho_padronizadas(dir_processed: Path, cd_cvm: int) -> Path:
    return dir_processed / "cvm" / str(cd_cvm) / "contas_padronizadas.parquet"


def ler_demonstracoes(dir_processed: Path, cd_cvm: int) -> pd.DataFrame:
    caminho = dir_processed / "cvm" / str(cd_cvm) / "demonstracoes.parquet"
    if not caminho.is_file():
        raise FileNotFoundError(2, "arquivo não encontrado", str(caminho))
    return pd.read_parquet(caminho)
