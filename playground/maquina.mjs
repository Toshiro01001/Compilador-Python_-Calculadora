// Camada fina sobre o módulo WebAssembly: toda a execução acontece em c/vm.c.
export async function criarMaquina(wasm) {
  const { instance } = await WebAssembly.instantiate(wasm, {});
  const e = instance.exports;
  const texto = new TextDecoder();
  const ler = (ponteiro, tamanho) =>
    texto.decode(new Uint8Array(e.memory.buffer, ponteiro >>> 0, tamanho >>> 0));
  const vaga = (n) => (n < 0 ? null : ler(e.vm_texto(), n));

  return {
    carregar(bytes, limite) {
      if (bytes.length > e.vm_buffer_capacidade() >>> 0) return false;
      new Uint8Array(e.memory.buffer, e.vm_buffer(), bytes.length).set(bytes);
      e.vm_definir_limite(limite);
      return e.vm_carregar(bytes.length) === 0;
    },
    passo: () => e.vm_passo(),
    executar: () => e.vm_executar(),
    estado() {
      const quadros = [];
      for (let i = 0; i < e.vm_quadros(); i++) {
        quadros.push({
          base: e.vm_quadro_base(i),
          piso: e.vm_quadro_piso(i),
          funcao: e.vm_quadro_funcao(i),
        });
      }
      return {
        situacao: e.vm_situacao(),
        pc: e.vm_pc() >>> 0,
        passos: e.vm_passos() >>> 0,
        topo: e.vm_topo() >>> 0,
        linha: e.vm_linha(),
        coluna: e.vm_coluna(),
        quadros,
      };
    },
    saida: () => ler(e.vm_saida(), e.vm_saida_tamanho()),
    erro: () => ler(e.vm_erro(), e.vm_erro_tamanho()),
    pilha: (i) => vaga(e.vm_pilha_texto(i)),
    global: (i) => vaga(e.vm_global_texto(i)),
  };
}
export const RODANDO = 0;
export const TERMINOU = 1;
export const ERRO = 2;
