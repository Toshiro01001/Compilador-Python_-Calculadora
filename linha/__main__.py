"""Linha de comando: python -m linha <comando> [arquivo]."""

import argparse
import sys
from pathlib import Path

from .arvore import desenhar
from .bytecode import Programa
from .compilador import compilar
from .erros import BytecodeInvalido, ErroExecucao, ErroLinha
from .lexer import tokenizar
from .maquina import LIMITE_PADRAO, Maquina
from .parser import analisar
from .repl import repl


def _executar(args: argparse.Namespace, fonte: str) -> int:
    if args.arquivo.endswith(".lbc"):
        programa = Programa.de_bytes(Path(args.arquivo).read_bytes())
    else:
        programa = compilar(fonte)
    maquina = Maquina(programa, limite_passos=args.passos)
    try:
        maquina.executar()
    finally:
        sys.stdout.write("".join(maquina.saida))
    return 0


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    geral = argparse.ArgumentParser(prog="python -m linha", description="Compilador da linguagem Linha.")
    comandos = geral.add_subparsers(dest="comando", required=True)
    for nome, ajuda in [
        ("executar", "compila e executa um arquivo .lin (ou executa um .lbc)"),
        ("tokens", "mostra os tokens"),
        ("arvore", "mostra a árvore sintática"),
        ("bytecode", "mostra o bytecode em texto"),
        ("compilar", "grava o bytecode em um arquivo .lbc"),
    ]:
        sub = comandos.add_parser(nome, help=ajuda)
        sub.add_argument("arquivo")
        if nome == "executar":
            sub.add_argument("--passos", type=int, default=LIMITE_PADRAO, help="limite de instruções")
        if nome == "compilar":
            sub.add_argument("-o", dest="saida", required=True, help="arquivo de saída")
    comandos.add_parser("repl", help="abre o modo interativo")
    args = geral.parse_args(argv)

    if args.comando == "repl":
        repl()
        return 0

    fonte = ""
    try:
        if not args.arquivo.endswith(".lbc"):
            fonte = Path(args.arquivo).read_text(encoding="utf-8")
        if args.comando == "executar":
            return _executar(args, fonte)
        if args.comando == "tokens":
            for t in tokenizar(fonte):
                print(f"{t.linha}:{t.coluna}\t{t.tipo}\t{t.texto!r}")
        elif args.comando == "arvore":
            print(desenhar(analisar(fonte)))
        elif args.comando == "bytecode":
            print(compilar(fonte).desmontar())
        elif args.comando == "compilar":
            Path(args.saida).write_bytes(compilar(fonte).para_bytes())
    except ErroExecucao as erro:
        print(erro, file=sys.stderr)
        return 1
    except ErroLinha as erro:
        print(erro.apontar(fonte), file=sys.stderr)
        return 1
    except BytecodeInvalido as erro:
        print(f"Bytecode inválido: {erro}", file=sys.stderr)
        return 2
    except OSError as erro:
        print(f"Não foi possível ler o arquivo: {erro}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
