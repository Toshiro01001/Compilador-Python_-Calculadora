# 🧮 Simple-Calculator-Compiler

Um projeto simples em Python que simula as etapas de um compilador (Análise Léxica e Análise Sintática) para interpretar e avaliar expressões matemáticas básicas.

Esta ferramenta funciona como uma calculadora interativa (REPL - Read-Eval-Print Loop) que suporta as quatro operações fundamentais e o uso de parênteses.

## 🚀 Funcionalidades

- **Operações Suportadas:** Adição (`+`), Subtração (`-`), Multiplicação (`*`), e Divisão (`/`).
- **Precedência de Operadores:** Respeita a ordem matemática padrão (multiplicação e divisão antes de adição e subtração).
- **Parênteses:** Suporte para agrupar expressões e alterar a ordem de avaliação.
- **Números Decimais:** Lida com números de ponto flutuante.

## ⚙️ Estrutura do "Compilador"

Embora seja um avaliador/interpretador, o código está organizado seguindo os princípios de um compilador:

1.  ### Análise Léxica (Lexer)

    - Implementada pela classe `Lexer`.
    - **Propósito:** Recebe a string de entrada (ex: `"5 + 3 * 2"`) e a transforma em uma lista de **Tokens** (unidades léxicas) como `NUMBER`, `PLUS`, `MULTIPLY`, etc.

2.  ### Análise Sintática e Avaliação (Parser)
    - Implementada pela classe `Parser`.
    - **Propósito:** Lê a sequência de tokens, verifica se a expressão é gramaticalmente válida e, simultaneamente, avalia o resultado.
    - **Método:** Utiliza a técnica de **Recursive Descent Parsing** para impor a correta precedência de operadores.

## 💻 Como Executar

### Pré-requisitos

Você precisa ter o Python 3 instalado no seu sistema.

### Execução

1.  Clone este repositório para a sua máquina local:

    ```bash
    git clone [https://www.youtube.com/watch?v=w1RGT6FpXyY](https://www.youtube.com/watch?v=w1RGT6FpXyY)
    cd Simple-Calculator-Compiler
    ```

2.  Execute o script principal:
    ```bash
    python calculator_compiler.py
    ```

### Modo de Uso (REPL)

Após executar o script, você verá o prompt `>>`. Digite sua expressão e pressione Enter:

---

Desenvolvido por Rodrigo Terroso Junior. O Claude, da Anthropic, foi usado como ferramenta durante o desenvolvimento.
