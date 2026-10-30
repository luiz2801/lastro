"""Esquema de `config/empresas/{TICKER}.yaml` (seção 9.1 do CLAUDE.md e ADR 0006).

`sugerido` é recalculado pelo sugestor a partir do histórico a cada execução; um número (ou lista,
um valor por ano projetado) é sobrescrita manual. Campos desconhecidos geram erro.

`projecao` e `cenarios` dependem do `tipo_modelo`: FCFF (`ConfigProjecao`, `Cenarios`) nas não
financeiras e DDM (`ProjecaoFinanceira`, `CenariosFinanceira`, ADR 0012) nas financeiras. Use
`projecao_dcf`/`cenarios_dcf` ou `projecao_ddm`/`cenarios_ddm`, que conferem o tipo.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any, Final, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from valuation.config import DIR_EMPRESAS, ErroConfiguracao, ler_yaml
from valuation.contabil.nao_financeiras import AjustesContabeis, NaoRecorrente

SUGERIDO: Final = "sugerido"
Sugerido = Literal["sugerido"]
Fracao = Annotated[float, Field(ge=0, le=1)]
FracaoComSinal = Annotated[float, Field(ge=-1, le=1)]
Delta = Annotated[float, Field(ge=-0.5, le=0.5)]


class _Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Trajetoria(_Modelo):
    """Valor no 1º ano projetado e no último, com convergência linear entre eles."""

    inicio: FracaoComSinal | Sugerido = SUGERIDO
    fim: FracaoComSinal | Sugerido = SUGERIDO
    curva: Literal["linear"] = "linear"


# Lista explícita: um valor por ano projetado, a partir do exercício seguinte ao último histórico.
Caminho = Trajetoria | tuple[FracaoComSinal, ...]


class Receita(_Modelo):
    crescimento: Caminho = Trajetoria()


class Margens(_Modelo):
    ebitda: Caminho = Trajetoria()


class AliquotaImposto(_Modelo):
    valor: Fracao | Sugerido = SUGERIDO
    limite_superior: Fracao | None = None  # None ⇒ settings.impostos.aliquota_nominal

    @model_validator(mode="after")
    def _valor_no_limite(self) -> AliquotaImposto:
        if (
            isinstance(self.valor, float)
            and self.limite_superior is not None
            and self.valor > self.limite_superior
        ):
            raise ValueError("aliquota_imposto.valor acima de limite_superior")
        return self


class TerminalEmpresa(_Modelo):
    g_nominal: float | None = None  # None ⇒ settings.terminal.g_nominal_max
    ronic: Literal["wacc", "roic_historico"] | float | None = None  # None ⇒ settings


class ConfigProjecao(_Modelo):
    horizonte_anos: Literal["perfil"] | Annotated[int, Field(gt=0, le=30)] = "perfil"
    receita: Receita = Receita()
    margens: Margens = Margens()
    da_sobre_receita: Fracao | Sugerido = SUGERIDO
    capex_sobre_receita: Fracao | Sugerido = SUGERIDO
    nwc_sobre_receita: FracaoComSinal | Sugerido = SUGERIDO
    # Proxy da reposição dos direitos de uso (IFRS 16 = dívida); ADR 0006.
    arrendamento_sobre_receita: Fracao | Sugerido = SUGERIDO
    aliquota_imposto: AliquotaImposto = AliquotaImposto()
    terminal: TerminalEmpresa = TerminalEmpresa()


class DeltaCenario(_Modelo):
    """Deltas somados às premissas do cenário base, em decimal (0,02 = 2 p.p.)."""

    crescimento_pp: Delta | Sugerido = SUGERIDO
    margem_ebitda_pp: Delta | Sugerido = SUGERIDO
    capex_pp: Delta | Sugerido = SUGERIDO


class Cenarios(_Modelo):
    pessimista: DeltaCenario = DeltaCenario()
    otimista: DeltaCenario = DeltaCenario()


class TerminalFinanceira(_Modelo):
    g_nominal: float | None = None  # None ⇒ settings.terminal.g_nominal_max


class ProjecaoFinanceira(_Modelo):
    """DDM (seção 11.3 do CLAUDE.md): o ROE converge linearmente para o de longo prazo (`roe.fim`)
    e o payout, de `payout_inicio` para 1 - g / ROE de longo prazo. Lista de ROE: um valor por
    ano a partir do primeiro exercício aberto na data-base."""

    horizonte_anos: Literal["perfil"] | Annotated[int, Field(gt=0, le=30)] = "perfil"
    roe: Caminho = Trajetoria()
    payout_inicio: Fracao | Sugerido = SUGERIDO
    terminal: TerminalFinanceira = TerminalFinanceira()


class DeltaCenarioFinanceira(_Modelo):
    """Delta somado ao ROE de todos os anos, inclusive o de longo prazo (0,02 = 2 p.p.)."""

    roe_pp: Delta | Sugerido = SUGERIDO


class CenariosFinanceira(_Modelo):
    pessimista: DeltaCenarioFinanceira = DeltaCenarioFinanceira()
    otimista: DeltaCenarioFinanceira = DeltaCenarioFinanceira()


class NaoRecorrenteConfig(_Modelo):
    ano: int
    conta: Literal["ebit"] = "ebit"
    valor: float  # unidades da moeda de reporte; ganho > 0, perda < 0
    descricao: str = ""


class Ajustes(_Modelo):
    consolidado: bool = True
    ifrs16: Literal["divida", "ignorar"] = "divida"
    capex_equivalente_arrendamento: bool = True
    minoritarios: Literal["contabil", "multiplo_pvp"] = "contabil"
    coligadas: Literal["somar_investimento_contabil", "manter_no_ebit"] = (
        "somar_investimento_contabil"
    )
    caixa_extra: tuple[str, ...] = ()
    divida_extra: tuple[str, ...] = ()
    nao_recorrentes: tuple[NaoRecorrenteConfig, ...] = ()
    mapeamento_extra: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)


class Pares(_Modelo):
    setor: str | None = None  # chave em config/setores.yaml
    incluir: tuple[str, ...] = ()
    excluir: tuple[str, ...] = ()


class _MetodoComValor(_Modelo):
    valor: float | None = None

    @model_validator(mode="after")
    def _manual_exige_valor(self) -> _MetodoComValor:
        if getattr(self, "metodo", None) == "manual" and self.valor is None:
            raise ValueError("metodo = manual exige valor")
        return self


class MetodoBeta(_MetodoComValor):
    metodo: Literal["regressao", "comparaveis", "manual"] = "regressao"


class MetodoKd(_MetodoComValor):
    metodo: Literal["historico", "manual"] = "historico"


class CustoCapitalEmpresa(_Modelo):
    beta: MetodoBeta = MetodoBeta()
    kd: MetodoKd = MetodoKd()


# Ajustes que valem para as financeiras (os demais são do FCFF e da ponte EV -> equity).
AJUSTES_FINANCEIRA = frozenset({"consolidado", "mapeamento_extra"})


class PremissasEmpresa(_Modelo):
    ticker: str
    tipo_modelo: Literal["nao_financeira", "financeira"]
    classes_acao: tuple[str, ...] = Field(min_length=1)
    moeda_relatorio: Literal["auto", "BRL", "USD"] = "auto"
    ajustes: Ajustes = Ajustes()
    projecao: ConfigProjecao | ProjecaoFinanceira = ConfigProjecao()
    cenarios: Cenarios | CenariosFinanceira = Cenarios()
    pares: Pares = Pares()
    custo_capital: CustoCapitalEmpresa = CustoCapitalEmpresa()

    @model_validator(mode="before")
    @classmethod
    def _blocos_do_tipo(cls, dados: Any) -> Any:
        """`projecao` e `cenarios` com o esquema do `tipo_modelo` (FCFF ou DDM)."""
        if not isinstance(dados, dict):
            return dados
        financeira = dados.get("tipo_modelo") == "financeira"
        modelos: dict[str, type[_Modelo]] = {
            "projecao": ProjecaoFinanceira if financeira else ConfigProjecao,
            "cenarios": CenariosFinanceira if financeira else Cenarios,
        }
        saida = dict(dados)
        for chave, modelo in modelos.items():
            valor = saida.get(chave)
            if not isinstance(valor, _Modelo):
                saida[chave] = modelo.model_validate({} if valor is None else valor)
        return saida

    @model_validator(mode="after")
    def _so_o_que_se_aplica(self) -> PremissasEmpresa:
        if self.tipo_modelo != "financeira":
            return self
        sobra = self.ajustes.model_fields_set - AJUSTES_FINANCEIRA
        if sobra:
            raise ValueError(
                f"ajustes {', '.join(sorted(sobra))} não se aplicam a financeiras "
                f"(só {', '.join(sorted(AJUSTES_FINANCEIRA))})"
            )
        if "kd" in self.custo_capital.model_fields_set:
            raise ValueError("custo_capital.kd não se aplica a financeiras (o DDM usa só o Ke)")
        return self

    @property
    def projecao_dcf(self) -> ConfigProjecao:
        return _do_tipo(self.projecao, ConfigProjecao, self)

    @property
    def cenarios_dcf(self) -> Cenarios:
        return _do_tipo(self.cenarios, Cenarios, self)

    @property
    def projecao_ddm(self) -> ProjecaoFinanceira:
        return _do_tipo(self.projecao, ProjecaoFinanceira, self)

    @property
    def cenarios_ddm(self) -> CenariosFinanceira:
        return _do_tipo(self.cenarios, CenariosFinanceira, self)


_T = TypeVar("_T")


def _do_tipo(valor: object, tipo: type[_T], premissas: PremissasEmpresa) -> _T:
    if not isinstance(valor, tipo):
        modelo = "DDM" if tipo in (ProjecaoFinanceira, CenariosFinanceira) else "FCFF"
        raise ErroConfiguracao(
            f"{premissas.ticker} é {premissas.tipo_modelo}: premissas de {modelo} não se aplicam."
        )
    return valor


def caminho_premissas(ticker: str, dir_empresas: Path = DIR_EMPRESAS) -> Path:
    return dir_empresas / f"{ticker.upper()}.yaml"


def carregar_premissas(caminho: Path) -> PremissasEmpresa:
    bruto = ler_yaml(caminho)
    try:
        premissas = PremissasEmpresa.model_validate(bruto)
    except ValueError as e:
        raise ErroConfiguracao(f"{caminho} inválido:\n{e}") from e
    if premissas.ticker.upper() != caminho.stem.upper():
        raise ErroConfiguracao(f"{caminho}: ticker {premissas.ticker!r} difere do nome do arquivo.")
    return premissas


def premissas_padrao(
    ticker: str, tipo_modelo: Literal["nao_financeira", "financeira"], classes_acao: Sequence[str]
) -> PremissasEmpresa:
    """Premissas de uma empresa sem YAML: tudo `sugerido` e ajustes padrão do guia."""
    return PremissasEmpresa(
        ticker=ticker.upper(), tipo_modelo=tipo_modelo, classes_acao=tuple(classes_acao)
    )


def conferir_cadastro(
    premissas: PremissasEmpresa, tickers: Sequence[str], tipo_modelo: str
) -> None:
    """O YAML tem de descrever a mesma empresa do cadastro (classes de ação e tipo de modelo)."""
    if set(premissas.classes_acao) != set(tickers):
        raise ErroConfiguracao(
            f"classes_acao de {premissas.ticker} ({', '.join(premissas.classes_acao)}) diferem "
            f"do cadastro ({', '.join(tickers)})."
        )
    if premissas.tipo_modelo != tipo_modelo:
        raise ErroConfiguracao(
            f"tipo_modelo de {premissas.ticker} é {premissas.tipo_modelo} no YAML e "
            f"{tipo_modelo} no cadastro (corrija um dos dois)."
        )


def ajustes_contabeis(ajustes: Ajustes) -> AjustesContabeis:
    """Os ajustes do YAML que a camada contábil aplica às métricas históricas."""
    return AjustesContabeis(
        ifrs16=ajustes.ifrs16,
        capex_equivalente_arrendamento=ajustes.capex_equivalente_arrendamento,
        coligadas=ajustes.coligadas,
        nao_recorrentes=tuple(
            NaoRecorrente(ano=n.ano, valor=n.valor, descricao=n.descricao)
            for n in ajustes.nao_recorrentes
        ),
        caixa_extra=ajustes.caixa_extra,
        divida_extra=ajustes.divida_extra,
    )
