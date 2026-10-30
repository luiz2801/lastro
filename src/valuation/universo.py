"""Universo de empresas: setores (enum) e as empresas de cada setor.

Os setores são os `setor_cvm` de `config/universo_ibovespa.csv`. O enum é fixo no código, para que
o mypy e a CLI conheçam os setores; um teste confere que ele coincide com o CSV.
"""

from __future__ import annotations

import csv
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from valuation.config import CAMINHO_UNIVERSO, ErroConfiguracao


class SetorCVM(StrEnum):
    """Setor de atividade do cadastro da CVM (valor = texto exato do CSV)."""

    AGRICULTURA_ACUCAR_ALCOOL_E_CANA = "Agricultura (Açúcar, Álcool e Cana)"
    ALIMENTOS = "Alimentos"
    BANCOS = "Bancos"
    BEBIDAS_E_FUMO = "Bebidas e Fumo"
    BOLSAS_DE_VALORES_MERCADORIAS_E_FUTUROS = "Bolsas de Valores/Mercadorias e Futuros"
    BRINQUEDOS_E_LAZER = "Brinquedos e Lazer"
    COMUNICACAO_E_INFORMATICA = "Comunicação e Informática"
    COMERCIO_ATACADO_E_VAREJO = "Comércio (Atacado e Varejo)"
    CONSTRUCAO_CIVIL_MAT_CONSTR_E_DECORACAO = "Construção Civil, Mat. Constr. e Decoração"
    EMP_ADM_PART_COMERCIO_ATACADO_E_VAREJO = "Emp. Adm. Part. - Comércio (Atacado e Varejo)"
    EMP_ADM_PART_CONST_CIVIL_MAT_CONST_E_DECORACAO = (
        "Emp. Adm. Part. - Const. Civil, Mat. Const. e Decoração"
    )
    EMP_ADM_PART_EDUCACAO = "Emp. Adm. Part. - Educação"
    EMP_ADM_PART_ENERGIA_ELETRICA = "Emp. Adm. Part. - Energia Elétrica"
    EMP_ADM_PART_EXTRACAO_MINERAL = "Emp. Adm. Part. - Extração Mineral"
    EMP_ADM_PART_INTERMEDIACAO_FINANCEIRA = "Emp. Adm. Part. - Intermediação Financeira"
    EMP_ADM_PART_METALURGIA_E_SIDERURGIA = "Emp. Adm. Part. - Metalurgia e Siderurgia"
    EMP_ADM_PART_MAQS_EQUIP_VEIC_E_PECAS = "Emp. Adm. Part. - Máqs., Equip., Veíc. e Peças"
    EMP_ADM_PART_PETROLEO_E_GAS = "Emp. Adm. Part. - Petróleo e Gás"
    EMP_ADM_PART_SEGURADORAS_E_CORRETORAS = "Emp. Adm. Part. - Seguradoras e Corretoras"
    EMP_ADM_PART_SERVICOS_TRANSPORTE_E_LOGISTICA = (
        "Emp. Adm. Part. - Serviços Transporte e Logística"
    )
    ENERGIA_ELETRICA = "Energia Elétrica"
    EXTRACAO_MINERAL = "Extração Mineral"
    FARMACEUTICO_E_HIGIENE = "Farmacêutico e Higiene"
    METALURGIA_E_SIDERURGIA = "Metalurgia e Siderurgia"
    MAQUINAS_EQUIPAMENTOS_VEICULOS_E_PECAS = "Máquinas, Equipamentos, Veículos e Peças"
    PAPEL_E_CELULOSE = "Papel e Celulose"
    PETROLEO_E_GAS = "Petróleo e Gás"
    SANEAMENTO_SERV_AGUA_E_GAS = "Saneamento, Serv. Água e Gás"
    SEGURADORAS_E_CORRETORAS = "Seguradoras e Corretoras"
    SERVICOS_MEDICOS = "Serviços Médicos"
    SERVICOS_TRANSPORTE_E_LOGISTICA = "Serviços Transporte e Logística"
    TELECOMUNICACOES = "Telecomunicações"
    TEXTIL_E_VESTUARIO = "Têxtil e Vestuário"


@dataclass(frozen=True)
class EmpresaUniverso:
    """Linha de `config/universo_ibovespa.csv`."""

    ticker: str
    setor: SetorCVM
    tipo_modelo: str


def _normalizar(texto: str) -> str:
    """Minúsculas, sem acento e sem pontuação, para casar nomes digitados à mão."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return "".join(c for c in sem_acento.lower() if c.isalnum())


def buscar_setor(texto: str) -> SetorCVM:
    """Setor pelo nome do membro (`BANCOS`) ou pelo texto da CVM (`Bancos`), sem distinguir caixa,
    acento ou pontuação. Desconhecido ⇒ `ErroConfiguracao`."""
    alvo = _normalizar(texto)
    for setor in SetorCVM:
        if alvo in (_normalizar(setor.name), _normalizar(setor.value)):
            return setor
    raise ErroConfiguracao(f"Setor {texto!r} não existe. Use `valuation setores` para ver a lista.")


def carregar_universo(caminho: Path = CAMINHO_UNIVERSO) -> list[EmpresaUniverso]:
    """Lê o CSV do universo (separador `;`, linhas `#` são comentário). Setor fora do enum ou
    arquivo sem as colunas exigidas ⇒ `ErroConfiguracao`."""
    if not caminho.is_file():
        raise ErroConfiguracao(f"{caminho} não existe.")
    with caminho.open(encoding="utf-8", newline="") as f:
        linhas = [linha for linha in f if linha.strip() and not linha.startswith("#")]
    leitor = csv.DictReader(linhas, delimiter=";")
    colunas = {"ticker", "setor_cvm", "tipo_modelo"}
    if not colunas.issubset(leitor.fieldnames or ()):
        raise ErroConfiguracao(f"{caminho} precisa das colunas {', '.join(sorted(colunas))}")
    empresas: list[EmpresaUniverso] = []
    for linha in leitor:
        try:
            setor = SetorCVM(linha["setor_cvm"])
        except ValueError as e:
            raise ErroConfiguracao(
                f"{caminho}: setor {linha['setor_cvm']!r} do ticker {linha['ticker']} não está "
                "no enum SetorCVM (src/valuation/universo.py)."
            ) from e
        empresas.append(EmpresaUniverso(linha["ticker"], setor, linha["tipo_modelo"]))
    return empresas


def empresas_do_setor(universo: list[EmpresaUniverso], setor: SetorCVM) -> list[EmpresaUniverso]:
    """Empresas do setor, na ordem do CSV."""
    return [e for e in universo if e.setor == setor]
