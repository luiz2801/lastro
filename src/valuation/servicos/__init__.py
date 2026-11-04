"""Camada de serviço: orquestração sem apresentação, comum à CLI e à GUI (ADR 0022).

Devolve objetos e DataFrames; avisos voltam no retorno como `list[str]` e erros são as exceções de
domínio. Sem terminal nem tela aqui.
"""
