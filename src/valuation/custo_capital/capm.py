"""Custo do capital próprio (seção 10.2 do guia).

- `brl_direto`: Ke = Rf_BRL + beta x ERP. A Rf (NTN-F longa) já embute o risco soberano: não se
  soma risco-país.
- `usd_crp`: Ke_USD = Rf_USD + beta x ERP + CRP; convertido para BRL por Fisher quando a empresa
  reporta em BRL. Obrigatório para quem reporta em USD (fluxo e taxa na mesma moeda).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from valuation.custo_capital import ErroCustoCapital

MetodoKe = Literal["brl_direto", "usd_crp"]
Moeda = Literal["BRL", "USD"]


@dataclass(frozen=True)
class CustoCapitalProprio:
    """`ke` está na moeda de reporte; `ke_usd` só existe no método `usd_crp`."""

    metodo: MetodoKe
    moeda: Moeda
    ke: float
    beta: float
    erp: float
    rf: float  # Rf da moeda do método (BRL no brl_direto, USD no usd_crp)
    crp: float = 0.0
    ke_usd: float | None = None
    inflacao_brl: float | None = None
    inflacao_usd: float | None = None


def converter_taxa(taxa: float, inflacao_destino: float, inflacao_origem: float) -> float:
    """Fisher: (1 + taxa) x (1 + pi_destino) / (1 + pi_origem) - 1."""
    return (1 + taxa) * (1 + inflacao_destino) / (1 + inflacao_origem) - 1


def metodo_efetivo(metodo: MetodoKe, moeda: Moeda) -> tuple[MetodoKe, str | None]:
    """Quem reporta em USD usa `usd_crp`, seja qual for o `settings` (com aviso)."""
    if moeda == "USD" and metodo != "usd_crp":
        return "usd_crp", "Empresa reporta em USD: Ke pelo método usd_crp (seção 10.2)."
    return metodo, None


def custo_capital_proprio(
    *,
    metodo: MetodoKe,
    moeda: Moeda,
    beta: float,
    erp: float,
    rf_brl: float,
    rf_usd: float,
    crp: float,
    inflacao_usd: float,
    inflacao_brl: float | None,
) -> CustoCapitalProprio:
    """Ke na moeda de reporte. `inflacao_brl` (IPCA de longo prazo) só é exigida em `usd_crp`
    para empresa que reporta em BRL."""
    if metodo == "brl_direto":
        if moeda != "BRL":
            raise ErroCustoCapital("brl_direto só vale para empresa que reporta em BRL.")
        return CustoCapitalProprio(metodo, moeda, rf_brl + beta * erp, beta, erp, rf_brl)
    ke_usd = rf_usd + beta * erp + crp
    if moeda == "USD":
        return CustoCapitalProprio(
            metodo, moeda, ke_usd, beta, erp, rf_usd, crp, ke_usd, None, inflacao_usd
        )
    if inflacao_brl is None:
        raise ErroCustoCapital("usd_crp em BRL exige a inflação brasileira de longo prazo.")
    return CustoCapitalProprio(
        metodo,
        moeda,
        converter_taxa(ke_usd, inflacao_brl, inflacao_usd),
        beta,
        erp,
        rf_usd,
        crp,
        ke_usd,
        inflacao_brl,
        inflacao_usd,
    )
