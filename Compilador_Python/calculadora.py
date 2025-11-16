import re

# 1. Análise Léxica (Tokenização)
# ---

class Token:
    """Representa um elemento léxico da expressão (número ou operador)."""
    def __init__(self, tipo, valor=None):
        self.tipo = tipo  # Ex: 'NUMBER', 'PLUS', 'MINUS'
        self.valor = valor # O valor, se for um número

    def __repr__(self):
        return f"Token({self.tipo}{f', {self.valor}' if self.valor is not None else ''})"

class Lexer:
    """Divide a string de entrada em Tokens."""
    def __init__(self, expressao):
        self.expressao = expressao
        self.posicao = 0
        self.tokens = []
        self.regex_map = {
            'NUMBER': r'\d+(\.\d*)?',
            'PLUS': r'\+',
            'MINUS': r'-',
            'MULTIPLY': r'\*',
            'DIVIDE': r'/',
            'LPAREN': r'\(',
            'RPAREN': r'\)',
            'WHITESPACE': r'\s+',
        }
        self.token_types = [t for t in self.regex_map if t != 'WHITESPACE']
        self.full_regex = '|'.join(f'(?P<{tipo}>{regex})' for tipo, regex in self.regex_map.items())

    def tokenizar(self):
        """Processa a expressão e retorna uma lista de tokens."""
        for match in re.finditer(self.full_regex, self.expressao):
            tipo = match.lastgroup
            valor = match.group(tipo)

            if tipo == 'WHITESPACE':
                continue # Ignora espaços em branco

            if tipo == 'NUMBER':
                self.tokens.append(Token(tipo, float(valor)))
            elif tipo in self.token_types:
                self.tokens.append(Token(tipo, valor))
            else:
                raise ValueError(f"Caractere inválido ou token desconhecido: {valor}")

        return self.tokens

# 2. Análise Sintática (Parsing) e Avaliação
# ---

class Parser:
    """Analisa a lista de tokens e avalia a expressão."""
    def __init__(self, tokens):
        self.tokens = tokens
        self.current_token_index = 0

    def peek(self):
        """Retorna o próximo token sem avançar o índice."""
        if self.current_token_index < len(self.tokens):
            return self.tokens[self.current_token_index]
        return None

    def eat(self, tipo):
        """Consome o token atual se o tipo corresponder e avança."""
        token = self.tokens[self.current_token_index]
        if token.tipo == tipo:
            self.current_token_index += 1
            return token
        else:
            raise SyntaxError(f"Esperado {tipo}, mas encontrou {token.tipo} em {token}")

    def parse(self):
        """Inicia a análise e avaliação."""
        return self.expr()

    # Gramática: expr -> term ( (PLUS | MINUS) term )*
    def expr(self):
        """Avalia adições e subtrações."""
        resultado = self.term()

        while self.peek() and self.peek().tipo in ('PLUS', 'MINUS'):
            op = self.peek().tipo
            self.current_token_index += 1  # Consome o operador
            direito = self.term()

            if op == 'PLUS':
                resultado += direito
            elif op == 'MINUS':
                resultado -= direito
        
        return resultado

    # Gramática: term -> factor ( (MULTIPLY | DIVIDE) factor )*
    def term(self):
        """Avalia multiplicações e divisões."""
        resultado = self.factor()

        while self.peek() and self.peek().tipo in ('MULTIPLY', 'DIVIDE'):
            op = self.peek().tipo
            self.current_token_index += 1  # Consome o operador
            direito = self.factor()

            if op == 'MULTIPLY':
                resultado *= direito
            elif op == 'DIVIDE':
                if direito == 0:
                    raise ZeroDivisionError("Divisão por zero não permitida.")
                resultado /= direito
        
        return resultado

    # Gramática: factor -> NUMBER | LPAREN expr RPAREN
    def factor(self):
        """Avalia números e expressões entre parênteses."""
        token = self.peek()
        
        if token.tipo == 'NUMBER':
            self.current_token_index += 1 # Consome o número
            return token.valor

        elif token.tipo == 'LPAREN':
            self.current_token_index += 1 # Consome '('
            resultado = self.expr()       # Avalia a sub-expressão
            self.eat('RPAREN')            # Espera e consome ')'
            return resultado

        # Lidar com números negativos no início ou após '('
        elif token.tipo == 'MINUS':
            self.current_token_index += 1 # Consome '-'
            # Deve ser seguido por um fator (ex: -5 ou -(2+3))
            return -self.factor()
        
        else:
            raise SyntaxError(f"Expressão mal formada, esperado número ou '(', encontrado {token}")


# 3. Função Principal do Compilador/Avaliador
# ---

def calcular(expressao: str) -> float:
    """
    Função principal que orquestra a lexer, parser e avaliação.
    
    Args:
        expressao: A string contendo a expressão matemática (ex: "5 + 3 * (10 / 2)").
        
    Returns:
        O resultado da expressão como um float.
    """
    
    # 1. Análise Léxica (Tokenização)
    lexer = Lexer(expressao)
    tokens = lexer.tokenizar()
    # print(f"Tokens: {tokens}") # Para debug
    
    # 2. Análise Sintática e Avaliação
    parser = Parser(tokens)
    resultado = parser.parse()
    
    return resultado

# 4. Interface de Linha de Comando (REPL)
# ---

def main():
    """Loop principal para interagir com o usuário."""
    print("✨ Mini-Calculadora Compiler em Python ✨")
    print("Operações suportadas: +, -, *, /, ( )")
    print("Digite 'sair' ou 'exit' para terminar.")
    
    while True:
        try:
            expressao = input(">> ").strip()
            
            if expressao.lower() in ('sair', 'exit'):
                break
            
            if not expressao:
                continue
            
            resultado = calcular(expressao)
            print(f"Resultado: {resultado}")
            
        except (ValueError, SyntaxError) as e:
            print(f"ERRO DE SINTAXE: {e}")
        except ZeroDivisionError as e:
            print(f"ERRO MATEMÁTICO: {e}")
        except Exception as e:
            print(f"Um erro inesperado ocorreu: {e}")

if __name__ == "__main__":
    main()