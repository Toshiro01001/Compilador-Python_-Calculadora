"""Formato binário do bytecode, compartilhado por Python, JavaScript e C.

Tudo em little-endian:

    "LIN1"
    u16 n, f64[n]                          constantes
    u16 n, {u16 tamanho, bytes UTF-8}[n]   nomes (para mensagens de erro)
    u16 globais
    u16 n, {u32 início, u16 parâmetros, u16 locais, u16 nome}[n]   funções
    u32 n, bytes[n]                        código
    u32 n, {u32 pc, u32 linha, u32 coluna, u16 nome}[n]            posições
"""

import struct
from dataclasses import dataclass, field

from .erros import BytecodeInvalido

ASSINATURA = b"LIN1"
SEM_NOME = 0xFFFF
MAX_PROGRAMA = 1 << 20
MAX_GLOBAIS = 4096

# (código, mnemônico, tamanho do operando em bytes)
_TABELA = [
    "PARA:0", "CONST:2", "LE_GLOBAL:2", "GRAVA_GLOBAL:2", "LE_LOCAL:2", "GRAVA_LOCAL:2",
    "SOMA:0", "SUB:0", "MUL:0", "DIV:0", "RESTO:0", "NEG:0",
    "IGUAL:0", "DIFERENTE:0", "MENOR:0", "MENOR_IGUAL:0", "MAIOR:0", "MAIOR_IGUAL:0",
    "PULA:4", "PULA_SE_ZERO:4", "CHAMA:2", "RETORNA:0", "IMPRIME:0", "DESCARTA:0",
]
MNEMONICOS = [item.split(":")[0] for item in _TABELA]
OPERANDO = [int(item.split(":")[1]) for item in _TABELA]
OP = {nome: codigo for codigo, nome in enumerate(MNEMONICOS)}


@dataclass
class InfoFuncao:
    inicio: int
    parametros: int
    locais: int
    nome: int


@dataclass
class Posicao:
    pc: int
    linha: int
    coluna: int
    nome: int = SEM_NOME


@dataclass
class Programa:
    constantes: list[float] = field(default_factory=list)
    nomes: list[str] = field(default_factory=list)
    globais: int = 0
    funcoes: list[InfoFuncao] = field(default_factory=list)
    codigo: bytearray = field(default_factory=bytearray)
    posicoes: list[Posicao] = field(default_factory=list)

    def para_bytes(self) -> bytes:
        saida = bytearray(ASSINATURA)
        saida += struct.pack("<H", len(self.constantes))
        for valor in self.constantes:
            saida += struct.pack("<d", valor)
        saida += struct.pack("<H", len(self.nomes))
        for nome in self.nomes:
            bruto = nome.encode("utf-8")
            saida += struct.pack("<H", len(bruto)) + bruto
        saida += struct.pack("<H", self.globais)
        saida += struct.pack("<H", len(self.funcoes))
        for f in self.funcoes:
            saida += struct.pack("<IHHH", f.inicio, f.parametros, f.locais, f.nome)
        saida += struct.pack("<I", len(self.codigo)) + self.codigo
        saida += struct.pack("<I", len(self.posicoes))
        for p in self.posicoes:
            saida += struct.pack("<IIIH", p.pc, p.linha, p.coluna, p.nome)
        return bytes(saida)

    @classmethod
    def de_bytes(cls, dados: bytes) -> "Programa":
        leitor = _Leitor(dados)
        try:
            if leitor.bruto(4) != ASSINATURA:
                raise BytecodeInvalido("assinatura desconhecida")
            p = cls()
            p.constantes = [leitor.ler("<d") for _ in range(leitor.ler("<H"))]
            p.nomes = [leitor.bruto(leitor.ler("<H")).decode("utf-8") for _ in range(leitor.ler("<H"))]
            p.globais = leitor.ler("<H")
            p.funcoes = [
                InfoFuncao(leitor.ler("<I"), leitor.ler("<H"), leitor.ler("<H"), leitor.ler("<H"))
                for _ in range(leitor.ler("<H"))
            ]
            p.codigo = bytearray(leitor.bruto(leitor.ler("<I")))
            p.posicoes = [
                Posicao(leitor.ler("<I"), leitor.ler("<I"), leitor.ler("<I"), leitor.ler("<H"))
                for _ in range(leitor.ler("<I"))
            ]
        except (struct.error, UnicodeDecodeError) as erro:
            raise BytecodeInvalido("arquivo cortado ou corrompido") from erro
        return p

    def desmontar(self) -> str:
        """Lista o bytecode em texto, uma instrução por linha."""
        linhas = []
        pc = 0
        por_pc = {p.pc: p for p in self.posicoes}
        while pc < len(self.codigo):
            codigo = self.codigo[pc]
            tamanho = OPERANDO[codigo]
            operando = int.from_bytes(self.codigo[pc + 1:pc + 1 + tamanho], "little")
            texto = f"{pc:6d}  {MNEMONICOS[codigo]:<14}"
            if tamanho:
                texto += f"{operando:<6d}"
            pos = por_pc[pc]
            nota = f"linha {pos.linha}"
            if MNEMONICOS[codigo] == "CONST":
                nota = f"{self.constantes[operando]:g}; {nota}"
            elif pos.nome != SEM_NOME:
                nota = f"{self.nomes[pos.nome]}; {nota}"
            linhas.append(f"{texto:<28} # {nota}")
            pc += 1 + tamanho
        return "\n".join(linhas)


class _Leitor:
    def __init__(self, dados: bytes) -> None:
        self.dados = dados
        self.i = 0

    def ler(self, formato: str):
        valor = struct.unpack_from(formato, self.dados, self.i)[0]
        self.i += struct.calcsize(formato)
        return valor

    def bruto(self, tamanho: int) -> bytes:
        if self.i + tamanho > len(self.dados):
            raise BytecodeInvalido("arquivo cortado ou corrompido")
        valor = self.dados[self.i:self.i + tamanho]
        self.i += tamanho
        return valor
