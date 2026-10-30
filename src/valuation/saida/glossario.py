"""Glossário das métricas exibidas na CLI e nos relatórios (`valuation glossario`, `--explicar`).

Dados estáticos, sem I/O. Cada termo tem definição, fórmula (ou origem) e como interpretar no
valuation. As chaves são minúsculas, sem acento e sem símbolos (`p_vp`, `ev_ebitda`).
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Termo:
    chave: str
    sigla: str
    nome: str
    grupo: str
    definicao: str
    formula: str
    interpretacao: str


GRUPOS = ("Custo de capital", "Modelos", "Múltiplos", "Perfil e decisão")

_T = Termo
TERMOS: tuple[Termo, ...] = (
    # --- Custo de capital -------------------------------------------------------------------
    _T(
        "wacc",
        "WACC",
        "Custo médio ponderado de capital",
        "Custo de capital",
        "Taxa mínima que credores e acionistas exigem para financiar os ativos operacionais.",
        "Ke x E/(D+E) + Kd x (1 - t) x D/(D+E)",
        "Taxa de desconto do FCFF. Quanto maior, menor o valor; precisa ser maior que g.",
    ),
    _T(
        "ke",
        "Ke",
        "Custo do capital próprio",
        "Custo de capital",
        "Retorno que o acionista exige pelo risco de manter a ação.",
        "Rf + β x ERP (CAPM, método brl_direto)",
        "Taxa de desconto do DDM. Em empresas não financeiras entra no WACC.",
    ),
    _T(
        "kd",
        "Kd",
        "Custo da dívida",
        "Custo de capital",
        "Taxa que a empresa paga para captar dívida, antes do imposto.",
        "Despesas financeiras / dívida bruta média (ou valor manual)",
        "O benefício fiscal entra no WACC como Kd x (1 - t).",
    ),
    _T(
        "beta",
        "β",
        "Beta",
        "Custo de capital",
        "Sensibilidade dos retornos da ação aos do Ibovespa.",
        "Regressão OLS dos retornos semanais (260 semanas), com ajuste de Blume: 0,67 x β + 0,33",
        "β > 1 amplifica o mercado. R² baixo ou ação pouco líquida tornam o beta pouco confiável.",
    ),
    _T(
        "erp",
        "ERP",
        "Prêmio de risco de mercado",
        "Custo de capital",
        "Retorno extra que a bolsa precisa oferecer sobre a taxa livre de risco.",
        "Parâmetro do usuário (settings.yaml)",
        "Premissa, não dado de mercado. Cada ponto percentual muda o Ke por β pontos.",
    ),
    _T(
        "rf",
        "Rf",
        "Taxa livre de risco",
        "Custo de capital",
        "Rendimento do Tesouro Prefixado longo (NTN-F), em BRL.",
        "Tesouro Transparente (ou override manual)",
        "Já embute o risco soberano do Brasil; não se soma risco-país por cima em BRL.",
    ),
    _T(
        "ke_implicito",
        "Ke implícito",
        "Ke implícito no preço",
        "Custo de capital",
        "Taxa de desconto que iguala o valor justo ao preço de mercado.",
        "Ke tal que valor(Ke) = preço (busca numérica)",
        "É o retorno anual que o mercado está precificando; compare com o hurdle do perfil.",
    ),
    _T(
        "wacc_implicito",
        "WACC implícito",
        "WACC implícito no preço",
        "Custo de capital",
        "WACC que iguala o valor justo ao preço de mercado.",
        "WACC tal que valor(WACC) = preço (busca numérica)",
        "Acima do WACC calculado, o preço é atraente; abaixo, o mercado paga mais que o modelo.",
    ),
    _T(
        "hurdle",
        "Hurdle",
        "Retorno mínimo exigido",
        "Perfil e decisão",
        "Retorno anual mínimo que o perfil do investidor aceita.",
        "Selic + spread do perfil (3, 5 ou 7 p.p.)",
        "Se o Ke implícito no preço fica abaixo dele, a ação não paga o risco esperado.",
    ),
    # --- Modelos ----------------------------------------------------------------------------
    _T(
        "g",
        "g",
        "Crescimento na perpetuidade",
        "Modelos",
        "Taxa nominal de crescimento dos fluxos depois do horizonte explícito.",
        "Parâmetro limitado por terminal.g_nominal_max",
        "Deve ser menor que o WACC (ou Ke) e compatível com PIB + inflação de longo prazo.",
    ),
    _T(
        "ronic",
        "RONIC",
        "Retorno sobre o novo capital investido",
        "Modelos",
        "Retorno dos investimentos feitos para sustentar o crescimento na perpetuidade.",
        "Reinvestimento terminal = g / RONIC",
        "RONIC = WACC (padrão) não cria valor no crescimento; acima dele, cria.",
    ),
    _T(
        "fcff",
        "FCFF",
        "Fluxo de caixa livre da firma",
        "Modelos",
        "Caixa operacional disponível a credores e acionistas depois de impostos e investimentos.",
        "EBIT x (1 - t) + D&A - Capex - ΔNWC",
        "Base do DCF das não financeiras.",
    ),
    _T(
        "nopat",
        "NOPAT",
        "Lucro operacional após impostos",
        "Modelos",
        "Resultado operacional como se a empresa não tivesse dívida.",
        "EBIT x (1 - t)",
        "Mede a geração operacional antes da estrutura de capital.",
    ),
    _T(
        "dividendos",
        "Dividendos",
        "Fluxo de dividendos projetado",
        "Modelos",
        "Parcela do lucro distribuída aos acionistas; é o fluxo do DDM das financeiras.",
        "payout x lucro líquido",
        "Respeita a restrição de capital regulatório só por premissa (o programa não vê Basileia).",
    ),
    _T(
        "vt",
        "VT",
        "Valor terminal",
        "Modelos",
        "Valor, na data final do horizonte, dos fluxos depois dele.",
        "FCFF(T+1) / (WACC - g), com FCFF(T+1) = NOPAT(T) x (1 + g) x (1 - g/RONIC)",
        "Concentra boa parte do valor; é o ponto mais sensível a WACC e g.",
    ),
    _T(
        "vt_ev",
        "VT/EV",
        "Peso do valor terminal no EV",
        "Modelos",
        "Fração do valor da firma que vem da perpetuidade.",
        "VP(VT) / EV",
        "Acima do alerta (dcf.alerta_tv_sobre_ev), depende mais da perpetuidade que dos anos "
        "projetados.",
    ),
    _T(
        "ev",
        "EV",
        "Valor da firma",
        "Modelos",
        "Valor presente das operações para todos os provedores de capital.",
        "VP(FCFF) + VP(VT)",
        "Passa pela ponte (dívida, caixa, minoritários) para chegar ao equity.",
    ),
    _T(
        "equity",
        "Equity",
        "Valor do patrimônio dos acionistas",
        "Modelos",
        "Valor que sobra aos acionistas depois da ponte.",
        "EV - dívida bruta + caixa - minoritários + coligadas - itens extras",
        "Dividido pelas ações em circulação dá o valor por ação.",
    ),
    _T(
        "valor_por_acao",
        "Valor por ação",
        "Valor justo por ação",
        "Modelos",
        "Valor intrínseco de cada ação em um cenário.",
        "Equity / ações em circulação (sem tesouraria)",
        "Ignora diluição e diferenças entre classes; é uma faixa, não um número exato.",
    ),
    _T(
        "ponderado",
        "Valor ponderado",
        "Valor justo ponderado",
        "Perfil e decisão",
        "Média dos valores por ação dos cenários, com os pesos do perfil.",
        "Σ peso do cenário x valor por ação do cenário",
        "Perfis conservadores dão mais peso ao cenário pessimista.",
    ),
    _T(
        "margem_seguranca",
        "Margem de segurança",
        "Margem de segurança",
        "Perfil e decisão",
        "Desconto exigido sobre o valor justo para cobrir erros do modelo.",
        "30% (conservador), 20% (moderado), 10% (arrojado)",
        "Define o preço máximo de compra.",
    ),
    _T(
        "preco_maximo",
        "Preço máximo",
        "Preço máximo de compra",
        "Perfil e decisão",
        "Maior preço que o perfil aceita pagar.",
        "Valor ponderado x (1 - margem de segurança)",
        "Preço de mercado abaixo dele é compatível com o perfil.",
    ),
    _T(
        "upside",
        "Upside",
        "Potencial de valorização",
        "Perfil e decisão",
        "Diferença entre o valor ponderado e o preço de mercado.",
        "Valor ponderado / preço - 1",
        "Positivo indica preço abaixo do valor justo do modelo; não é previsão de preço.",
    ),
    _T(
        "lucro_residual",
        "Lucro residual",
        "Lucro residual",
        "Modelos",
        "Lucro que excede o custo de oportunidade do capital próprio.",
        "Lucro líquido - Ke x PL (V0 = PL0 + Σ VP do lucro residual)",
        "Serve de checagem cruzada do DDM; divergência relevante aponta premissas inconsistentes.",
    ),
    _T(
        "roe",
        "ROE",
        "Retorno sobre o patrimônio líquido",
        "Modelos",
        "Lucro da controladora sobre o PL da controladora.",
        "Lucro líquido / PL médio",
        "ROE acima do Ke cria valor; o g sustentável é ROE x (1 - payout).",
    ),
    _T(
        "payout",
        "Payout",
        "Índice de distribuição",
        "Modelos",
        "Parcela do lucro paga como dividendos.",
        "Dividendos / lucro líquido",
        "No longo prazo converge para 1 - g/ROE.",
    ),
    # --- Múltiplos --------------------------------------------------------------------------
    _T(
        "p_l",
        "P/L",
        "Preço sobre lucro",
        "Múltiplos",
        "Quantos anos de lucro o mercado paga pela ação.",
        "Preço / lucro por ação (LTM)",
        "Descartado quando o lucro é negativo.",
    ),
    _T(
        "p_vp",
        "P/VP",
        "Preço sobre valor patrimonial",
        "Múltiplos",
        "Valor de mercado em relação ao patrimônio líquido.",
        "Market cap / PL da controladora",
        "Em bancos, relaciona-se ao ROE; o P/VP justificado é (ROE - g) / (Ke - g).",
    ),
    _T(
        "ev_ebitda",
        "EV/EBITDA",
        "Valor da firma sobre EBITDA",
        "Múltiplos",
        "Preço do negócio em anos de geração operacional de caixa, sem efeito da dívida.",
        "EV / EBITDA (LTM)",
        "Compara empresas com estruturas de capital diferentes.",
    ),
    _T(
        "ev_ebit",
        "EV/EBIT",
        "Valor da firma sobre EBIT",
        "Múltiplos",
        "Como o EV/EBITDA, depois de depreciação e amortização.",
        "EV / EBIT (LTM)",
        "Mais adequado quando o capex é alto.",
    ),
    _T(
        "ev_receita",
        "EV/Receita",
        "Valor da firma sobre receita",
        "Múltiplos",
        "Preço do negócio em relação ao faturamento.",
        "EV / receita líquida (LTM)",
        "Ignora margem; use com cuidado.",
    ),
    _T(
        "ev_fcf",
        "EV/FCF",
        "Valor da firma sobre fluxo de caixa livre",
        "Múltiplos",
        "Preço do negócio em relação ao FCFF histórico.",
        "EV / FCFF (LTM)",
        "Instável quando o capex ou o capital de giro oscilam.",
    ),
    _T(
        "dividend_yield",
        "Dividend yield",
        "Rendimento de dividendos",
        "Múltiplos",
        "Dividendos dos últimos 12 meses sobre o preço.",
        "Dividendos LTM / market cap",
        "Compare com a renda fixa; yield alto pode refletir queda de preço.",
    ),
    _T(
        "p25_p75",
        "P25 / Mediana / P75",
        "Quartis dos pares",
        "Múltiplos",
        "Estatísticas do múltiplo entre os pares do setor.",
        "Percentis 25, 50 e 75 (com winsorização)",
        "Delimitam a faixa de valor implícito; menos de 3 pares dá baixa confiança.",
    ),
    _T(
        "regressao_pvp_roe",
        "Regressão P/VP x ROE",
        "Regressão P/VP x ROE",
        "Múltiplos",
        "Reta ajustada entre P/VP e ROE dos bancos pares.",
        "P/VP = a + b x ROE",
        "Dá o P/VP esperado no ROE do alvo; R² baixo enfraquece o resultado.",
    ),
    _T(
        "ltm",
        "LTM",
        "Últimos 12 meses",
        "Múltiplos",
        "Soma móvel dos 12 meses mais recentes.",
        "Último exercício + YTD atual - YTD do mesmo período do ano anterior",
        "Base dos múltiplos, para refletir a empresa hoje.",
    ),
    _T(
        "ebitda",
        "EBITDA",
        "Resultado antes de juros, impostos, depreciação e amortização",
        "Múltiplos",
        "Proxy da geração operacional de caixa.",
        "EBIT + D&A",
        "Pode ser ajustado por não recorrentes definidos no YAML da empresa.",
    ),
)

_POR_CHAVE = {t.chave: t for t in TERMOS}


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return "".join(c if c.isalnum() else "_" for c in sem_acento.lower()).strip("_")


def buscar(texto: str) -> list[Termo]:
    """Termos cuja chave, sigla ou nome contêm `texto` (sem acento nem caixa); o exato vem só."""
    alvo = _normalizar(texto)
    if not alvo:
        return []
    exatos = [t for t in TERMOS if alvo in (t.chave, _normalizar(t.sigla))]
    if exatos:
        return exatos
    return [t for t in TERMOS if alvo in t.chave or alvo in _normalizar(t.nome)]


def termos(chaves: Iterable[str]) -> list[Termo]:
    """Termos pelas chaves exatas, na ordem dada; chave desconhecida é erro de programação."""
    return [_POR_CHAVE[c] for c in chaves]


def dicionario(chaves: Iterable[str] | None = None) -> dict[str, dict[str, str]]:
    """Dicionário serializável (`meta.json`): chave → sigla, nome, definição, fórmula, leitura."""
    escolhidos = TERMOS if chaves is None else termos(chaves)
    return {
        t.chave: {
            "sigla": t.sigla,
            "nome": t.nome,
            "definicao": t.definicao,
            "formula": t.formula,
            "interpretacao": t.interpretacao,
        }
        for t in escolhidos
    }


# Termos mostrados em cada tabela/comando, para a legenda de `--explicar`.
LEGENDA_DCF = (
    "wacc",
    "g",
    "ronic",
    "vt_ev",
    "ev",
    "equity",
    "valor_por_acao",
    "ponderado",
    "preco_maximo",
    "upside",
    "ke_implicito",
    "wacc_implicito",
    "hurdle",
)
LEGENDA_DDM = (
    "ke",
    "g",
    "roe",
    "payout",
    "dividendos",
    "vt",
    "lucro_residual",
    "p_vp",
    "valor_por_acao",
    "ponderado",
    "preco_maximo",
    "upside",
    "ke_implicito",
    "hurdle",
)
LEGENDA_MULTIPLOS = ("ltm", "p25_p75")
LEGENDA_WACC = ("rf", "erp", "beta", "ke", "kd", "wacc")


def legenda_multiplos(nomes: Iterable[str]) -> tuple[str, ...]:
    """Legenda dos múltiplos que aparecem na tabela, mais LTM e quartis."""
    return (*nomes, *LEGENDA_MULTIPLOS)
