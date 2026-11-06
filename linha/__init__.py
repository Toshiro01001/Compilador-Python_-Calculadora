"""Linha: uma linguagem pequena, com compilador para bytecode e máquina de pilha."""

from .bytecode import Programa
from .compilador import Compilador, compilar
from .erros import (
    BytecodeInvalido,
    ErroExecucao,
    ErroLexico,
    ErroLinha,
    ErroSemantico,
    ErroSintaxe,
)
from .lexer import Token, tokenizar
from .maquina import Maquina, formatar_numero
from .parser import analisar

__all__ = [
    "BytecodeInvalido", "Compilador", "ErroExecucao", "ErroLexico", "ErroLinha",
    "ErroSemantico", "ErroSintaxe", "Maquina", "Programa", "Token", "analisar",
    "compilar", "formatar_numero", "tokenizar",
]
