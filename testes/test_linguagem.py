"""Lexer, parser e compilador em Python."""

import unittest

from linha import (
    ErroLexico,
    ErroSemantico,
    ErroSintaxe,
    Programa,
    analisar,
    compilar,
    tokenizar,
)
from linha import arvore as a
from linha.bytecode import OP


class Lexer(unittest.TestCase):
    def test_tipos_e_posicoes(self):
        tokens = tokenizar("x = 1.5\nif x >= 2 { }")
        self.assertEqual(
            [(t.tipo, t.linha, t.coluna) for t in tokens],
            [("NOME", 1, 1), ("=", 1, 3), ("NUMERO", 1, 5), ("FIM_LINHA", 1, 8),
             ("if", 2, 1), ("NOME", 2, 4), (">=", 2, 6), ("NUMERO", 2, 9),
             ("{", 2, 11), ("}", 2, 13), ("FIM", 2, 14)],
        )

    def test_comentarios_e_acentos(self):
        tipos = [t.texto for t in tokenizar("preço = 1 # ação não é código")]
        self.assertEqual(tipos, ["preço", "=", "1", ""])

    def test_quebra_de_linha_dentro_de_parenteses_nao_conta(self):
        tipos = [t.tipo for t in tokenizar("(1 +\n2)")]
        self.assertNotIn("FIM_LINHA", tipos)

    def test_caractere_invalido_aponta_posicao(self):
        with self.assertRaises(ErroLexico) as ctx:
            tokenizar("x = 1\ny = 2 @ 3")
        self.assertEqual((ctx.exception.linha, ctx.exception.coluna), (2, 7))

    def test_numero_incompleto(self):
        with self.assertRaises(ErroLexico) as ctx:
            tokenizar("x = 12.")
        self.assertEqual(ctx.exception.coluna, 5)


class Parser(unittest.TestCase):
    def test_precedencia(self):
        no = analisar("1 + 2 * 3").itens[0].valor
        self.assertEqual(no.op, "+")
        self.assertEqual(no.direita.op, "*")

    def test_associatividade_a_esquerda(self):
        no = analisar("8 - 3 - 2").itens[0].valor
        self.assertEqual(no.esquerda.op, "-")

    def test_comparacao_abaixo_da_soma(self):
        self.assertEqual(analisar("1 + 2 < 4").itens[0].valor.op, "<")

    def test_else_em_outra_linha_e_else_if(self):
        no = analisar("if 1 { }\nelse if 2 { } else { print(3) }").itens[0]
        self.assertIsInstance(no.senao[0], a.Se)
        self.assertIsInstance(no.senao[0].senao[0], a.Imprime)

    def casos_de_erro(self):
        return [
            ("x = 10 +\nprint(x)", 1, 9, "esperava um valor, mas encontrei o fim da linha"),
            ("print(1", 1, 8, "esperava ')' para fechar o print, mas encontrei o fim do programa"),
            ("if 1 print(2)", 1, 6, "esperava '{' para abrir o bloco, mas encontrei 'print'"),
            ("while 1 {", 1, 10, "esperava '}' para fechar o bloco, mas o programa acabou"),
            ("x = 1 y = 2", 1, 7, "esperava o fim da instrução, mas encontrei 'y'"),
            ("else { }", 1, 1, "'else' sem um 'if' antes"),
            ("if 1 { func f() { } }", 1, 8, "funções só podem ser declaradas fora de blocos"),
            ("func f(a, a) { }", 1, 11, "parâmetro 'a' repetido"),
        ]

    def test_erros_com_linha_e_coluna(self):
        for fonte, linha, coluna, mensagem in self.casos_de_erro():
            with self.subTest(fonte=fonte), self.assertRaises(ErroSintaxe) as ctx:
                analisar(fonte)
            self.assertEqual(
                (ctx.exception.linha, ctx.exception.coluna, ctx.exception.mensagem),
                (linha, coluna, mensagem),
            )

    def test_aninhamento_patologico_nao_estoura_a_recursao(self):
        for fonte in ("(" * 5000, "-" * 5000 + "1", "if 1 {" * 5000):
            with self.subTest(fonte=fonte[:10]), self.assertRaises(ErroSintaxe) as ctx:
                analisar(fonte)
            self.assertIn("aninhamento", ctx.exception.mensagem)

    def test_expressao_gigante_tem_limite(self):
        with self.assertRaises(ErroSintaxe) as ctx:
            analisar("1" + " + 1" * 5000)
        self.assertIn("longa demais", ctx.exception.mensagem)

    def test_apontar_mostra_a_coluna(self):
        with self.assertRaises(ErroSintaxe) as ctx:
            analisar("x = (1")
        self.assertEqual(ctx.exception.apontar("x = (1").splitlines()[-1], " " * 10 + "^")


class Compilador(unittest.TestCase):
    def test_soma_vira_bytecode_de_pilha(self):
        p = compilar("print(1 + 2)")
        ops = [OP["CONST"], 0, 0, OP["CONST"], 1, 0, OP["SOMA"], OP["IMPRIME"], OP["PARA"]]
        self.assertEqual(list(p.codigo), ops)
        self.assertEqual(p.constantes, [1.0, 2.0])

    def test_constantes_repetidas_sao_reaproveitadas(self):
        self.assertEqual(compilar("print(7); print(7)").constantes, [7.0])

    def test_nome_atribuido_na_funcao_e_local(self):
        p = compilar("x = 1\nfunc f() { x = 2; return x }\nf()")
        self.assertEqual(p.globais, 1)
        self.assertEqual(p.funcoes[0].locais, 1)

    def test_funcao_pode_ser_usada_antes_da_declaracao(self):
        compilar("print(f())\nfunc f() { return 1 }")

    def test_erros_semanticos(self):
        casos = [
            ("print(g(1))", 1, 7, "função 'g' não existe"),
            ("func f(a) { }\nf()", 2, 1, "função 'f' espera 1 argumento(s), mas recebeu 0"),
            ("return 1", 1, 1, "'return' fora de uma função"),
            ("func f() { }\nfunc f() { }", 2, 1, "função 'f' declarada mais de uma vez"),
        ]
        for fonte, linha, coluna, mensagem in casos:
            with self.subTest(fonte=fonte), self.assertRaises(ErroSemantico) as ctx:
                compilar(fonte)
            self.assertEqual(
                (ctx.exception.linha, ctx.exception.coluna, ctx.exception.mensagem),
                (linha, coluna, mensagem),
            )

    def test_bytes_vao_e_voltam(self):
        original = compilar("func f(a) { b = a * 2; return b }\nprint(f(21))\ny = 1").para_bytes()
        self.assertEqual(Programa.de_bytes(original).para_bytes(), original)

    def test_desmontagem_lista_as_instrucoes(self):
        texto = compilar("x = 2").desmontar()
        self.assertIn("CONST", texto)
        self.assertIn("GRAVA_GLOBAL", texto)
        self.assertIn("x; linha 1", texto)


if __name__ == "__main__":
    unittest.main()
