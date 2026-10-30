"""Artefatos de reprodutibilidade e dados dos gráficos (seção 13 do CLAUDE.md, ADR 0016).

`meta.json` (versões, fontes, perfil, moeda), `premissas_usadas.yaml` (cópia final das premissas),
`qa.json`, `historico.csv`, e as estruturas que alimentam os gráficos: o detalhe de cada cenário
(`CenarioSaida`) e as faixas do football field.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import platform
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import yaml

from valuation.modelos import dcf, ddm
from valuation.modelos import multiplos as mt
from valuation.modelos import ponte as pt
from valuation.saida import real


@dataclass(frozen=True)
class CenarioSaida:
    """O que os gráficos e o relatório real precisam de um cenário, nas unidades da moeda."""

    valor_por_acao: float  # BRL
    fluxos: pd.DataFrame  # índice ano; colunas `fluxo` e `tau`
    projecao: pd.DataFrame  # projeção completa (anos inteiros, sem a fração)
    vp_fluxos: float
    vp_terminal: float
    valor_terminal: float
    taxa: float
    g: float
    ponte: pd.DataFrame | None  # `ponte.tabela` (só DCF)

    def para_real(self) -> real.FluxosCenario:
        return real.FluxosCenario(
            self.fluxos, self.valor_terminal, self.taxa, self.g, self.valor_por_acao
        )


def cenario_dcf(av: dcf.Avaliacao) -> CenarioSaida:
    r = av.dcf
    return CenarioSaida(
        valor_por_acao=av.valor_por_acao,
        fluxos=r.fluxos[["fluxo", "tau"]],
        projecao=av.projecao,
        vp_fluxos=r.vp_fluxos,
        vp_terminal=r.vp_terminal,
        valor_terminal=r.valor_terminal,
        taxa=r.wacc,
        g=r.g,
        ponte=pt.tabela(av.ponte),
    )


def cenario_ddm(av: ddm.AvaliacaoDDM) -> CenarioSaida:
    r = av.ddm
    return CenarioSaida(
        valor_por_acao=av.valor_por_acao,
        fluxos=r.fluxos[["dividendos", "tau"]].rename(columns={"dividendos": "fluxo"}),
        projecao=av.projecao,
        vp_fluxos=r.vp_dividendos,
        vp_terminal=r.vp_terminal,
        valor_terminal=r.valor_terminal,
        taxa=r.ke,
        g=r.g,
        ponte=None,
    )


# --- JSON, YAML e hash ------------------------------------------------------------------------


def serializavel(obj: Any) -> Any:
    """Converte dataclasses, tuplas, datas e escalares do numpy em tipos de JSON/YAML."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return serializavel(dataclasses.asdict(obj))
    if isinstance(obj, Mapping):
        return {str(k): serializavel(v) for k, v in obj.items()}
    if isinstance(obj, Sequence) and not isinstance(obj, str):
        return [serializavel(v) for v in obj]
    if isinstance(obj, dt.date | dt.datetime):
        return obj.isoformat()
    if isinstance(obj, np.generic):
        return serializavel(obj.item())
    if isinstance(obj, float) and not np.isfinite(obj):
        return None
    return obj


def gravar_json(dados: Mapping[str, Any], caminho: Path) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(serializavel(dados), ensure_ascii=False, indent=2)
    caminho.write_text(texto + "\n", encoding="utf-8")
    return caminho


def gravar_yaml(dados: Mapping[str, Any], caminho: Path, cabecalho: str = "") -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    corpo = yaml.safe_dump(
        serializavel(dados), allow_unicode=True, sort_keys=False, default_flow_style=None
    )
    caminho.write_text(cabecalho + corpo, encoding="utf-8")
    return caminho


