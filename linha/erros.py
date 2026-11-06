"""Erros da linguagem. Todos carregam a linha e a coluna do problema."""


class ErroLinha(Exception):
    """Erro com posição no código-fonte (linha e coluna começam em 1)."""

    def __init__(self, mensagem: str, linha: int, coluna: int) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.linha = linha
        self.coluna = coluna

    def __str__(self) -> str:
        return f"Erro na linha {self.linha}, coluna {self.coluna}: {self.mensagem}"

    def apontar(self, fonte: str) -> str:
        """Devolve a mensagem com a linha do código e um ^ sob a coluna."""
        linhas = fonte.split("\n")
        if not 1 <= self.linha <= len(linhas):
            return str(self)
        margem = f"{self.linha} | "
        texto = linhas[self.linha - 1].rstrip("\r")
        return f"{self}\n{margem}{texto}\n{' ' * (len(margem) + self.coluna - 1)}^"


class ErroLexico(ErroLinha):
    """Caractere ou número que a linguagem não reconhece."""


class ErroSintaxe(ErroLinha):
    """Tokens válidos em uma ordem que a gramática não aceita."""


class ErroSemantico(ErroLinha):
    """Programa bem formado, mas sem sentido: função inexistente, por exemplo."""


class ErroExecucao(ErroLinha):
    """Problema durante a execução: divisão por zero, limite de passos etc."""


class BytecodeInvalido(Exception):
    """Arquivo de bytecode corrompido ou que não veio deste compilador."""
