"""Carga e validação de `config/settings.yaml`.

Campos desconhecidos geram erro (`extra="forbid"`) para pegar erros de digitação no YAML.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
DIR_CONFIG = RAIZ_PROJETO / "config"
CAMINHO_SETTINGS = DIR_CONFIG / "settings.yaml"
CAMINHO_CADASTRO_MANUAL = DIR_CONFIG / "cadastro_manual.csv"
CAMINHO_UNIVERSO = DIR_CONFIG / "universo_ibovespa.csv"
CAMINHO_SETORES = DIR_CONFIG / "setores.yaml"
DIR_EMPRESAS = DIR_CONFIG / "empresas"
DIR_RAW = RAIZ_PROJETO / "data" / "raw"
DIR_PROCESSED = RAIZ_PROJETO / "data" / "processed"
CAMINHO_PERFIL = RAIZ_PROJETO / "perfil" / "perfil_investidor.json"
DIR_SAIDA = RAIZ_PROJETO / "saida"


class _Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ConfigCsv(_Modelo):
    separador: str = ";"
    decimal: str = ","
    encoding: str = "utf-8-sig"


class CacheTtlHoras(_Modelo):
    cvm: float = Field(gt=0)
    precos: float = Field(gt=0)
    macro: float = Field(gt=0)


class Impostos(_Modelo):
    aliquota_nominal: float = Field(ge=0, le=1)


class RfBrl(_Modelo):
    fonte: Literal["tesouro_prefixado_longo", "manual"]
    override: float | None = None

    @model_validator(mode="after")
    def _manual_exige_override(self) -> RfBrl:
        if self.fonte == "manual" and self.override is None:
            raise ValueError("rf_brl.fonte = manual exige rf_brl.override")
        return self


class ConfigBeta(_Modelo):
    metodo: Literal["regressao", "comparaveis", "manual"]
    janela_semanas: int = Field(gt=0)
    ajuste_blume: bool
    min_r2_aviso: float = Field(ge=0, le=1)


class EstruturaAlvo(_Modelo):
    metodo: Literal["mercado_atual", "setor", "manual"]
    divida_sobre_capital: float | None = Field(default=None, ge=0, lt=1)  # D/(D+E), só manual

    @model_validator(mode="after")
    def _manual_exige_valor(self) -> EstruturaAlvo:
        if self.metodo == "manual" and self.divida_sobre_capital is None:
            raise ValueError("estrutura_alvo.metodo = manual exige divida_sobre_capital")
        return self


class LimitesKd(_Modelo):
    """Faixa aceita para o Kd histórico, em spread sobre a Rf da moeda (decimal)."""

    spread_min: float
    spread_max: float

    @model_validator(mode="after")
    def _ordem(self) -> LimitesKd:
        if self.spread_min > self.spread_max:
            raise ValueError("kd.spread_min deve ser <= kd.spread_max")
        return self


class ConfigCustoCapital(_Modelo):
    metodo: Literal["brl_direto", "usd_crp"]
    rf_brl: RfBrl
    erp: float
    crp: float
    rf_usd: float
    inflacao_usd_lp: float
    beta: ConfigBeta
    kd: LimitesKd
    estrutura_alvo: EstruturaAlvo


class ConfigTerminal(_Modelo):
    g_nominal_max: float
    ronic: Literal["wacc", "roic_historico"] | float
    checagem_multiplo_saida: bool


class ConfigDcf(_Modelo):
    convencao_meio_periodo: bool
    alerta_tv_sobre_ev: float = Field(gt=0, le=1)


class ConfigSensibilidade(_Modelo):
    wacc_passo: float = Field(gt=0)
    wacc_faixa: float = Field(gt=0)
    g_passo: float = Field(gt=0)
    g_faixa: float = Field(gt=0)


class ValidacaoCruzada(_Modelo):
    """Tolerâncias da comparação entre duas fontes. Taxas em decimal (0,003 = 0,3 p.p.)."""

    preco_rel: float = Field(gt=0)
    cambio_rel: float = Field(gt=0)
    market_cap_rel: float = Field(gt=0)
    selic_abs: float = Field(gt=0)
    ipca_abs: float = Field(gt=0)
    rf_abs: float = Field(gt=0)


class PesosCenarios(_Modelo):
    pessimista: float = Field(ge=0, le=1)
    base: float = Field(ge=0, le=1)
    otimista: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _soma_um(self) -> PesosCenarios:
        if abs(self.pessimista + self.base + self.otimista - 1) > 1e-9:
            raise ValueError("pesos_cenarios devem somar 1")
        return self


class ParametrosPerfilConfig(_Modelo):
    """O que o perfil muda: desconto exigido, ponderação dos cenários, horizonte e hurdle."""

    margem_seguranca: float = Field(ge=0, lt=1)
    pesos_cenarios: PesosCenarios
    horizonte_anos: int = Field(gt=0, le=30)
    hurdle_spread_selic: float = Field(ge=0)  # hurdle = Selic + spread (decimal)


class ConfigPerfil(_Modelo):
    conservador: ParametrosPerfilConfig
    moderado: ParametrosPerfilConfig
    arrojado: ParametrosPerfilConfig


class Settings(_Modelo):
    versao: Literal[1]
    data_base: Literal["hoje"] | dt.date
    historico_anos: int = Field(gt=0, le=30)
    moeda_saida: Literal["BRL", "USD"]
    csv: ConfigCsv
    cache_ttl_horas: CacheTtlHoras
    impostos: Impostos
    custo_capital: ConfigCustoCapital
    terminal: ConfigTerminal
    dcf: ConfigDcf
    sensibilidade: ConfigSensibilidade
    validacao_cruzada: ValidacaoCruzada
    perfil: ConfigPerfil

    def resolver_data_base(self, hoje: dt.date) -> dt.date:
        """Data-base efetiva. `hoje` vem de quem chama (CLI), nunca de `date.today()` aqui."""
        return hoje if self.data_base == "hoje" else self.data_base


class Setor(_Modelo):
    """Entrada de `config/setores.yaml`. `pares` (tickers comparáveis) é preenchido na Fase 8."""

    descricao: str
    tipo_modelo: Literal["nao_financeira", "financeira"]
    commodity: bool
    pares: tuple[str, ...] = ()


class ErroConfiguracao(Exception):
    """Arquivo de configuração ausente ou inválido."""


def ler_yaml(caminho: Path) -> dict[str, Any]:
    """Mapeamento YAML no topo do arquivo; ausente, ilegível ou outro tipo ⇒ `ErroConfiguracao`."""
    if not caminho.is_file():
        raise ErroConfiguracao(f"Arquivo de configuração não encontrado: {caminho}")
    with caminho.open(encoding="utf-8") as f:
        try:
            bruto = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ErroConfiguracao(f"{caminho} não é YAML válido:\n{e}") from e
    if not isinstance(bruto, dict):
        raise ErroConfiguracao(f"{caminho} deve conter um mapeamento YAML no topo")
    return bruto


def carregar_settings(caminho: Path = CAMINHO_SETTINGS) -> Settings:
    bruto = ler_yaml(caminho)
    try:
        return Settings.model_validate(bruto)
    except ValueError as e:
        raise ErroConfiguracao(f"{caminho} inválido:\n{e}") from e


def carregar_setores(caminho: Path = CAMINHO_SETORES) -> dict[str, Setor]:
    bruto = ler_yaml(caminho)
    try:
        return {chave: Setor.model_validate(valor) for chave, valor in bruto.items()}
    except ValueError as e:
        raise ErroConfiguracao(f"{caminho} inválido:\n{e}") from e
