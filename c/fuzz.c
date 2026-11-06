/* Teste de robustez: corrompe bytecode válido e executa sob ASan/UBSan.
   Uso: fuzz iteracoes programa.lbc [mais.lbc ...]. Sucesso é não abortar. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "vm.h"

static uint32_t estado_rng = 0x1234ABCDu;

static uint32_t sorteio(void) {
    estado_rng ^= estado_rng << 13;
    estado_rng ^= estado_rng >> 17;
    estado_rng ^= estado_rng << 5;
    return estado_rng;
}

static uint8_t sementes[64][1u << 16];
static uint32_t tamanhos[64];

int main(int argc, char **argv) {
    unsigned long iteracoes;
    unsigned long aceitos = 0;
    int n = 0;
    if (argc < 3) return 2;
    iteracoes = strtoul(argv[1], NULL, 10);
    for (int i = 2; i < argc && n < 64; i++) {
        FILE *f = fopen(argv[i], "rb");
        if (!f) return 2;
        tamanhos[n] = (uint32_t)fread(sementes[n], 1, sizeof sementes[n], f);
        fclose(f);
        n++;
    }
    vm_definir_limite(5000);
    for (unsigned long it = 0; it < iteracoes; it++) {
        uint32_t s = sorteio() % (uint32_t)n, tam = tamanhos[s];
        uint32_t trocas = 1 + sorteio() % 8;
        memcpy(vm_buffer(), sementes[s], tam);
        for (uint32_t k = 0; k < trocas && tam; k++) {
            /* Depois da assinatura, para que a maioria chegue a executar. */
            uint32_t i = 4 + sorteio() % (tam > 4 ? tam - 4 : 1);
            if (i < tam) vm_buffer()[i] = (uint8_t)sorteio();
        }
        if (sorteio() % 8 == 0 && tam) tam = sorteio() % tam;
        if (vm_carregar(tam) != 0) continue;
        aceitos++;
        vm_executar();
        (void)vm_linha();
        for (uint32_t i = 0; i < vm_topo() && i < 8; i++) (void)vm_pilha_texto(i);
        for (uint32_t i = 0; i < vm_quadros() && i < 8; i++) (void)vm_quadro_base(i);
        (void)vm_global_texto(0);
    }
    printf("%lu iterações, %lu aceitas pelo carregador\n", iteracoes, aceitos);
    return 0;
}
