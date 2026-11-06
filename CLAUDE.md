# Mini compilador: linguagem Linha

Compilador de uma linguagem pequena, com pacote em Python (`linha/`), máquina de pilha em C (`c/vm.c`, compilada para `playground/vm.wasm`) e playground no navegador (`index.html` e `playground/`). A calculadora original fica em `Compilador_Python/calculadora.py`.

## Como este projeto funciona

- Rode com `python3 -m linha executar programa.lin` ou `python3 -m linha repl`. O playground é a raiz do repositório servida por HTTP, sem build.
- Python e JavaScript têm o mesmo compilador, e Python e C têm a mesma máquina: toda mudança na linguagem precisa ser feita nos dois lados, com as mesmas mensagens e limites.
- Depois de alterar `c/vm.c`, rode `c/compilar.sh` e versione o novo `playground/vm.wasm`.
- Testes: `python3 -m unittest discover -s testes -t .` e `NODE_PATH=$(npm root -g) node testes/navegador.cjs`.
- Os arquivos `.docx` na raiz são trabalhos acadêmicos: não os altere.

## Regras de trabalho

- Responda em português do Brasil, sem travessões, e chame o dono de Rodrigo Jr.
- Altere só o que foi pedido. Publicar ou fazer merge no `main` depende de pedido dele.
- Ao terminar uma alteração, entregue a mensagem de commit em dois blocos rotulados: "Título" (até 50 caracteres) e "Descrição" (estendida, com exatamente o que foi feito).
- Entregue arquivos soltos, nunca em `.zip`.
- O repositório é público: não coloque senhas, chaves secretas nem dados pessoais em arquivos versionados.