def sha256_arquivo(caminho: Path) -> str | None:
    if not caminho.is_file():
        return None
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def commit_git(raiz: Path) -> str | None:
    """Hash do commit do código e `+sujo` se houver alterações; None fora de um repositório."""
    try:
        h = subprocess.run(
            ["git", "-C", str(raiz), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
        sujo = subprocess.run(
            ["git", "-C", str(raiz), "status", "--porcelain", "--untracked-files=no"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return f"{h}+sujo" if sujo else h


def fontes_cvm(dir_raw: Path) -> list[dict[str, Any]]:
    """URL, data e hash de cada arquivo da CVM em cache (`.meta.json` do `http.baixar`)."""
    itens: list[dict[str, Any]] = []
    for pasta in ("CAD", "DFP", "ITR", "FCA"):
        for caminho in sorted((dir_raw / pasta).rglob("*.meta.json")):
            m = json.loads(caminho.read_text(encoding="utf-8"))
            if "url" in m:
                itens.append(
                    {k: m.get(k) for k in ("url", "baixado_em", "sha256", "tamanho_bytes")}
                )
    return itens


def montar_meta(
    *,
    versao: str,
    agora: dt.datetime,
    comando: str,
    commit: str | None,
    ticker: str,
    data_base: dt.date,
    modelo: str,
    perfil: str,
    origem_perfil: str,
    moeda_reporte: str,
    cambio: float,
    cenarios: Sequence[str],
    referencia: str,
    taxa_desconto: Mapping[str, float],
    fontes: Mapping[str, Any],
    hash_contas: str | None,
    arquivos: Sequence[str],
    avisos: Sequence[str],
) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "data_base": data_base,
        "gerado_em": agora,
        "comando": comando,
        "codigo": {
            "versao": versao,
            "commit": commit,
            "python": platform.python_version(),
            "sistema": platform.platform(),
        },
        "modelo": modelo,
        "perfil": {"nome": perfil, "origem": origem_perfil},
        "moeda_reporte": moeda_reporte,
        "cambio_brl_por_unidade": cambio,
        "cenarios": list(cenarios),
        "cenario_de_referencia": referencia,
        "taxa_desconto": dict(taxa_desconto),
        "fontes": dict(fontes),
        "hash_contas_padronizadas": hash_contas,
        "arquivos": list(arquivos),
        "avisos": list(avisos),
    }


# --- Histórico --------------------------------------------------------------------------------


def tabela_historico(anual: pd.DataFrame, ltm: pd.Series) -> pd.DataFrame:
    """`historico.csv`: uma linha por exercício e a linha LTM (`periodo`, `tipo`, métricas)."""
    df = anual.copy()
    df.insert(0, "tipo", "anual")
    df.insert(0, "periodo", [str(getattr(i, "year", i)) for i in df.index])
    linha = ltm.to_frame().T
    linha.insert(0, "tipo", "ltm")
    linha.insert(0, "periodo", f"LTM {pd.Timestamp(str(ltm.name)):%m/%Y}")
    return pd.concat([df.reset_index(drop=True), linha.reset_index(drop=True)], ignore_index=True)


# --- Football field ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Faixa:
    rotulo: str
    minimo: float
    maximo: float
    ponto: float | None = None  # mediana, valor base…
    aviso: bool = False  # baixa confiança


def faixas_football(
    cenarios: Mapping[str, float],
    matriz: pd.DataFrame,
    multiplos: mt.ResultadoMultiplos | None,
    faixa_52s: tuple[float, float] | None,
    *,
    modelo: str,
    rotulo_matriz: str,
) -> list[Faixa]:
    """Barras do football field (seção 12): modelo por cenário, faixa da sensibilidade, múltiplos
    pelos quartis dos pares (P25 a P75, ponto na mediana) e a faixa de 52 semanas."""
    nome = modelo.upper()
    faixas: list[Faixa] = []
    if len(cenarios) > 1:
        faixas.append(
            Faixa(
                f"{nome} (pess. a otim.)",
                min(cenarios.values()),
                max(cenarios.values()),
                cenarios.get("base"),
            )
        )
    valores = matriz.to_numpy(dtype=float)
    valores = valores[np.isfinite(valores)]
    if valores.size:
        faixas.append(Faixa(f"{nome} ({rotulo_matriz})", valores.min(), valores.max()))
    if multiplos is not None:
        for n in multiplos.nomes:
            tab = multiplos.implicitos
            lo, md, hi = (float(cast(float, tab.at[n, f"valor_{s}"])) for s in mt.ESTATISTICAS)
            if not np.isfinite([lo, hi]).all():
                continue
            faixas.append(
                Faixa(
                    mt.ROTULOS[n],
                    min(lo, hi),
                    max(lo, hi),
                    md if np.isfinite(md) else None,
                    aviso=bool(tab.at[n, "confianca"] == "baixa"),
                )
            )
    if faixa_52s is not None:
        faixas.append(Faixa("Faixa de 52 semanas", faixa_52s[0], faixa_52s[1]))
    return faixas


def faixa_52_semanas(historico: pd.DataFrame, base: dt.date) -> tuple[float, float] | None:
    """Mínima e máxima do fechamento (não ajustado) nos 52 semanas até a data-base."""
    if historico.empty:
        return None
    idx = pd.to_datetime(historico.index)
    janela = historico.loc[
        (idx > pd.Timestamp(base) - pd.Timedelta(weeks=52)) & (idx <= pd.Timestamp(base)), "close"
    ].dropna()
    return (float(janela.min()), float(janela.max())) if len(janela) else None
