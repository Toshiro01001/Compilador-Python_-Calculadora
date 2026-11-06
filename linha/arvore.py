"""Árvore sintática abstrata (AST): a estrutura do programa, sem pontuação."""

from dataclasses import dataclass


@dataclass
class No:
    linha: int
    coluna: int


# Expressões
@dataclass
class Numero(No):
    valor: float


@dataclass
class Variavel(No):
    nome: str


@dataclass
class Binaria(No):
    op: str
    esquerda: No
    direita: No
    profundidade: int = 1


@dataclass
class Negativo(No):
    valor: No


@dataclass
class Chamada(No):
    nome: str
    argumentos: list[No]


# Instruções
@dataclass
class Atribuicao(No):
    nome: str
    valor: No


@dataclass
class Imprime(No):
    valor: No


@dataclass
class Retorna(No):
    valor: No | None


@dataclass
class ExpressaoSolta(No):
    valor: No


@dataclass
class Se(No):
    condicao: No
    entao: list[No]
    senao: list[No] | None


@dataclass
class Enquanto(No):
    condicao: No
    corpo: list[No]


@dataclass
class Funcao(No):
    nome: str
    parametros: list[str]
    corpo: list[No]
    fim_linha: int
    fim_coluna: int


@dataclass
class Programa(No):
    """A posição do programa é a do fim do texto."""

    itens: list[No]


def _rotulo(no: No) -> str:
    match no:
        case Numero():
            return f"Número {no.valor:g}"
        case Variavel():
            return f"Variável {no.nome}"
        case Binaria():
            return f"Operação {no.op}"
        case Negativo():
            return "Negativo"
        case Chamada():
            return f"Chamada {no.nome}"
        case Atribuicao():
            return f"Atribuição {no.nome}"
        case Funcao():
            return f"Função {no.nome}({', '.join(no.parametros)})"
    return {
        Imprime: "Print",
        Retorna: "Return",
        ExpressaoSolta: "Expressão",
        Se: "If",
        Enquanto: "While",
        Programa: "Programa",
    }[type(no)]


def _filhos(no: No) -> list[No]:
    match no:
        case Binaria():
            return [no.esquerda, no.direita]
        case Negativo() | Atribuicao() | Imprime() | ExpressaoSolta():
            return [no.valor]
        case Retorna():
            return [no.valor] if no.valor else []
        case Chamada():
            return no.argumentos
        case Se():
            return [no.condicao, *no.entao, *(no.senao or [])]
        case Enquanto():
            return [no.condicao, *no.corpo]
        case Funcao():
            return no.corpo
        case Programa():
            return no.itens
    return []


def desenhar(no: No, margem: str = "") -> str:
    """Desenha a árvore em texto, um nó por linha."""
    linhas = [margem + _rotulo(no)]
    linhas += [desenhar(filho, margem + "  ") for filho in _filhos(no)]
    return "\n".join(linhas)
