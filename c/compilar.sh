#!/bin/sh
# Compila a máquina de pilha para WebAssembly e para executáveis nativos.
#   c/compilar.sh          tudo
#   c/compilar.sh wasm     só playground/vm.wasm
#   c/compilar.sh nativo   só c/build/ (normal, com sanitizers e fuzz)
set -eu
cd "$(dirname "$0")/.."
ALVO="${1:-tudo}"
AVISOS="-Wall -Wextra -Werror -Wconversion -std=c11"

if [ "$ALVO" = tudo ] || [ "$ALVO" = wasm ]; then
    mkdir -p c/build
    SAIDA="${SAIDA_WASM:-playground/vm.wasm}"
    # shellcheck disable=SC2086
    clang --target=wasm32 -nostdlib -ffreestanding -fno-builtin -O2 -ffp-contract=off \
        $AVISOS -c c/vm.c -o c/build/vm_wasm.o
    # Sem importações: o módulo não enxerga rede, arquivos nem a página.
    EXPORTS=""
    for nome in vm_buffer vm_buffer_capacidade vm_carregar vm_reiniciar vm_definir_limite \
        vm_passo vm_executar vm_situacao vm_pc vm_passos vm_topo vm_quadros vm_quadro_base vm_quadro_piso \
        vm_quadro_funcao vm_linha vm_coluna vm_saida vm_saida_tamanho vm_erro vm_erro_tamanho \
        vm_texto vm_formatar vm_pilha_texto vm_global_texto; do
        EXPORTS="$EXPORTS --export=$nome"
    done
    # shellcheck disable=SC2086
    wasm-ld --no-entry --strip-all -z stack-size=65536 \
        --initial-memory=2097152 --max-memory=2097152 $EXPORTS \
        c/build/vm_wasm.o -o "$SAIDA"
    echo "WebAssembly: $SAIDA ($(wc -c < "$SAIDA") bytes)"
fi

if [ "$ALVO" = tudo ] || [ "$ALVO" = nativo ]; then
    mkdir -p c/build
    # shellcheck disable=SC2086
    gcc -O2 -ffp-contract=off $AVISOS c/vm.c c/main.c -lm -o c/build/linha_vm
    SAN="-g -O1 -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer"
    # shellcheck disable=SC2086
    gcc $SAN -ffp-contract=off $AVISOS c/vm.c c/main.c -lm -o c/build/linha_vm_san
    # shellcheck disable=SC2086
    gcc $SAN -ffp-contract=off $AVISOS c/vm.c c/fuzz.c -lm -o c/build/fuzz_san
    echo "Nativos: c/build/linha_vm, c/build/linha_vm_san, c/build/fuzz_san"
fi
