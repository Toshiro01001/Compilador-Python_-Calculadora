"""Geração de código: percorre a árvore e escreve bytecode para a máquina de pilha.

Regra de escopo, como no Python: dentro de uma função, é local todo nome que
seja parâmetro ou receba uma atribuição ali. Os demais nomes leem a global.
"""

import struct

from . import arvore as a
from .bytecode import (
    MAX_GLOBAIS,
    MAX_PROGRAMA,
    OP,
    SEM_NOME,
    InfoFuncao,
    Posicao,
    Programa,
)
from .erros import ErroSemantico
from .parser import analisar

_BINARIAS = {
    "+": "SOMA", "-": "SUB", "*": "MUL", "/": "DIV", "%": "RESTO",
    "==": "IGUAL", "!=": "DIFERENTE", "<": "MENOR", "<=": "MENOR_IGUAL",
    ">": "MAIOR", ">=": "MAIOR_IGUAL",
}
MAX_INDICE = 0xFFFF


def _nomes_atribuidos(corpo: list[a.No], saida: list[str]) -> None:
    for no in corpo:
        if isinstance(no, a.Atribuicao) and no.nome not in saida:
            saida.append(no.nome)
        elif isinstance(no, a.Se):
            _nomes_atribuidos(no.entao, saida)
            _nomes_atribuidos(no.senao or [], saida)
        elif isinstance(no, a.Enquanto):
            _nomes_atribuidos(no.corpo, saida)


