/* Máquina de pilha da linguagem Linha: sem libc, sem malloc, só memória estática.
   O mesmo vm.c vira WebAssembly (navegador) e executável nativo (testes). */
#ifndef LINHA_VM_H
#define LINHA_VM_H

#include <stdint.h>

#define VM_RODANDO 0
#define VM_TERMINOU 1
#define VM_ERRO 2

uint8_t *vm_buffer(void);          /* onde gravar o bytecode antes de vm_carregar */
uint32_t vm_buffer_capacidade(void);
int32_t vm_carregar(uint32_t tamanho); /* 0 se válido; 1 se o arquivo é inválido */
void vm_reiniciar(void);
void vm_definir_limite(uint32_t passos);
int32_t vm_passo(void);            /* executa uma instrução */
int32_t vm_executar(void);         /* executa até terminar, falhar ou bater no limite */

int32_t vm_situacao(void);        /* VM_RODANDO, VM_TERMINOU ou VM_ERRO */
uint32_t vm_pc(void);
uint32_t vm_passos(void);
uint32_t vm_topo(void);            /* quantidade de valores na pilha */
uint32_t vm_quadros(void);
uint32_t vm_quadro_base(uint32_t i);
uint32_t vm_quadro_piso(uint32_t i);
uint32_t vm_quadro_funcao(uint32_t i);
uint32_t vm_linha(void);           /* posição da instrução atual no código-fonte */
uint32_t vm_coluna(void);

const uint8_t *vm_saida(void);
uint32_t vm_saida_tamanho(void);
const uint8_t *vm_erro(void);
uint32_t vm_erro_tamanho(void);

const uint8_t *vm_texto(void);     /* resultado das três funções abaixo */
uint32_t vm_formatar(double x);
int32_t vm_pilha_texto(uint32_t i);  /* tamanho do texto, ou -1 se a vaga está sem valor */
int32_t vm_global_texto(uint32_t i);

#endif
