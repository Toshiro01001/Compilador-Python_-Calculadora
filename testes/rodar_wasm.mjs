// Ponte de teste. Lê casos em JSON da entrada padrão e devolve, para cada um, o
// que o compilador em JavaScript e a máquina em WebAssembly produziram.
// Com --exemplos, só lista os exemplos do playground.
import { readFileSync } from "node:fs";
import { compilar, tokenizar, ErroLinha } from "../playground/compilador.mjs";
import { EXEMPLOS } from "../playground/exemplos.mjs";
import { criarMaquina, RODANDO, ERRO } from "../playground/maquina.mjs";

if (process.argv.includes("--exemplos")) {
  console.log(JSON.stringify(EXEMPLOS));
  process.exit(0);
}

const wasm = readFileSync(new URL("../playground/vm.wasm", import.meta.url));
const maquina = await criarMaquina(wasm);
const { casos, limite } = JSON.parse(readFileSync(0, "utf-8"));

function resultadoDa(estadoFinal) {
  const e = maquina.estado();
  return {
    saida: maquina.saida(),
    passos: e.passos,
    erro: estadoFinal === ERRO ? `Erro na linha ${e.linha}, coluna ${e.coluna}: ${maquina.erro()}` : null,
  };
}

const respostas = casos.map((fonte) => {
  const r = {};
  try {
    r.tokens = tokenizar(fonte).map((t) => [t.tipo, t.texto, t.linha, t.coluna]);
    const c = compilar(fonte);
    r.bytes = Buffer.from(c.bytes).toString("hex");
    maquina.carregar(c.bytes, limite);
    r.tudo = resultadoDa(maquina.executar());
    // O modo passo a passo do playground precisa chegar ao mesmo resultado.
    maquina.carregar(c.bytes, limite);
    let estado = RODANDO;
    while (estado === RODANDO) estado = maquina.passo();
    r.passoAPasso = resultadoDa(estado);
  } catch (erro) {
    if (!(erro instanceof ErroLinha)) throw erro;
    r.erroCompilacao = erro.texto();
  }
  return r;
});
console.log(JSON.stringify(respostas));
