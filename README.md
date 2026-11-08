# Mini compilador: linguagem Linha

![Mini Compilador com o editor e os tokens da linguagem](docs/tela.webp)

## O que é isto

Um compilador é o programa que traduz um texto escrito por pessoas para instruções simples que o computador executa. Eu fiz um compilador completo, do zero, para uma linguagem pequena que chamei de Linha. Ele roda direto no navegador: você escreve uma regra ou uma conta em texto simples, aperta Executar e vê o resultado e cada etapa da tradução, dos tokens até a execução instrução por instrução.

Esta é uma demonstração do que a Mil e Uma Linhas! sabe fazer. Os exemplos usam valores inventados (preços, juros, números de documento) e nada é vendido, cobrado ou salvo. Nada do que você digita sai do seu navegador.

O projeto nasceu de uma calculadora acadêmica, que continua em `Compilador_Python/calculadora.py`.

## Como usar o site

1. Abra a página publicada em <https://toshiro01001.github.io/Compilador-Python_-Calculadora/>.
2. Escolha um exemplo na lista **Exemplo** ou escreva o seu próprio programa na caixa **Programa**.
3. Aperte **Executar** (ou Ctrl+Enter). O resultado aparece em **Saída**. Se houver erro, a página aponta a linha e a coluna.
4. As abas **Tokens**, **Árvore**, **Bytecode** e **Execução** mostram cada etapa da tradução. Na aba Execução, **Próximo passo** roda uma instrução por vez e mostra a pilha de valores e as variáveis.
5. **Limite de passos** é um freio: se um programa repetir para sempre, ele para ao chegar a esse número, em vez de travar a página.

## Por que isso interessa a uma empresa

- **Regras de negócio configuráveis.** Comissão, desconto ou frete podem virar um pequeno texto editável, em vez de exigir uma nova versão do sistema a cada mudança de política.
- **Fórmulas.** O usuário escreve a conta do jeito dele, como em uma planilha, e o sistema executa sempre do mesmo modo, em qualquer aparelho.
- **Validação.** Um texto errado é recusado antes de rodar, com a linha e a coluna do problema.
- **Segurança.** O programa digitado só conhece as instruções da máquina: sem acesso a rede, arquivos ou à página, e com limite de passos contra laço infinito.

## O que a linguagem faz

```text
# Números, variáveis, contas e comparações
total = 1250

func desconto(valor) {
  if valor >= 1000 {
    return valor * 0.10
  }
  return 0
}

i = 0
while i < 3 {
  print(total - desconto(total) + i)
  i = i + 1
}
```

- Números com ponto decimal, variáveis e os operadores `+ - * / %`.
- Comparações `== != < <= > >=`, que dão 1 ou 0. Em `if` e `while`, zero é falso e o resto é verdadeiro.
- `if`, `else`, `else if`, `while`, funções com recursão, `return` e `print`.
- Erros de sintaxe e de execução apontam linha e coluna.

## Como funciona por dentro

A tradução acontece em quatro etapas, as mesmas das abas do site.

1. **Lexer** (o leitor): separa o texto em tokens, as peças pequenas como números, nomes e sinais, e guarda a posição de cada uma.
2. **Parser recursivo** (o analisador): confere se o texto segue a gramática e monta a árvore sintática (AST), já com a precedência certa das contas.
3. **Compilador**: percorre a árvore e gera bytecode, uma lista de instruções curtas em um formato binário único, descrito em `linha/bytecode.py`.
4. **Máquina de pilha** (o executor): executa o bytecode guardando os valores em uma pilha, com limite de passos contra laço infinito.

Fiz tudo isso três vezes de propósito: em Python, em JavaScript e com a máquina virtual em C compilada para WebAssembly (código que o navegador roda quase na velocidade de um programa instalado).

| Parte | Python | Navegador |
| --- | --- | --- |
| Lexer, parser e bytecode | `linha/` | `playground/compilador.mjs` |
| Máquina de pilha | `linha/maquina.py` | `c/vm.c` compilado em `playground/vm.wasm` |

O teste cruzado exige que os dois compiladores gerem exatamente os mesmos bytes e que as máquinas em Python, C nativo e WebAssembly deem a mesma saída, o mesmo erro e a mesma contagem de passos.

O módulo WebAssembly não tem nenhuma importação: ele não enxerga rede, arquivos nem a página. O código digitado nunca passa por `eval`, e a página tem uma política de segurança (CSP) que bloqueia terceiros.

## Como rodar no seu computador

**Playground.** Sirva a raiz do repositório e abra o endereço no navegador. Não há etapa de build. No GitHub Pages, publique a raiz do ramo `main`.

```bash
python3 -m http.server 8000
```

**Linha de comando.** Precisa de Python 3.10 ou mais novo, sem dependências.

```bash
python3 -m linha executar programa.lin     # compila e executa
python3 -m linha tokens programa.lin       # mostra os tokens
python3 -m linha arvore programa.lin       # mostra a árvore
python3 -m linha bytecode programa.lin     # mostra o bytecode
python3 -m linha compilar programa.lin -o programa.lbc
python3 -m linha repl                      # modo interativo
```

**Máquina em C.** O script gera o `.wasm` com `clang --target=wasm32 -nostdlib` e `wasm-ld`, e os executáveis nativos com `gcc`.

```bash
c/compilar.sh                              # tudo
c/build/linha_vm programa.lbc
```

**Testes.**

```bash
python3 -m unittest discover -s testes -t .
NODE_PATH=$(npm root -g) node testes/navegador.cjs
```

A primeira linha roda os testes de unidade, o teste cruzado com os executáveis em C (um deles com `-fsanitize=address,undefined`) e o teste com bytecode corrompido. A segunda percorre o playground em computador e celular com Playwright e Chromium já instalados.

## Tecnologias

Python 3 (só biblioteca padrão), C11 sem libc na máquina virtual, WebAssembly, JavaScript em módulos, HTML, CSS e SVG, `unittest`, Playwright, AddressSanitizer e UBSan.

Desenvolvi este projeto e usei o Claude, da Anthropic, como ferramenta durante o desenvolvimento.
