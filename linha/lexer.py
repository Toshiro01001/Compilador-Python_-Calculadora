"""Análise léxica: transforma o texto do programa em uma lista de tokens."""

from dataclasses import dataclass

from .erros import ErroLexico

PALAVRAS = frozenset({"if", "else", "while", "func", "return", "print"})
OPERADORES_DUPLOS = frozenset({"==", "!=", "<=", ">="})
SIMBOLOS = frozenset("+-*/%=<>(){},;")

NUMERO = "NUMERO"
NOME = "NOME"
FIM_LINHA = "FIM_LINHA"
FIM = "FIM"


@dataclass(frozen=True)
class Token:
    """`tipo` é NUMERO, NOME, FIM_LINHA, FIM ou o próprio texto (`if`, `+`)."""

    tipo: str
    texto: str
    linha: int
    coluna: int


def _inicia_nome(c: str) -> bool:
    return c == "_" or "a" <= c <= "z" or "A" <= c <= "Z" or (
        "À" <= c <= "ÿ" and c not in "×÷"
    )


def _digito(c: str) -> bool:
    return "0" <= c <= "9"


def tokenizar(fonte: str) -> list[Token]:
    """Lê o texto inteiro. Quebras de linha dentro de parênteses são ignoradas."""
    tokens: list[Token] = []
    i, linha, inicio_linha, parenteses = 0, 1, 0, 0
    tamanho = len(fonte)

    while i < tamanho:
        c = fonte[i]
        coluna = i - inicio_linha + 1

        if c == "\n":
            if parenteses == 0 and tokens and tokens[-1].tipo != FIM_LINHA:
                tokens.append(Token(FIM_LINHA, "\n", linha, coluna))
            i += 1
            linha += 1
            inicio_linha = i
        elif c in " \t\r":
            i += 1
        elif c == "#":
            while i < tamanho and fonte[i] != "\n":
                i += 1
        elif _digito(c):
            fim = i
            while fim < tamanho and _digito(fonte[fim]):
                fim += 1
            if fim < tamanho and fonte[fim] == ".":
                fim += 1
                if fim >= tamanho or not _digito(fonte[fim]):
                    raise ErroLexico(
                        "número incompleto: falta um dígito depois do ponto",
                        linha,
                        coluna,
                    )
                while fim < tamanho and _digito(fonte[fim]):
                    fim += 1
            tokens.append(Token(NUMERO, fonte[i:fim], linha, coluna))
            i = fim
        elif _inicia_nome(c):
            fim = i
            while fim < tamanho and (_inicia_nome(fonte[fim]) or _digito(fonte[fim])):
                fim += 1
            texto = fonte[i:fim]
            tokens.append(Token(texto if texto in PALAVRAS else NOME, texto, linha, coluna))
            i = fim
        elif fonte[i:i + 2] in OPERADORES_DUPLOS:
            tokens.append(Token(fonte[i:i + 2], fonte[i:i + 2], linha, coluna))
            i += 2
        elif c in SIMBOLOS:
            if c == "(":
                parenteses += 1
            elif c == ")" and parenteses > 0:
                parenteses -= 1
            tokens.append(Token(c, c, linha, coluna))
            i += 1
        else:
            raise ErroLexico(f"caractere inesperado '{c}'", linha, coluna)

    tokens.append(Token(FIM, "", linha, tamanho - inicio_linha + 1))
    return tokens
