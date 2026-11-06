"""Máquina de pilha em Python. Espelha c/vm.c regra por regra, inclusive limites."""

import math
from dataclasses import dataclass

from .bytecode import MNEMONICOS, OPERANDO, SEM_NOME, Programa
from .erros import BytecodeInvalido, ErroExecucao

MAX_PILHA = 65536
MAX_QUADROS = 2048
MAX_SAIDA = 65536
LIMITE_PADRAO = 1_000_000


def _partes(a: float) -> tuple[int, int]:
    inteira = math.floor(a)
    decimais = math.floor((a - inteira) * 1e6 + 0.5)
    if decimais >= 1_000_000:
        inteira += 1
        decimais = 0
    return inteira, decimais


def _texto(inteira: int, decimais: int) -> str:
    if decimais == 0:
        return str(inteira)
    return f"{inteira}.{decimais:06d}".rstrip("0")


def formatar_numero(x: float) -> str:
    """Até 6 casas decimais, sem zeros à direita. Mesmo algoritmo do C."""
    if math.isnan(x):
        return "nan"
    if math.isinf(x):
        return "inf" if x > 0 else "-inf"
    a = abs(x)
    if a >= 1e15:
        expoente = 0
        while a >= 10:
            a /= 10
            expoente += 1
        inteira, decimais = _partes(a)
        if inteira >= 10:
            inteira, decimais = 1, 0
            expoente += 1
        corpo = f"{_texto(inteira, decimais)}e+{expoente}"
    else:
        corpo = _texto(*_partes(a))
    return f"-{corpo}" if x < 0 and corpo != "0" else corpo


def resto(a: float, b: float) -> float:
    """Resto com o sinal do dividendo, calculado igual em todas as máquinas."""
    q = a / b
    if math.isnan(q) or math.isinf(q):
        return a - b * q
    return a - b * float(math.trunc(q))


@dataclass
class Quadro:
    retorno: int
    base: int
    piso: int
    funcao: int


