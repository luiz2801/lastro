"""Perfil gravado em JSON local, com validade de 12 meses (seção 8.3 do CLAUDE.md)."""

from __future__ import annotations

import calendar
import datetime as dt
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast, get_args

from valuation.perfil import ErroPerfil, NomePerfil
from valuation.perfil.pontuacao import classificar
from valuation.perfil.questionario import VERSAO_QUESTIONARIO

VALIDADE_MESES = 12

OrigemPerfil = Literal["questionario", "override"]


@dataclass(frozen=True)
class RegistroPerfil:
    versao_questionario: int
    data: dt.date
    valido_ate: dt.date
    respostas: Mapping[str, int] = field(hash=False)
    pontuacao: int
    vetos_aplicados: tuple[str, ...]
    perfil: NomePerfil

    def vencido(self, hoje: dt.date) -> bool:
        return hoje > self.valido_ate

    def para_dict(self) -> dict[str, Any]:
        return {
            "versao_questionario": self.versao_questionario,
            "data": self.data.isoformat(),
            "valido_ate": self.valido_ate.isoformat(),
            "respostas": dict(self.respostas),
            "pontuacao": self.pontuacao,
            "vetos_aplicados": list(self.vetos_aplicados),
            "perfil": self.perfil,
        }


def somar_meses(data: dt.date, meses: int) -> dt.date:
    """`data` + `meses`; o dia é limitado ao último do mês (29/02 + 12 meses = 28/02)."""
    indice = data.month - 1 + meses
    ano, mes = data.year + indice // 12, indice % 12 + 1
    return data.replace(year=ano, month=mes, day=min(data.day, calendar.monthrange(ano, mes)[1]))


def criar_registro(respostas: Mapping[str, int], data: dt.date) -> RegistroPerfil:
    c = classificar(respostas)
    return RegistroPerfil(
        versao_questionario=VERSAO_QUESTIONARIO,
        data=data,
        valido_ate=somar_meses(data, VALIDADE_MESES),
        respostas=dict(respostas),
        pontuacao=c.pontuacao,
        vetos_aplicados=c.vetos_aplicados,
        perfil=c.perfil,
    )


def gravar(registro: RegistroPerfil, caminho: Path) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(registro.para_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return caminho


def ler(caminho: Path) -> RegistroPerfil:
    """Lê e confere o JSON: a classificação gravada tem de bater com a recalculada das respostas.

    Arquivo ausente ⇒ `FileNotFoundError`; qualquer outra inconsistência ⇒ `ErroPerfil`.
    """
    texto = caminho.read_text(encoding="utf-8")
    refazer = "Rode `valuation perfil --refazer`."
    try:
        bruto = json.loads(texto)
        versao = int(bruto["versao_questionario"])
        if versao != VERSAO_QUESTIONARIO:
            raise ErroPerfil(
                f"{caminho} foi gravado com o questionário v{versao}; o atual é "
                f"v{VERSAO_QUESTIONARIO}. {refazer}"
            )
        respostas = {str(k): int(v) for k, v in bruto["respostas"].items()}
        data = dt.date.fromisoformat(bruto["data"])
        gravado = RegistroPerfil(
            versao_questionario=versao,
            data=data,
            valido_ate=dt.date.fromisoformat(bruto["valido_ate"]),
            respostas=respostas,
            pontuacao=int(bruto["pontuacao"]),
            vetos_aplicados=tuple(str(v) for v in bruto["vetos_aplicados"]),
            perfil=cast(NomePerfil, bruto["perfil"]),
        )
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        raise ErroPerfil(f"{caminho} inválido ({e}). {refazer}") from e
    if gravado.perfil not in get_args(NomePerfil):
        raise ErroPerfil(f"{caminho}: perfil desconhecido “{gravado.perfil}”. {refazer}")
    if gravado != criar_registro(respostas, data):
        raise ErroPerfil(
            f"{caminho}: pontuação, perfil, vetos ou validade não batem com as respostas "
            f"(arquivo editado à mão?). {refazer}"
        )
    return gravado


@dataclass(frozen=True)
class PerfilEfetivo:
    perfil: NomePerfil
    origem: OrigemPerfil
    registro: RegistroPerfil | None


def resolver_perfil(caminho: Path, hoje: dt.date, override: NomePerfil | None) -> PerfilEfetivo:
    """Perfil a usar numa execução: o override explícito vence; senão o JSON, se válido."""
    if override is not None:
        return PerfilEfetivo(override, "override", None)
    try:
        registro = ler(caminho)
    except FileNotFoundError as e:
        raise ErroPerfil(
            "Perfil do investidor não encontrado. Rode `valuation perfil` "
            "(ou use --perfil conservador|moderado|arrojado)."
        ) from e
    if registro.vencido(hoje):
        raise ErroPerfil(
            f"Perfil vencido em {registro.valido_ate}. Rode `valuation perfil --refazer` "
            "(ou use --perfil conservador|moderado|arrojado)."
        )
    return PerfilEfetivo(registro.perfil, "questionario", registro)
