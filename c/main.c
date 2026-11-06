/* Executável nativo: linha_vm programa.lbc [--passos N]. Usado nos testes. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "vm.h"

int main(int argc, char **argv) {
    FILE *arquivo;
    size_t lido;
    if (argc != 2 && !(argc == 4 && strcmp(argv[2], "--passos") == 0)) {
        fprintf(stderr, "Uso: %s programa.lbc [--passos N]\n", argv[0]);
        return 2;
    }
    if (argc == 4) vm_definir_limite((uint32_t)strtoul(argv[3], NULL, 10));
    arquivo = fopen(argv[1], "rb");
    if (!arquivo) {
        fprintf(stderr, "Não foi possível ler o arquivo: %s\n", argv[1]);
        return 2;
    }
    lido = fread(vm_buffer(), 1, vm_buffer_capacidade(), arquivo);
    fclose(arquivo);
    if (vm_carregar((uint32_t)lido) != 0) {
        fprintf(stderr, "Bytecode inválido: arquivo cortado ou corrompido\n");
        return 2;
    }
    int32_t estado = vm_executar();
    fwrite(vm_saida(), 1, vm_saida_tamanho(), stdout);
    if (estado == VM_ERRO) {
        fprintf(stderr, "Erro na linha %u, coluna %u: %.*s\n", vm_linha(), vm_coluna(),
                (int)vm_erro_tamanho(), (const char *)vm_erro());
        return 1;
    }
    return 0;
}
