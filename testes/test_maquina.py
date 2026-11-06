"""Máquina de pilha em Python, CLI e REPL."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from linha import ErroExecucao, Maquina, Programa, compilar, formatar_numero
from linha.__main__ import main
from linha.erros import BytecodeInvalido
from linha.maquina import MAX_SAIDA
from linha.repl import Sessao, repl


def rodar(fonte: str, limite: int = 1_000_000) -> str:
    return Maquina(compilar(fonte), limite_passos=limite).executar()


class Execucao(unittest.TestCase):
    def test_aritmetica(self):
        self.assertEqual(rodar("print(2 + 3 * 4)\nprint((2 + 3) * 4)\nprint(-7 % 3)\nprint(7 / 2)"), "14\n20\n-1\n3.5\n")

    def test_comparacoes_dao_um_e_zero(self):
        fonte = "print(1 < 2)\nprint(2 <= 1)\nprint(3 == 3)\nprint(3 != 3)\nprint(4 > 1)\nprint(1 >= 4)"
        self.assertEqual(rodar(fonte), "1\n0\n1\n0\n1\n0\n")

    def test_if_else_e_while(self):
        fonte = """
        i = 0
        while i < 4 {
          if i % 2 == 0 { print(i) } else if i == 1 { print(100) } else { print(200) }
          i = i + 1
        }
        """
        self.assertEqual(rodar(fonte), "0\n100\n2\n200\n")

    def test_funcoes_recursao_e_escopo(self):
        fonte = """
        x = 10
        func fat(n) {
          if n <= 1 { return 1 }
          return n * fat(n - 1)
        }
        func muda() { x = 99; return x }
        func le() { return x }
        print(fat(6)); print(muda()); print(x); print(le())
        """
        self.assertEqual(rodar(fonte), "720\n99\n10\n10\n")

    def test_funcao_sem_return_devolve_zero(self):
        self.assertEqual(rodar("func f() { }\nprint(f())\nfunc g() { return }\nprint(g())"), "0\n0\n")

    def test_erros_de_execucao_com_posicao(self):
        casos = [
            ("x = 1\nprint(x / 0)", 2, 9, "divisão por zero"),
            ("print(5 % 0)", 1, 9, "divisão por zero"),
            ("print(y)", 1, 7, "variável 'y' não tem valor"),
            ("func f() { if 0 { z = 1 }\nreturn z }\nf()", 2, 8, "variável 'z' não tem valor"),
            ("func f(n) { return f(n + 1) }\nf(0)", 1, 20, "chamadas demais: recursão profunda demais"),
        ]
        for fonte, linha, coluna, mensagem in casos:
            with self.subTest(fonte=fonte), self.assertRaises(ErroExecucao) as ctx:
                rodar(fonte)
            self.assertEqual(
                (ctx.exception.linha, ctx.exception.coluna, ctx.exception.mensagem),
                (linha, coluna, mensagem),
            )

    def test_limite_de_passos_interrompe_laco_infinito(self):
        maquina = Maquina(compilar("while 1 { }"), limite_passos=500)
        with self.assertRaises(ErroExecucao) as ctx:
            maquina.executar()
        self.assertEqual(ctx.exception.mensagem, "limite de passos atingido")
        self.assertEqual(maquina.passos, 500)

    def test_limite_de_saida(self):
        with self.assertRaises(ErroExecucao) as ctx:
            rodar("while 1 { print(1) }", limite=10 * MAX_SAIDA)
        self.assertEqual(ctx.exception.mensagem, "saída grande demais")

    def test_formatacao_de_zero_negativo(self):
        self.assertEqual(formatar_numero(-0.0), "0")

    def test_formatacao_de_numeros(self):
        casos = {
            0.0: "0", 3.0: "3", 0.1 + 0.2: "0.3", 1 / 3: "0.333333", -2.5: "-2.5",
            1e15: "1e+15", 2.5e20: "2.5e+20", 0.0000001: "0", -0.0000001: "0",
            999999.9999999: "1000000", float("inf"): "inf", float("-inf"): "-inf",
        }
        for valor, texto in casos.items():
            with self.subTest(valor=valor):
                self.assertEqual(formatar_numero(valor), texto)

    def test_bytecode_corrompido_nao_vira_traceback(self):
        programa = compilar("print(1)")
        programa.codigo[1] = 200
        with self.assertRaises(BytecodeInvalido):
            Maquina(programa).executar()
        with self.assertRaises(BytecodeInvalido):
            Programa.de_bytes(b"XXXX")
        with self.assertRaises(BytecodeInvalido):
            Programa.de_bytes(compilar("print(1)").para_bytes()[:12])


class LinhaDeComando(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.pasta = Path(pasta.name)

    def chamar(self, *args):
        saida, erro = io.TextIOWrapper(io.BytesIO(), encoding="utf-8"), io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(erro):
            codigo = main(list(args))
        saida.seek(0)
        erro.seek(0)
        return codigo, saida.read(), erro.read()

    def test_comandos(self):
        fonte = self.pasta / "p.lin"
        fonte.write_text("print(6 * 7)", encoding="utf-8")
        self.assertEqual(self.chamar("executar", str(fonte)), (0, "42\n", ""))
        self.assertIn("NUMERO", self.chamar("tokens", str(fonte))[1])
        self.assertIn("Operação *", self.chamar("arvore", str(fonte))[1])
        self.assertIn("MUL", self.chamar("bytecode", str(fonte))[1])
        lbc = self.pasta / "p.lbc"
        self.assertEqual(self.chamar("compilar", str(fonte), "-o", str(lbc))[0], 0)
        self.assertEqual(self.chamar("executar", str(lbc)), (0, "42\n", ""))

    def test_erro_de_sintaxe_aponta_a_coluna(self):
        fonte = self.pasta / "e.lin"
        fonte.write_text("x = (1", encoding="utf-8")
        codigo, _, erro = self.chamar("executar", str(fonte))
        self.assertEqual(codigo, 1)
        self.assertIn("Erro na linha 1, coluna 7", erro)
        self.assertTrue(erro.rstrip("\n").endswith("^"))

    def test_erro_de_execucao_mantem_saida_parcial(self):
        fonte = self.pasta / "e.lin"
        fonte.write_text("print(1)\nprint(1 / 0)", encoding="utf-8")
        codigo, saida, erro = self.chamar("executar", str(fonte))
        self.assertEqual((codigo, saida), (1, "1\n"))
        self.assertEqual(erro.strip(), "Erro na linha 2, coluna 9: divisão por zero")

    def test_limite_pela_linha_de_comando(self):
        fonte = self.pasta / "l.lin"
        fonte.write_text("while 1 { }", encoding="utf-8")
        codigo, _, erro = self.chamar("executar", str(fonte), "--passos", "100")
        self.assertEqual(codigo, 1)
        self.assertIn("limite de passos", erro)

    def test_arquivo_inexistente_e_bytecode_invalido(self):
        self.assertEqual(self.chamar("executar", str(self.pasta / "nada.lin"))[0], 2)
        lixo = self.pasta / "x.lbc"
        lixo.write_bytes(b"lixo")
        self.assertEqual(self.chamar("executar", str(lixo))[0], 2)


class Repl(unittest.TestCase):
    def test_estado_persiste_entre_entradas(self):
        sessao = Sessao()
        self.assertEqual(sessao.avaliar("x = 20"), "")
        self.assertEqual(sessao.avaliar("func dobro(n) { return n * 2 }"), "")
        self.assertEqual(sessao.avaliar("dobro(x) + 2"), "42\n")

    def test_sessao_completa(self):
        entradas = iter(["a = 5", "func f(n) {", "return n + a", "}", "f(1)", "1 +", "1 / 0", "print(a)", "sair"])
        escritas = []
        repl(ler=lambda _: next(entradas), escrever=escritas.append)
        self.assertIn("6", escritas)
        self.assertIn("5", escritas)
        self.assertTrue(any("esperava um valor" in e for e in escritas))
        self.assertTrue(any("divisão por zero" in e for e in escritas))


if __name__ == "__main__":
    unittest.main()
