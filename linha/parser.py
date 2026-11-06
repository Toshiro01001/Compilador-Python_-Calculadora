"""Análise sintática por descida recursiva: uma função para cada regra.

Gramática (da menor para a maior precedência nas expressões):

    programa    -> (instrucao separador)* FIM
    instrucao   -> funcao | if | while | return | print | atribuicao | expressao
    funcao      -> "func" NOME "(" parametros? ")" bloco
    if          -> "if" expressao bloco ("else" (if | bloco))?
    while       -> "while" expressao bloco
    return      -> "return" expressao?
    print       -> "print" "(" expressao ")"
    atribuicao  -> NOME "=" expressao
    bloco       -> "{" (instrucao separador)* "}"
    expressao   -> soma (("==" | "!=" | "<" | "<=" | ">" | ">=") soma)*
    soma        -> produto (("+" | "-") produto)*
    produto     -> unario (("*" | "/" | "%") unario)*
    unario      -> "-" unario | primario
    primario    -> NUMERO | NOME | NOME "(" argumentos? ")" | "(" expressao ")"
"""

from . import arvore as a
from .erros import ErroSintaxe
from .lexer import FIM, FIM_LINHA, NOME, NUMERO, Token, tokenizar

# Limites iguais aos do compilador em JavaScript: protegem contra estouro de
# recursão com programas patológicos, como milhares de parênteses abertos.
MAX_ANINHAMENTO = 64
MAX_PROFUNDIDADE = 200

COMPARACOES = frozenset({"==", "!=", "<", "<=", ">", ">="})


def _descrever(token: Token) -> str:
    if token.tipo == FIM:
        return "o fim do programa"
    if token.tipo == FIM_LINHA:
        return "o fim da linha"
    return f"'{token.texto}'"


def _profundidade(no: a.No) -> int:
    if isinstance(no, a.Binaria):
        return no.profundidade
    return 1


