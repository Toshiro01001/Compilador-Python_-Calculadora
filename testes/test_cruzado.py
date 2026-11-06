"""Teste cruzado: Python, C nativo, C com sanitizers e WebAssembly têm de concordar."""

import json
import os
import random
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from linha import ErroExecucao, ErroLinha, Maquina, compilar, tokenizar

RAIZ = Path(__file__).resolve().parent.parent
BUILD = RAIZ / "c" / "build"
LIMITE = 20000

PROGRAMAS_FIXOS = [
    "",
    "# só comentário",
    "print(0.1 + 0.2)\nprint(1 / 3)\nprint(-1 / 3)\nprint(2 / 3)\nprint(1000000 * 1000000 * 1000)",
    "print(7 % 3)\nprint(-7 % 3)\nprint(7 % -3)\nprint(7.5 % 2)\nprint(0 - 0)",
    "x = 1\ni = 0\nwhile i < 400 {\n x = x * 10\n i = i + 1\n}\nprint(x)\nprint(0 - x)\nprint(x - x)\nprint((x - x) == (x - x))",
    "x = 1\nwhile x < 1000000000000000000000 { x = x * 3\n print(x) }",
    "print(999999.9999999)\nprint(0.0000004)\nprint(0.0000005)\nprint(9999999999999999)\nprint(99999999999999.5)",
    "func f(n) { return f(n + 1) }\nf(0)",
    "func f(a) { b = a\n return b + f(a) }\nprint(f(1))",
    "print(1)\nprint(1 / 0)\nprint(2)",
    "print(ninguem)",
    "func f() { if 0 { z = 1 }\n return z }\nprint(f())",
    "while 1 { }",
    "while 1 { print(123456) }",
    "preço = 10\nação = preço * 2\nprint(ação)\nprint(nãoexiste)",
    "x = (1 +\n 2)\nprint(x)\nif x == 3 { print(1) }\nelse { print(2) }",
    "x = 1 @ 2",
    "x = 1 😀",
    "x = 12.",
    "print(1",
    "if 1 {",
    "func f(a, a) { }",
    "func f() { }\nfunc f() { }",
    "g(1)",
    "func f(a) { }\nf(1, 2)",
    "return 1",
    "(" * 300,
    "-" * 300 + "1",
    "1" + " + 1" * 300,
    "if 1 {\n" * 100,
    "a\r\nb = 2\r\nprint(b)\r\n",
]