class Compilador:
    """`funcoes` e `globais` permitem ao REPL lembrar o que já foi digitado."""

    def __init__(
        self,
        funcoes: dict[str, a.Funcao] | None = None,
        globais: dict[str, int] | None = None,
    ) -> None:
        self.programa = Programa()
        self.ast_funcoes: dict[str, a.Funcao] = dict(funcoes or {})
        self.globais: dict[str, int] = dict(globais or {})
        self.indice_funcao: dict[str, int] = {}
        self._constantes: dict[float, int] = {}
        self._nomes: dict[str, int] = {}
        self.locais: list[str] | None = None

    def _emitir(
        self, nome_op: str, no_pos: tuple[int, int], operando: int | None = None,
        nome: str | None = None, largura: int = 2,
    ) -> int:
        """Escreve uma instrução e devolve a posição do operando (para remendos)."""
        prog = self.programa
        prog.posicoes.append(
            Posicao(len(prog.codigo), no_pos[0], no_pos[1],
                    self._nome(nome, no_pos) if nome is not None else SEM_NOME)
        )
        prog.codigo.append(OP[nome_op])
        local_operando = len(prog.codigo)
        if operando is not None:
            prog.codigo += operando.to_bytes(largura, "little")
        return local_operando

    def _nome(self, nome: str, pos: tuple[int, int]) -> int:
        if nome not in self._nomes:
            if len(self.programa.nomes) >= MAX_INDICE:
                raise ErroSemantico("nomes demais no programa", *pos)
            self._nomes[nome] = len(self.programa.nomes)
            self.programa.nomes.append(nome)
        return self._nomes[nome]

    def _constante(self, valor: float, pos: tuple[int, int]) -> int:
        if valor not in self._constantes:
            if len(self.programa.constantes) >= MAX_INDICE:
                raise ErroSemantico("constantes demais no programa", *pos)
            self._constantes[valor] = len(self.programa.constantes)
            self.programa.constantes.append(valor)
        return self._constantes[valor]

    def _global(self, nome: str, pos: tuple[int, int]) -> int:
        if nome not in self.globais:
            if len(self.globais) >= MAX_GLOBAIS:
                raise ErroSemantico(f"variáveis globais demais (limite de {MAX_GLOBAIS})", *pos)
            self.globais[nome] = len(self.globais)
        return self.globais[nome]

    def compilar(self, arvore: a.Programa) -> Programa:
        principais: list[a.No] = []
        declaradas: set[str] = set()
        for item in arvore.itens:
            if isinstance(item, a.Funcao):
                if item.nome in declaradas:
                    raise ErroSemantico(
                        f"função '{item.nome}' declarada mais de uma vez", item.linha, item.coluna
                    )
                declaradas.add(item.nome)
                self.ast_funcoes[item.nome] = item
            else:
                principais.append(item)

        for indice, nome in enumerate(self.ast_funcoes):
            funcao = self.ast_funcoes[nome]
            self.indice_funcao[nome] = indice
            locais = list(funcao.parametros)
            _nomes_atribuidos(funcao.corpo, locais)
            if len(locais) > MAX_INDICE or indice >= MAX_INDICE:
                raise ErroSemantico("funções ou variáveis locais demais", funcao.linha, funcao.coluna)
            self.programa.funcoes.append(
                InfoFuncao(0, len(funcao.parametros), len(locais),
                           self._nome(nome, (funcao.linha, funcao.coluna)))
            )

        self._bloco(principais)
        self._emitir("PARA", (arvore.linha, arvore.coluna))

        for indice, nome in enumerate(self.ast_funcoes):
            self._funcao(self.ast_funcoes[nome], indice)

        self.programa.globais = len(self.globais)
        if len(self.programa.para_bytes()) > MAX_PROGRAMA:
            raise ErroSemantico("programa grande demais", arvore.linha, arvore.coluna)
        return self.programa

    def _funcao(self, funcao: a.Funcao, indice: int) -> None:
        self.programa.funcoes[indice].inicio = len(self.programa.codigo)
        self.locais = list(funcao.parametros)
        _nomes_atribuidos(funcao.corpo, self.locais)
        self._bloco(funcao.corpo)
        fim = (funcao.fim_linha, funcao.fim_coluna)
        self._emitir("CONST", fim, self._constante(0.0, fim))
        self._emitir("RETORNA", fim)
        self.locais = None

    def _bloco(self, corpo: list[a.No]) -> None:
        for no in corpo:
            self._instrucao(no)

    def _remendar(self, local: int) -> None:
        struct.pack_into("<I", self.programa.codigo, local, len(self.programa.codigo))

    def _instrucao(self, no: a.No) -> None:
        pos = (no.linha, no.coluna)
        match no:
            case a.Atribuicao():
                self._expressao(no.valor)
                if self.locais is not None and no.nome in self.locais:
                    self._emitir("GRAVA_LOCAL", pos, self.locais.index(no.nome), nome=no.nome)
                else:
                    self._emitir("GRAVA_GLOBAL", pos, self._global(no.nome, pos), nome=no.nome)
            case a.Imprime():
                self._expressao(no.valor)
                self._emitir("IMPRIME", pos)
            case a.ExpressaoSolta():
                self._expressao(no.valor)
                self._emitir("DESCARTA", pos)
            case a.Retorna():
                if self.locais is None:
                    raise ErroSemantico("'return' fora de uma função", *pos)
                if no.valor is None:
                    self._emitir("CONST", pos, self._constante(0.0, pos))
                else:
                    self._expressao(no.valor)
                self._emitir("RETORNA", pos)
            case a.Se():
                self._expressao(no.condicao)
                para_senao = self._emitir("PULA_SE_ZERO", pos, 0, largura=4)
                self._bloco(no.entao)
                if no.senao is None:
                    self._remendar(para_senao)
                else:
                    para_fim = self._emitir("PULA", pos, 0, largura=4)
                    self._remendar(para_senao)
                    self._bloco(no.senao)
                    self._remendar(para_fim)
            case a.Enquanto():
                inicio = len(self.programa.codigo)
                self._expressao(no.condicao)
                para_fim = self._emitir("PULA_SE_ZERO", pos, 0, largura=4)
                self._bloco(no.corpo)
                self._emitir("PULA", pos, inicio, largura=4)
                self._remendar(para_fim)
            case _:
                raise AssertionError(f"instrução desconhecida: {no!r}")

    def _expressao(self, no: a.No) -> None:
        pos = (no.linha, no.coluna)
        match no:
            case a.Numero():
                self._emitir("CONST", pos, self._constante(no.valor, pos))
            case a.Variavel():
                if self.locais is not None and no.nome in self.locais:
                    self._emitir("LE_LOCAL", pos, self.locais.index(no.nome), nome=no.nome)
                else:
                    self._emitir("LE_GLOBAL", pos, self._global(no.nome, pos), nome=no.nome)
            case a.Binaria():
                self._expressao(no.esquerda)
                self._expressao(no.direita)
                self._emitir(_BINARIAS[no.op], pos)
            case a.Negativo():
                self._expressao(no.valor)
                self._emitir("NEG", pos)
            case a.Chamada():
                self._chamada(no, pos)
            case _:
                raise AssertionError(f"expressão desconhecida: {no!r}")

    def _chamada(self, no: a.Chamada, pos: tuple[int, int]) -> None:
        funcao = self.ast_funcoes.get(no.nome)
        if funcao is None:
            raise ErroSemantico(f"função '{no.nome}' não existe", *pos)
        if len(no.argumentos) != len(funcao.parametros):
            raise ErroSemantico(
                f"função '{no.nome}' espera {len(funcao.parametros)} argumento(s), "
                f"mas recebeu {len(no.argumentos)}",
                *pos,
            )
        for argumento in no.argumentos:
            self._expressao(argumento)
        self._emitir("CHAMA", pos, self.indice_funcao[no.nome], nome=no.nome)


def compilar(fonte: str) -> Programa:
    """Do texto ao bytecode."""
    return Compilador().compilar(analisar(fonte))
