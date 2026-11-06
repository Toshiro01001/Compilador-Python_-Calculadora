"""REPL: digite instruções; variáveis e funções continuam valendo entre entradas."""

from collections.abc import Callable

from . import arvore as a
from .compilador import Compilador
from .erros import ErroExecucao, ErroLinha
from .lexer import FIM, tokenizar
from .maquina import Maquina
from .parser import analisar


def _incompleto(texto: str) -> bool:
    """Blocos ou parênteses abertos: a entrada continua na próxima linha."""
    try:
        tokens = tokenizar(texto)
    except ErroLinha:
        return False
    abertos = 0
    for token in tokens:
        if token.tipo == FIM:
            break
        if token.tipo in ("{", "("):
            abertos += 1
        elif token.tipo in ("}", ")"):
            abertos -= 1
    return abertos > 0


class Sessao:
    def __init__(self) -> None:
        self.funcoes: dict[str, a.Funcao] = {}
        self.globais: dict[str, int] = {}
        self.valores: list[float | None] = []

    def avaliar(self, fonte: str) -> str:
        """Roda uma entrada e devolve a saída. Expressão solta no fim é mostrada."""
        arvore = analisar(fonte)
        if arvore.itens and isinstance(arvore.itens[-1], a.ExpressaoSolta):
            ultima = arvore.itens[-1]
            arvore.itens[-1] = a.Imprime(ultima.linha, ultima.coluna, ultima.valor)
        compilador = Compilador(self.funcoes, self.globais)
        programa = compilador.compilar(arvore)
        maquina = Maquina(programa, globais=self.valores)
        self.funcoes = compilador.ast_funcoes
        self.globais = compilador.globais
        try:
            return maquina.executar()
        except ErroExecucao as erro:
            parcial = "".join(maquina.saida)
            raise _ErroComSaida(erro, parcial) from erro
        finally:
            self.valores = maquina.globais


class _ErroComSaida(ErroLinha):
    def __init__(self, erro: ErroLinha, saida: str) -> None:
        super().__init__(erro.mensagem, erro.linha, erro.coluna)
        self.saida = saida


def repl(ler: Callable[[str], str] = input, escrever: Callable[[str], None] = print) -> None:
    escrever("Linha, REPL interativo. Digite 'sair' para terminar.")
    sessao = Sessao()
    while True:
        texto = ""
        try:
            texto = ler(">> ")
            if texto.strip() in ("sair", "exit"):
                return
            while _incompleto(texto):
                texto += "\n" + ler(".. ")
            if not texto.strip():
                continue
            saida = sessao.avaliar(texto)
            if saida:
                escrever(saida.rstrip("\n"))
        except _ErroComSaida as erro:
            if erro.saida:
                escrever(erro.saida.rstrip("\n"))
            escrever(erro.apontar(texto))
        except ErroLinha as erro:
            escrever(erro.apontar(texto))
        except (EOFError, KeyboardInterrupt):
            escrever("")
            return