def gerar_programa(semente: int) -> str:
    """Programa aleatório: sintaticamente válido, mas pode falhar ao executar."""
    r = random.Random(semente)
    nomes = ["a", "b", "c", "dia", "mês"]
    funcoes = [("f", 1), ("g", 2), ("h", 0)]

    def expr(prof: int) -> str:
        if prof <= 0 or r.random() < 0.25:
            escolha = r.random()
            if escolha < 0.5:
                return r.choice(["0", "1", "2", "3", "0.5", "10", "1.25", "1000000", "99999999999"])
            return r.choice(nomes)
        escolha = r.random()
        if escolha < 0.6:
            op = r.choice(["+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">="])
            return f"{expr(prof - 1)} {op} {expr(prof - 1)}"
        if escolha < 0.75:
            return f"({expr(prof - 1)})"
        if escolha < 0.85:
            return f"-{expr(prof - 1)}"
        nome, aridade = r.choice(funcoes)
        return f"{nome}({', '.join(expr(prof - 1) for _ in range(aridade))})"

    def bloco(prof: int, recuo: str, em_funcao: bool) -> list[str]:
        linhas = []
        for _ in range(r.randint(1, 4)):
            escolha = r.random()
            if escolha < 0.45:
                linhas.append(f"{recuo}{r.choice(nomes)} = {expr(2)}")
            elif escolha < 0.65:
                linhas.append(f"{recuo}print({expr(3)})")
            elif escolha < 0.8 and prof > 0:
                linhas.append(f"{recuo}if {expr(2)} {{")
                linhas += bloco(prof - 1, recuo + "  ", em_funcao)
                if r.random() < 0.5:
                    linhas.append(f"{recuo}}} else {{")
                    linhas += bloco(prof - 1, recuo + "  ", em_funcao)
                linhas.append(f"{recuo}}}")
            elif escolha < 0.9 and prof > 0:
                contador = r.choice(nomes)
                linhas.append(f"{recuo}{contador} = {r.randint(0, 4)}")
                linhas.append(f"{recuo}while {contador} > 0 {{")
                linhas += bloco(prof - 1, recuo + "  ", em_funcao)
                linhas.append(f"{recuo}  {contador} = {contador} - 1")
                linhas.append(f"{recuo}}}")
            elif em_funcao:
                linhas.append(f"{recuo}return {expr(2)}")
            else:
                linhas.append(f"{recuo}{expr(2)}")
        return linhas

    # Quase sempre dá valor às variáveis, para o programa ir longe antes de falhar.
    saida = [f"{n} = {r.randint(1, 9)}" for n in nomes if r.random() < 0.97]
    for nome, aridade in funcoes:
        escolhidos = r.sample(nomes, aridade)
        saida.append(f"func {nome}({', '.join(escolhidos)}) {{")
        saida += [f"  {n} = {r.randint(1, 9)}" for n in nomes if n not in escolhidos and r.random() < 0.97]
        saida += bloco(2, "  ", True)
        saida.append("}")
    saida += bloco(3, "", False)
    return "\n".join(saida) + "\n"


def rodar_python(fonte: str) -> dict:
    try:
        programa = compilar(fonte)
    except ErroLinha as erro:
        return {"erro_compilacao": str(erro)}
    maquina = Maquina(programa, limite_passos=LIMITE)
    erro = None
    try:
        maquina.executar()
    except ErroExecucao as e:
        erro = str(e)
    return {
        "bytes": programa.para_bytes(), "saida": "".join(maquina.saida),
        "erro": erro, "passos": maquina.passos,
    }


def rodar_nativo(executavel: Path, arquivo: Path) -> tuple[int, str, str]:
    r = subprocess.run(
        [str(executavel), str(arquivo), "--passos", str(LIMITE)],
        capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    return r.returncode, r.stdout, r.stderr


def tokens_python(fonte: str):
    try:
        return [[t.tipo, t.texto, t.linha, t.coluna] for t in tokenizar(fonte)]
    except ErroLinha:
        return None


@unittest.skipUnless(shutil.which("gcc") and shutil.which("node") and shutil.which("clang"),
                     "o teste cruzado precisa de gcc, clang e node")
class Cruzado(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([str(RAIZ / "c" / "compilar.sh"), "nativo"], check=True, capture_output=True)
        exemplos = subprocess.run(
            ["node", str(RAIZ / "testes" / "rodar_wasm.mjs"), "--exemplos"],
            check=True, capture_output=True, text=True, encoding="utf-8",
        )
        cls.exemplos = [e["fonte"] for e in json.loads(exemplos.stdout)]
        cls.pasta = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.pasta.cleanup)

    def conferir(self, casos: list[str]) -> None:
        entrada = json.dumps({"casos": casos, "limite": LIMITE})
        processo = subprocess.run(
            ["node", str(RAIZ / "testes" / "rodar_wasm.mjs")],
            input=entrada, check=True, capture_output=True, text=True, encoding="utf-8",
        )
        respostas = json.loads(processo.stdout)
        arquivo = Path(self.pasta.name) / "p.lbc"
        for fonte, js in zip(casos, respostas, strict=True):
            with self.subTest(fonte=fonte[:300]):
                py = rodar_python(fonte)
                tokens = tokens_python(fonte)
                if tokens is not None:
                    self.assertEqual(js["tokens"], tokens)
                if "erro_compilacao" in py:
                    self.assertEqual(js["erroCompilacao"], py["erro_compilacao"])
                    continue
                self.assertEqual(bytes.fromhex(js["bytes"]), py["bytes"], "bytecode diferente")
                arquivo.write_bytes(py["bytes"])
                esperado_rc = 1 if py["erro"] else 0
                esperado_err = py["erro"] + "\n" if py["erro"] else ""
                for nome in ("linha_vm", "linha_vm_san"):
                    rc, saida, erro = rodar_nativo(BUILD / nome, arquivo)
                    self.assertEqual((rc, saida, erro), (esperado_rc, py["saida"], esperado_err), nome)
                for modo in ("tudo", "passoAPasso"):
                    self.assertEqual(js[modo]["saida"], py["saida"], modo)
                    self.assertEqual(js[modo]["erro"], py["erro"], modo)
                    self.assertEqual(js[modo]["passos"], py["passos"], modo)

    def test_programas_fixos(self):
        self.conferir(PROGRAMAS_FIXOS)

    def test_exemplos_do_playground(self):
        self.conferir(self.exemplos)

    def test_programas_aleatorios(self):
        quantidade = int(os.environ.get("LINHA_ALEATORIOS", "300"))
        self.conferir([gerar_programa(s) for s in range(quantidade)])

    def test_fuzz_com_sanitizers(self):
        """Bytecode corrompido não pode causar erro de memória nem comportamento indefinido."""
        sementes = []
        for i, fonte in enumerate(self.exemplos[:5] + [gerar_programa(s) for s in range(20)]):
            caminho = Path(self.pasta.name) / f"s{i}.lbc"
            caminho.write_bytes(compilar(fonte).para_bytes())
            sementes.append(str(caminho))
        r = subprocess.run(
            [str(BUILD / "fuzz_san"), os.environ.get("LINHA_FUZZ", "200000"), *sementes],
            capture_output=True, text=True, timeout=500,
        )
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        self.assertIn("aceitas pelo carregador", r.stdout)

    def test_wasm_do_repositorio_veio_deste_codigo(self):
        temporario = Path(self.pasta.name) / "novo.wasm"
        subprocess.run(
            [str(RAIZ / "c" / "compilar.sh"), "wasm"], check=True, capture_output=True,
            env={**os.environ, "SAIDA_WASM": str(temporario)},
        )
        self.assertEqual(temporario.read_bytes(), (RAIZ / "playground" / "vm.wasm").read_bytes())


if __name__ == "__main__":
    unittest.main()
