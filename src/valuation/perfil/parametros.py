"""Mapeamento perfil → parâmetros (seção 8.4 do CLAUDE.md), lido de `settings.yaml > perfil`.

O perfil não altera fatos contábeis nem o custo de capital da empresa: só o desconto exigido, a
ponderação dos cenários, o horizonte de projeção explícita e o retorno mínimo.
"""

from __future__ import annotations

from dataclasses import dataclass

from valuation.config import ConfigPerfil
from valuation.perfil import NomePerfil


@dataclass(frozen=True)
class ParametrosPerfil:
    perfil: NomePerfil
    margem_seguranca: float
    peso_pessimista: float
    peso_base: float
    peso_otimista: float
    horizonte_anos: int
    hurdle_spread_selic: float

    def hurdle(self, selic: float) -> float:
        """Retorno mínimo exigido = Selic + spread do perfil (decimal)."""
        return selic + self.hurdle_spread_selic


def parametros_do_perfil(perfil: NomePerfil, config: ConfigPerfil) -> ParametrosPerfil:
    c = getattr(config, perfil)
    return ParametrosPerfil(
        perfil=perfil,
        margem_seguranca=c.margem_seguranca,
        peso_pessimista=c.pesos_cenarios.pessimista,
        peso_base=c.pesos_cenarios.base,
        peso_otimista=c.pesos_cenarios.otimista,
        horizonte_anos=c.horizonte_anos,
        hurdle_spread_selic=c.hurdle_spread_selic,
    )
