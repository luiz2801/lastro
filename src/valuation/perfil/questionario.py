"""Questionário de perfil do investidor (estilo suitability), só dados.

Cada alternativa vale de 1 a 5 pontos; 10 perguntas ⇒ pontuação de 10 a 50. Alternativas com
`veto` forçam o perfil conservador, independentemente da soma (seção 8.2 do CLAUDE.md).
Mudar texto, pontos ou vetos de forma que altere a classificação exige subir
`VERSAO_QUESTIONARIO`: perfis gravados com outra versão deixam de ser aceitos.
"""

from __future__ import annotations

from dataclasses import dataclass

VERSAO_QUESTIONARIO = 1

VETO_HORIZONTE_CURTO = "horizonte_menor_2_anos"
VETO_NAO_ACEITA_PERDAS = "nao_aceita_perdas"


@dataclass(frozen=True)
class Alternativa:
    texto: str
    pontos: int
    veto: str | None = None


@dataclass(frozen=True)
class Pergunta:
    chave: str
    tema: str
    enunciado: str
    alternativas: tuple[Alternativa, ...]


QUESTIONARIO: tuple[Pergunta, ...] = (
    Pergunta(
        "q1",
        "Objetivo",
        "Qual é o principal objetivo dos seus investimentos?",
        (
            Alternativa("Preservar o capital, mesmo que rendendo pouco", 1),
            Alternativa("Gerar renda regular (dividendos, juros)", 2),
            Alternativa("Equilibrar renda e crescimento do patrimônio", 3),
            Alternativa("Fazer o patrimônio crescer no longo prazo", 4),
            Alternativa("Buscar ganhos altos, aceitando grandes oscilações", 5),
        ),
    ),
    Pergunta(
        "q2",
        "Horizonte",
        "Por quanto tempo pretende manter o dinheiro em ações sem precisar resgatá-lo?",
        (
            Alternativa("Menos de 2 anos", 1, VETO_HORIZONTE_CURTO),
            Alternativa("De 2 a 3 anos", 2),
            Alternativa("De 3 a 5 anos", 3),
            Alternativa("De 5 a 10 anos", 4),
            Alternativa("Mais de 10 anos", 5),
        ),
    ),
    Pergunta(
        "q3",
        "Reação a queda",
        "Sua carteira de ações cai 20% em poucos meses. O que você faz?",
        (
            Alternativa("Vendo tudo para evitar novas perdas", 1),
            Alternativa("Vendo parte para reduzir o risco", 2),
            Alternativa("Mantenho e espero a recuperação", 3),
            Alternativa("Mantenho e, se os fundamentos seguirem bons, compro um pouco mais", 4),
            Alternativa("Compro mais de forma significativa, aproveitando os preços", 5),
        ),
    ),
    Pergunta(
        "q4",
        "Renda variável no patrimônio",
        "Que parte do seu patrimônio financeiro ficará em renda variável?",
        (
            Alternativa("Até 10%", 1),
            Alternativa("De 10% a 25%", 2),
            Alternativa("De 25% a 50%", 3),
            Alternativa("De 50% a 75%", 4),
            Alternativa("Mais de 75%", 5),
        ),
    ),
    Pergunta(
        "q5",
        "Dependência da renda",
        "Quanto você depende da renda gerada pelos investimentos?",
        (
            Alternativa("Dependo dela para as despesas do mês", 1),
            Alternativa("Ela complementa boa parte das despesas", 2),
            Alternativa("Ela ajuda eventualmente", 3),
            Alternativa("Não preciso dela; reinvisto quase tudo", 4),
            Alternativa("Não preciso dela e não precisarei nos próximos 10 anos", 5),
        ),
    ),
    Pergunta(
        "q6",
        "Experiência",
        "Qual é a sua experiência com renda variável?",
        (
            Alternativa("Nunca investi em renda variável", 1),
            Alternativa("Menos de 2 anos, só com fundos ou ETFs", 2),
            Alternativa("De 2 a 5 anos com ações", 3),
            Alternativa("Mais de 5 anos com ações", 4),
            Alternativa("Mais de 5 anos com ações e derivativos (opções, termo)", 5),
        ),
    ),
    Pergunta(
        "q7",
        "Reserva de emergência",
        "Quantos meses de despesas a sua reserva de emergência cobre, fora deste investimento?",
        (
            Alternativa("Não tenho reserva", 1),
            Alternativa("Menos de 3 meses", 2),
            Alternativa("De 3 a 6 meses", 3),
            Alternativa("De 6 a 12 meses", 4),
            Alternativa("Mais de 12 meses", 5),
        ),
    ),
    Pergunta(
        "q8",
        "Análise fundamentalista",
        "Qual é o seu conhecimento de análise fundamentalista?",
        (
            Alternativa("Nenhum", 1),
            Alternativa("Conheço indicadores como P/L e dividend yield", 2),
            Alternativa("Leio DRE e balanço, com alguma dificuldade", 3),
            Alternativa("Analiso demonstrações e calculo múltiplos com segurança", 4),
            Alternativa("Monto modelos de fluxo de caixa descontado", 5),
        ),
    ),
    Pergunta(
        "q9",
        "Perda máxima",
        "Qual é a maior perda que você aceitaria em 12 meses sem mudar de estratégia?",
        (
            Alternativa("Não aceito perdas", 1, VETO_NAO_ACEITA_PERDAS),
            Alternativa("Até 5%", 2),
            Alternativa("Até 15%", 3),
            Alternativa("Até 30%", 4),
            Alternativa("Mais de 30%", 5),
        ),
    ),
    Pergunta(
        "q10",
        "Estabilidade da renda",
        "Como é a sua renda principal (trabalho, aposentadoria, aluguéis)?",
        (
            Alternativa("Não tenho renda regular", 1),
            Alternativa("Variável e imprevisível (autônomo, comissões)", 2),
            Alternativa("Variável, mas com um mínimo previsível", 3),
            Alternativa("Fixa, no setor privado", 4),
            Alternativa("Fixa e muito estável (servidor, aposentadoria, aluguéis)", 5),
        ),
    ),
)