class Maquina:
    def __init__(
        self, programa: Programa, limite_passos: int = LIMITE_PADRAO,
        globais: list[float | None] | None = None,
    ) -> None:
        self.p = programa
        self.limite = limite_passos
        self.globais: list[float | None] = list(globais or [])
        self.globais += [None] * (programa.globais - len(self.globais))
        self.pilha: list[float | None] = []
        self.quadros = [Quadro(0, 0, 0, SEM_NOME)]
        self.pc = 0
        self.passos = 0
        self.saida: list[str] = []
        self.tamanho_saida = 0
        self.terminou = False

    def _falhar(self, mensagem: str, pc: int) -> None:
        linha, coluna = self._posicao(pc)
        raise ErroExecucao(mensagem, linha, coluna)

    def _posicao(self, pc: int) -> tuple[int, int]:
        melhor = self.p.posicoes[0] if self.p.posicoes else None
        for pos in self.p.posicoes:
            if pos.pc > pc:
                break
            melhor = pos
        return (melhor.linha, melhor.coluna) if melhor else (0, 0)

    def _nome_em(self, pc: int) -> str:
        for pos in self.p.posicoes:
            if pos.pc == pc and pos.nome != SEM_NOME:
                return self.p.nomes[pos.nome]
        return "?"

    def _empilhar(self, valor: float | None, pc: int) -> None:
        if len(self.pilha) >= MAX_PILHA:
            self._falhar("pilha cheia", pc)
        self.pilha.append(valor)

    def _imprimir(self, valor: float, pc: int) -> None:
        texto = formatar_numero(valor) + "\n"
        if self.tamanho_saida + len(texto) > MAX_SAIDA:
            self._falhar("saída grande demais", pc)
        self.saida.append(texto)
        self.tamanho_saida += len(texto)

    def passo(self) -> bool:
        """Executa uma instrução. Devolve False quando o programa termina."""
        if self.terminou:
            return False
        pc = self.pc
        if self.passos >= self.limite:
            self._falhar("limite de passos atingido", pc)
        self.passos += 1

        codigo = self.p.codigo
        op = codigo[pc]
        largura = OPERANDO[op]
        arg = int.from_bytes(codigo[pc + 1:pc + 1 + largura], "little")
        self.pc = pc + 1 + largura
        nome = MNEMONICOS[op]
        pilha = self.pilha

        if nome == "PARA":
            self.pc = pc
            self.terminou = True
            return False
        if nome == "CONST":
            self.pc = pc
            self._empilhar(self.p.constantes[arg], pc)
        elif nome == "LE_GLOBAL":
            self.pc = pc
            if self.globais[arg] is None:
                self._falhar(f"variável '{self._nome_em(pc)}' não tem valor", pc)
            self._empilhar(self.globais[arg], pc)
        elif nome == "GRAVA_GLOBAL":
            self.globais[arg] = pilha.pop()
        elif nome == "LE_LOCAL":
            self.pc = pc
            valor = pilha[self.quadros[-1].base + arg]
            if valor is None:
                self._falhar(f"variável '{self._nome_em(pc)}' não tem valor", pc)
            self._empilhar(valor, pc)
        elif nome == "GRAVA_LOCAL":
            pilha[self.quadros[-1].base + arg] = pilha.pop()
        elif nome == "NEG":
            pilha[-1] = -pilha[-1]
        elif nome == "PULA":
            self.pc = arg
            return True
        elif nome == "PULA_SE_ZERO":
            if pilha.pop() == 0:
                self.pc = arg
            return True
        elif nome == "CHAMA":
            self.pc = pc
            self._chamar(arg, pc)
            return True
        elif nome == "RETORNA":
            valor = pilha.pop()
            quadro = self.quadros.pop()
            del pilha[quadro.base:]
            pilha.append(valor)
            self.pc = quadro.retorno
            return True
        elif nome == "IMPRIME":
            self.pc = pc
            self._imprimir(pilha[-1], pc)
            pilha.pop()
        elif nome == "DESCARTA":
            pilha.pop()
        else:
            self.pc = pc
            b = pilha.pop()
            a = pilha.pop()
            pilha.append(self._binaria(nome, a, b, pc))
        self.pc = pc + 1 + largura
        return True

    def _binaria(self, nome: str, a: float, b: float, pc: int) -> float:
        if nome in ("DIV", "RESTO") and b == 0:
            self._falhar("divisão por zero", pc)
        match nome:
            case "SOMA":
                return a + b
            case "SUB":
                return a - b
            case "MUL":
                return a * b
            case "DIV":
                return a / b
            case "RESTO":
                return resto(a, b)
            case "IGUAL":
                return 1.0 if a == b else 0.0
            case "DIFERENTE":
                return 1.0 if a != b else 0.0
            case "MENOR":
                return 1.0 if a < b else 0.0
            case "MENOR_IGUAL":
                return 1.0 if a <= b else 0.0
            case "MAIOR":
                return 1.0 if a > b else 0.0
            case "MAIOR_IGUAL":
                return 1.0 if a >= b else 0.0
        raise AssertionError(nome)

    def _chamar(self, indice: int, pc: int) -> None:
        funcao = self.p.funcoes[indice]
        if len(self.quadros) >= MAX_QUADROS:
            self._falhar("chamadas demais: recursão profunda demais", pc)
        extras = funcao.locais - funcao.parametros
        if len(self.pilha) + extras > MAX_PILHA:
            self._falhar("pilha cheia", pc)
        base = len(self.pilha) - funcao.parametros
        self.pilha.extend([None] * extras)
        self.quadros.append(Quadro(pc + 3, base, len(self.pilha), indice))
        self.pc = funcao.inicio

    def executar(self) -> str:
        """Roda até o fim e devolve a saída. Erros levam a saída em `self.saida`."""
        try:
            while self.passo():
                pass
        except (IndexError, TypeError) as erro:
            raise BytecodeInvalido("instrução fora do esperado") from erro
        return "".join(self.saida)
