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


GRUPOS = ("Custo de capital", "Modelos", "Múltiplos", "Indicadores", "Perfil e decisão")

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
        "preco_teto_bazin",
        "Teto Bazin",
        "Preço teto de Bazin",
        "Perfil e decisão",
        "Maior preço que ainda rende o yield mínimo de dividendos, pela regra de Décio Bazin.",
        "Média dos dividendos e JCP pagos (DFC) nos últimos exercícios (5, padrão) / ações / "
        "yield mínimo (6%, padrão)",
        "Informativo e só para pagadoras: ignora crescimento e risco. A recomendação usa o "
        "preço máximo de compra do perfil.",
    ),
    _T(
        "recomendacao",
        "Recomendação",
        "Recomendação do modelo",
        "Perfil e decisão",
        "Leitura do preço contra o valor justo e o retorno mínimo do perfil.",
        "Compra: preço <= preço máximo e Ke implícito >= hurdle; venda: preço > valor "
        "ponderado; manter: o resto",
        "Confiança baixa rebaixa a compra para manter. Estudo pessoal, não é recomendação de "
        "investimento.",
    ),
    _T(
        "confianca",
        "Confiança",
        "Confiança do resultado",
        "Perfil e decisão",
        "Se o resultado tem sinais de fragilidade nos dados ou no modelo.",
        "Baixa com erro de QA, VT acima do alerta, menos pares que o mínimo ou R² do beta "
        "abaixo do mínimo",
        "Com confiança baixa, revise os motivos antes de usar o valor.",
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
        "Lucro da controladora / PL da controladora do início do período",
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
    # --- Indicadores ------------------------------------------------------------------------
    _T(
        "margem_liquida",
        "Margem líquida",
        "Margem líquida",
        "Indicadores",
        "Quanto da receita líquida sobra como lucro para os acionistas da controladora.",
        "Lucro líquido da controladora / receita líquida",
        "Compare com a própria história e com pares do setor; commodities oscilam com o ciclo.",
    ),
    _T(
        "margem_ebitda",
        "Margem EBITDA",
        "Margem EBITDA",
        "Indicadores",
        "Geração operacional de caixa por real de receita, antes de depreciação e impostos.",
        "EBITDA (EBIT + D&A) / receita líquida",
        "Mostra a eficiência operacional; é a margem que o DCF projeta e faz reverter à mediana.",
    ),
    _T(
        "divida_bruta_pl",
        "Dív. bruta/PL",
        "Dívida bruta sobre patrimônio líquido",
        "Indicadores",
        "Quanto a empresa deve para cada real de capital próprio.",
        "Dívida bruta / PL total; arrendamento na dívida conforme ifrs16",
        "Quanto maior, mais alavancada. Compare com o setor; indefinido (—) se o PL é <= 0.",
    ),
    _T(
        "divida_liquida_pl",
        "Dív. líq./PL",
        "Dívida líquida sobre patrimônio líquido",
        "Indicadores",
        "Dívida depois do caixa, para cada real de capital próprio.",
        "(Dívida bruta - caixa e aplicações) / PL total",
        "Negativo = caixa maior que a dívida. Indefinido (—) se o PL é <= 0.",
    ),
    _T(
        "divida_bruta_ebitda",
        "Dív. bruta/EBITDA",
        "Dívida bruta sobre EBITDA",
        "Indicadores",
        "Em quantos anos de EBITDA a dívida seria paga, sem usar o caixa.",
        "Dívida bruta / EBITDA ajustado",
        "Maior que a dívida líquida/EBITDA quando há caixa; mostra o risco de refinanciar.",
    ),
    _T(
        "divida_liquida_ebit",
        "Dív. líq./EBIT",
        "Dívida líquida sobre EBIT",
        "Indicadores",
        "Como a dívida líquida/EBITDA, mas descontando a depreciação.",
        "(Dívida bruta - caixa e aplicações) / EBIT ajustado",
        "Mais exigente em empresa intensiva em capital; indefinido (—) se o EBIT é <= 0.",
    ),
    _T(
        "cobertura_juros",
        "Cobertura",
        "Cobertura de juros",
        "Indicadores",
        "Quantas vezes o lucro operacional paga as despesas financeiras.",
        "EBIT ajustado / despesas financeiras da DRE (3.06.02)",
        "Abaixo de 1,5x pede atenção. A despesa inclui variação cambial e juros de arrendamento; "
        "indefinido (—) se a DRE não a abre.",
    ),
    _T(
        "passivos_ativos",
        "Passivos/Ativos",
        "Passivos sobre ativos",
        "Indicadores",
        "Parte dos ativos financiada por terceiros.",
        "(Passivo circulante + não circulante) / ativo total",
        "Não usa a conta 2 da CVM, que inclui o PL e é sempre igual ao ativo.",
    ),
    _T(
        "pl_ativos",
        "PL/Ativos",
        "Patrimônio líquido sobre ativos",
        "Indicadores",
        "Parte dos ativos financiada pelos sócios.",
        "PL total / ativo total",
        "Complementa Passivos/Ativos: os dois somam 100%.",
    ),
    _T(
        "perfil_divida",
        "Dív. CP/bruta",
        "Perfil da dívida",
        "Indicadores",
        "Quanto da dívida vence em até 12 meses.",
        "Dívida de curto prazo / dívida bruta; arrendamento conforme ifrs16",
        "Alto com pouco caixa é risco de refinanciamento.",
    ),
    _T(
        "liquidez_corrente",
        "Liq. corrente",
        "Liquidez corrente",
        "Indicadores",
        "Ativo de curto prazo para cada real de passivo de curto prazo.",
        "Ativo circulante / passivo circulante",
        "Abaixo de 1 pede atenção, salvo setores de giro favorável (varejo, por exemplo).",
    ),
    _T(
        "liquidez_seca",
        "Liq. seca",
        "Liquidez seca",
        "Indicadores",
        "Liquidez corrente sem contar os estoques.",
        "(Ativo circulante - estoques) / passivo circulante",
        "Mais conservadora quando o estoque demora a virar caixa.",
    ),
    _T(
        "liquidez_imediata",
        "Liq. imediata",
        "Liquidez imediata",
        "Indicadores",
        "Caixa disponível para cada real de passivo de curto prazo.",
        "Caixa e aplicações / passivo circulante",
        "Costuma ficar bem abaixo de 1; compare com o histórico da própria empresa.",
    ),
    _T(
        "liquidez_geral",
        "Liq. geral",
        "Liquidez geral",
        "Indicadores",
        "Direitos contra obrigações de curto e de longo prazo.",
        "(Ativo circulante + realizável a LP) / (passivo circulante + não circulante)",
        "Abaixo de 1 é comum em empresa intensiva em imobilizado.",
    ),
    _T(
        "caixa_aplicacoes",
        "Caixa",
        "Caixa e aplicações",
        "Indicadores",
        "Caixa e aplicações financeiras de curto prazo.",
        "Caixa + aplicações financeiras + caixa_extra do YAML; o mesmo da dívida líquida",
        "Valor em R$ milhões; olhe em conjunto com a dívida de curto prazo.",
    ),
    _T(
        "caixa_divida_cp",
        "Caixa/Dív. CP",
        "Caixa sobre dívida de curto prazo",
        "Indicadores",
        "Quantas vezes o caixa paga a dívida que vence em 12 meses.",
        "Caixa e aplicações / dívida de curto prazo",
        "Abaixo de 1 depende de refinanciar ou de gerar caixa.",
    ),
    _T(
        "caixa_ativo",
        "Caixa/Ativos",
        "Caixa sobre ativos",
        "Indicadores",
        "Parte dos ativos mantida em caixa.",
        "Caixa e aplicações / ativo total",
        "Muito alto pode ser reserva ou falta de onde investir.",
    ),
    _T(
        "conversao_cfo_ebitda",
        "CFO/EBITDA",
        "Conversão de EBITDA em caixa",
        "Indicadores",
        "Quanto do EBITDA virou caixa operacional.",
        "Caixa das operações / EBITDA ajustado",
        "Persistente abaixo de 100% sugere lucro que não vira caixa, ou giro consumindo recursos.",
    ),
    _T(
        "conversao_fcf_lucro",
        "FCF/Lucro",
        "Conversão de lucro em caixa livre",
        "Indicadores",
        "Quanto do lucro sobrou em caixa depois do capex.",
        "(Caixa das operações - capex) / lucro da controladora",
        "Acima de 100% é forte; indefinido (—) se o lucro é <= 0.",
    ),
    _T(
        "divida_liquida_ebitda",
        "Dív. líq./EBITDA",
        "Dívida líquida sobre EBITDA",
        "Indicadores",
        "Em quantos anos de EBITDA a dívida líquida seria paga.",
        "(Dívida bruta - caixa e aplicações) / EBITDA ajustado; arrendamento na dívida (IFRS 16)",
        "Negativo = caixa líquido. Acima de 3x pede atenção; indefinido (—) se o EBITDA é <= 0.",
    ),
    _T(
        "roic",
        "ROIC",
        "Retorno sobre o capital investido",
        "Indicadores",
        "Retorno operacional após impostos sobre o capital que financia o negócio.",
        "NOPAT / média do capital investido (PL + dívida líquida)",
        "Acima do WACC a empresa cria valor; abaixo, destrói.",
    ),
    _T(
        "roa",
        "ROA",
        "Retorno sobre o ativo",
        "Indicadores",
        "Lucro líquido gerado por real de ativo (financeiras).",
        "Lucro líquido / ativo total do início do período",
        "Em bancos é baixo por natureza; leia junto com a alavancagem.",
    ),
    _T(
        "alavancagem",
        "Ativo / PL",
        "Alavancagem contábil",
        "Indicadores",
        "Quantas vezes o ativo é maior que o patrimônio líquido (financeiras).",
        "Ativo total / patrimônio líquido consolidado",
        "Alavancagem alta amplifica ROE e risco; o índice de Basileia não está na CVM.",
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
    "preco_teto_bazin",
    "recomendacao",
    "confianca",
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
    "preco_teto_bazin",
    "recomendacao",
    "confianca",
)
LEGENDA_MULTIPLOS = ("ltm", "p25_p75")
LEGENDA_WACC = ("rf", "erp", "beta", "ke", "kd", "wacc")


def legenda_multiplos(nomes: Iterable[str]) -> tuple[str, ...]:
    """Legenda dos múltiplos que aparecem na tabela, mais LTM e quartis."""
    return (*nomes, *LEGENDA_MULTIPLOS)


def legenda_indicadores(historicos: Iterable[str], mercado: Iterable[str]) -> tuple[str, ...]:
    """Legenda do comando `indicadores`: os indicadores e múltiplos mostrados, mais LTM."""
    return (*dict.fromkeys((*historicos, *mercado)), "ltm")