class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.i = 0
        self.nivel = 0

    @property
    def atual(self) -> Token:
        return self.tokens[self.i]

    def _avancar(self) -> Token:
        token = self.tokens[self.i]
        self.i += 1
        return token

    def _exigir(self, tipo: str, descricao: str) -> Token:
        if self.atual.tipo != tipo:
            self._falhar(f"esperava {descricao}, mas encontrei {_descrever(self.atual)}")
        return self._avancar()

    def _falhar(self, mensagem: str, token: Token | None = None) -> None:
        token = token or self.atual
        raise ErroSintaxe(mensagem, token.linha, token.coluna)

    def _entrar(self) -> None:
        self.nivel += 1
        if self.nivel > MAX_ANINHAMENTO:
            self._falhar(f"aninhamento profundo demais (limite de {MAX_ANINHAMENTO} níveis)")

    def _pular_separadores(self) -> None:
        while self.atual.tipo in (FIM_LINHA, ";"):
            self._avancar()

    def _fim_instrucao(self) -> None:
        if self.atual.tipo in (FIM_LINHA, ";"):
            self._pular_separadores()
        elif self.atual.tipo not in ("}", FIM):
            self._falhar(f"esperava o fim da instrução, mas encontrei {_descrever(self.atual)}")

    def programa(self) -> a.Programa:
        itens: list[a.No] = []
        self._pular_separadores()
        while self.atual.tipo != FIM:
            itens.append(self._instrucao(no_topo=True))
            self._fim_instrucao()
        return a.Programa(self.atual.linha, self.atual.coluna, itens)

    def _instrucao(self, no_topo: bool = False) -> a.No:
        token = self.atual
        if token.tipo == "func":
            if not no_topo:
                self._falhar("funções só podem ser declaradas fora de blocos")
            return self._funcao()
        if token.tipo == "if":
            return self._if()
        if token.tipo == "while":
            return self._while()
        if token.tipo == "return":
            return self._return()
        if token.tipo == "print":
            return self._print()
        if token.tipo == NOME and self.tokens[self.i + 1].tipo == "=":
            self._avancar()
            self._avancar()
            return a.Atribuicao(token.linha, token.coluna, token.texto, self._expressao())
        if token.tipo == "else":
            self._falhar("'else' sem um 'if' antes")
        return a.ExpressaoSolta(token.linha, token.coluna, self._expressao())

    def _funcao(self) -> a.Funcao:
        inicio = self._avancar()
        nome = self._exigir(NOME, "o nome da função")
        self._exigir("(", "'(' depois do nome da função")
        parametros: list[str] = []
        if self.atual.tipo != ")":
            while True:
                parametro = self._exigir(NOME, "o nome de um parâmetro")
                if parametro.texto in parametros:
                    self._falhar(f"parâmetro '{parametro.texto}' repetido", parametro)
                parametros.append(parametro.texto)
                if self.atual.tipo != ",":
                    break
                self._avancar()
        self._exigir(")", "')' depois dos parâmetros")
        corpo, fim = self._bloco()
        return a.Funcao(
            inicio.linha, inicio.coluna, nome.texto, parametros, corpo, fim.linha, fim.coluna
        )

    def _if(self) -> a.Se:
        inicio = self._avancar()
        condicao = self._expressao()
        entao, _ = self._bloco()
        senao = None
        volta = self.i
        while self.atual.tipo == FIM_LINHA:
            self._avancar()
        if self.atual.tipo == "else":
            self._avancar()
            if self.atual.tipo == "if":
                self._entrar()
                senao = [self._if()]
                self.nivel -= 1
            else:
                senao, _ = self._bloco()
        else:
            self.i = volta
        return a.Se(inicio.linha, inicio.coluna, condicao, entao, senao)

    def _while(self) -> a.Enquanto:
        inicio = self._avancar()
        condicao = self._expressao()
        corpo, _ = self._bloco()
        return a.Enquanto(inicio.linha, inicio.coluna, condicao, corpo)

    def _return(self) -> a.Retorna:
        inicio = self._avancar()
        valor = None
        if self.atual.tipo not in (FIM_LINHA, ";", "}", FIM):
            valor = self._expressao()
        return a.Retorna(inicio.linha, inicio.coluna, valor)

    def _print(self) -> a.Imprime:
        inicio = self._avancar()
        self._exigir("(", "'(' depois de print")
        valor = self._expressao()
        self._exigir(")", "')' para fechar o print")
        return a.Imprime(inicio.linha, inicio.coluna, valor)

    def _bloco(self) -> tuple[list[a.No], Token]:
        self._exigir("{", "'{' para abrir o bloco")
        self._entrar()
        corpo: list[a.No] = []
        self._pular_separadores()
        while self.atual.tipo != "}":
            if self.atual.tipo == FIM:
                self._falhar("esperava '}' para fechar o bloco, mas o programa acabou")
            corpo.append(self._instrucao())
            self._fim_instrucao()
        self.nivel -= 1
        return corpo, self._avancar()

    def _binaria(self, operador: Token, esquerda: a.No, direita: a.No) -> a.Binaria:
        profundidade = max(_profundidade(esquerda), _profundidade(direita)) + 1
        if profundidade > MAX_PROFUNDIDADE:
            self._falhar(
                f"expressão longa demais (limite de {MAX_PROFUNDIDADE} operações encadeadas)",
                operador,
            )
        return a.Binaria(
            operador.linha, operador.coluna, operador.tipo, esquerda, direita, profundidade
        )

    def _expressao(self) -> a.No:
        self._entrar()
        no = self._soma()
        while self.atual.tipo in COMPARACOES:
            operador = self._avancar()
            no = self._binaria(operador, no, self._soma())
        self.nivel -= 1
        return no

    def _soma(self) -> a.No:
        no = self._produto()
        while self.atual.tipo in ("+", "-"):
            operador = self._avancar()
            no = self._binaria(operador, no, self._produto())
        return no

    def _produto(self) -> a.No:
        no = self._unario()
        while self.atual.tipo in ("*", "/", "%"):
            operador = self._avancar()
            no = self._binaria(operador, no, self._unario())
        return no

    def _unario(self) -> a.No:
        if self.atual.tipo == "-":
            operador = self._avancar()
            self._entrar()
            valor = self._unario()
            self.nivel -= 1
            return a.Negativo(operador.linha, operador.coluna, valor)
        return self._primario()

    def _primario(self) -> a.No:
        token = self.atual
        if token.tipo == NUMERO:
            self._avancar()
            return a.Numero(token.linha, token.coluna, float(token.texto))
        if token.tipo == NOME:
            self._avancar()
            if self.atual.tipo == "(":
                return self._chamada(token)
            return a.Variavel(token.linha, token.coluna, token.texto)
        if token.tipo == "(":
            self._avancar()
            no = self._expressao()
            self._exigir(")", "')' para fechar o parêntese")
            return no
        self._falhar(f"esperava um valor, mas encontrei {_descrever(token)}")
        raise AssertionError  # _falhar sempre levanta exceção

    def _chamada(self, nome: Token) -> a.Chamada:
        self._avancar()
        argumentos: list[a.No] = []
        if self.atual.tipo != ")":
            while True:
                argumentos.append(self._expressao())
                if self.atual.tipo != ",":
                    break
                self._avancar()
        self._exigir(")", "')' para fechar a chamada")
        return a.Chamada(nome.linha, nome.coluna, nome.texto, argumentos)


def analisar(fonte: str) -> a.Programa:
    """Do texto à árvore: lança ErroLexico ou ErroSintaxe com linha e coluna."""
    return Parser(tokenizar(fonte)).programa()
