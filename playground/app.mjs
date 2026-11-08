// Interface do playground. Dado variável entra sempre por textContent.
import { compilar, tokenizar, ErroLinha } from "./compilador.mjs";
import { EXEMPLOS } from "./exemplos.mjs";
import { criarMaquina, RODANDO, TERMINOU, ERRO } from "./maquina.mjs";

const $ = (id) => document.getElementById(id);
const SVG_NS = "http://www.w3.org/2000/svg";
const MAX_CARTOES = 40;
const MAX_TOKENS = 1500;
const MAX_LINHAS_BYTECODE = 3000;
const MAX_NOS_ARVORE = 600;

const editor = $("codigo");
const camada = $("camada");
const margem = $("margem");
let maquina = null;
let resultado = null;     // saída de compilar(), ou null se há erro
let erroAtual = null;     // { linha, coluna } marcado no editor
let linhaMarcada = null;  // linha da instrução em execução
let carregado = false;    // bytecode atual já está na máquina
let abaAtiva = "tokens";

function el(tag, classe, texto) {
  const n = document.createElement(tag);
  if (classe) n.className = classe;
  if (texto !== undefined) n.textContent = texto;
  return n;
}

function limpar(n) {
  n.replaceChildren();
  return n;
}

// Editor: uma camada colorida atrás de um textarea com texto transparente.
const PADRAO_TOKEN = /#[^\n]*|\d+(?:\.\d+)?|[A-Za-z_À-ÿ][\wÀ-ÿ]*|==|!=|<=|>=|[+\-*/%=<>(){},;]|[^\S\n]+|./gu;
const CLASSES_PALAVRA = new Set(["if", "else", "while", "func", "return", "print"]);

function classeDe(trecho) {
  if (trecho[0] === "#") return "t-comentario";
  if (/^\d/.test(trecho)) return "t-numero";
  if (CLASSES_PALAVRA.has(trecho)) return "t-palavra";
  if (/^[+\-*/%=<>!]/.test(trecho)) return "t-operador";
  return "";
}

function desenharEditor() {
  const linhas = editor.value.split("\n");
  const frag = document.createDocumentFragment();
  const numeros = document.createDocumentFragment();
  linhas.forEach((linha, i) => {
    const numero = i + 1;
    const div = el("div", "linha");
    const erroAqui = erroAtual && erroAtual.linha === numero ? erroAtual.coluna : null;
    let coluna = 1;
    let marcou = false;
    for (const m of linha.matchAll(PADRAO_TOKEN)) {
      const trecho = m[0];
      const fim = coluna + trecho.length;
      if (erroAqui !== null && !marcou && erroAqui >= coluna && erroAqui < fim) {
        const antes = trecho.slice(0, erroAqui - coluna);
        if (antes) div.append(el("span", classeDe(trecho), antes));
        div.append(el("span", `${classeDe(trecho)} t-erro`, trecho.slice(erroAqui - coluna)));
        marcou = true;
      } else {
        div.append(el("span", classeDe(trecho), trecho));
      }
      coluna = fim;
    }
    if (erroAqui !== null && !marcou) div.append(el("span", "t-erro", " "));
    if (numero === linhaMarcada) div.classList.add("marcada");
    frag.append(div);
    const n = el("div", "", String(numero));
    if (erroAqui !== null) n.className = "numero-erro";
    numeros.append(n);
  });
  limpar(camada).append(frag);
  limpar(margem).append(numeros);
  margem.style.setProperty("--digitos", String(String(linhas.length).length));
  sincronizarRolagem();
}

function sincronizarRolagem() {
  camada.style.transform = `translate(${-editor.scrollLeft}px, ${-editor.scrollTop}px)`;
  margem.style.transform = `translateY(${-editor.scrollTop}px)`;
}

// Abas
const ABAS = ["tokens", "arvore", "bytecode", "execucao"];

function ativarAba(nome, focar = false) {
  abaAtiva = nome;
  for (const a of ABAS) {
    const aba = $(`aba-${a}`);
    const sel = a === nome;
    aba.setAttribute("aria-selected", String(sel));
    aba.tabIndex = sel ? 0 : -1;
    $(`painel-${a}`).hidden = !sel;
  }
  if (focar) $(`aba-${nome}`).focus();
  desenharAba();
}

function desenharAba() {
  if (abaAtiva === "tokens") desenharTokens();
  else if (abaAtiva === "arvore") desenharArvore();
  else if (abaAtiva === "bytecode") desenharBytecode();
  else desenharExecucao();
}

function aviso(alvo, texto) {
  limpar(alvo).append(el("p", "aviso", texto));
}

function avisoErro(alvo, oQueFalta) {
  aviso(alvo, `Corrija o erro da linha ${erroAtual.linha} para ver ${oQueFalta}.`);
}

// Aba Tokens
const NOME_TIPO = { NUMERO: "número", NOME: "nome", FIM_LINHA: "fim de linha", FIM: "fim" };

function desenharTokens() {
  const alvo = $("painel-tokens-corpo");
  let tokens;
  try {
    tokens = tokenizar(editor.value);
  } catch (erro) {
    if (!(erro instanceof ErroLinha)) throw erro;
    aviso(alvo, `O leitor parou na linha ${erro.linha}, coluna ${erro.coluna}: ${erro.mensagem}. Corrija o programa para ver os tokens.`);
    return;
  }
  limpar(alvo);
  const lista = el("ol", "fita");
  for (const t of tokens.slice(0, MAX_TOKENS)) {
    const palavra = /^[a-z]/.test(t.tipo);
    const tipo = NOME_TIPO[t.tipo] ?? (palavra ? "palavra" : "símbolo");
    const item = el("li", `ficha ficha-${palavra ? "palavra" : t.tipo === "NUMERO" ? "numero" : t.tipo === "NOME" ? "nome" : "simbolo"}`);
    item.append(el("span", "ficha-valor", t.tipo === "FIM_LINHA" ? "↵" : t.tipo === "FIM" ? "fim" : t.texto));
    item.append(el("span", "ficha-tipo", tipo));
    item.append(el("span", "ficha-pos", `${t.linha}:${t.coluna}`));
    lista.append(item);
  }
  alvo.append(lista);
  if (tokens.length > MAX_TOKENS) {
    alvo.append(el("p", "aviso", `Mostrando ${MAX_TOKENS} de ${tokens.length} tokens.`));
  }
}

// Aba Árvore: layout próprio em SVG. As folhas ocupam colunas; cada pai centraliza.
function noVisual(rotulo, classe, filhos = []) {
  return { rotulo, classe, filhos };
}

function converter(no) {
  switch (no.tipo) {
    case "Programa": return noVisual("Programa", "instr", no.itens.map(converter));
    case "Funcao": return noVisual(`func ${no.nome}(${no.parametros.join(", ")})`, "func", no.corpo.map(converter));
    case "Se": {
      const filhos = [noVisual("condição", "grupo", [converter(no.condicao)]),
        noVisual("então", "grupo", no.entao.map(converter))];
      if (no.senao) filhos.push(noVisual("senão", "grupo", no.senao.map(converter)));
      return noVisual("if", "instr", filhos);
    }
    case "Enquanto":
      return noVisual("while", "instr", [noVisual("condição", "grupo", [converter(no.condicao)]),
        noVisual("corpo", "grupo", no.corpo.map(converter))]);
    case "Atribuicao": return noVisual(`${no.nome} =`, "instr", [converter(no.valor)]);
    case "Imprime": return noVisual("print", "instr", [converter(no.valor)]);
    case "Retorna": return noVisual("return", "instr", no.valor ? [converter(no.valor)] : []);
    case "ExpressaoSolta": return converter(no.valor);
    case "Binaria": return noVisual(no.op, "expr", [converter(no.esquerda), converter(no.direita)]);
    case "Negativo": return noVisual("- unário", "expr", [converter(no.valor)]);
    case "Chamada": return noVisual(`${no.nome}( )`, "func", no.argumentos.map(converter));
    case "Numero": return noVisual(no.texto, "folha-num");
    case "Variavel": return noVisual(no.nome, "folha-var");
    default: throw new Error(no.tipo);
  }
}

const ALTURA_NO = 30;
const PASSO_Y = 62;
const FOLGA_X = 14;
const LARGURA_CHAR = 8.2;

function medir(no) {
  no.largura = Math.max(36, no.rotulo.length * LARGURA_CHAR + 18);
  const filhos = no.filhos.reduce((soma, f) => soma + medir(f) + FOLGA_X, -FOLGA_X);
  no.espaco = Math.max(no.largura, filhos);
  no.espacoFilhos = filhos;
  return no.espaco;
}

function colocar(no, esquerda, nivel) {
  no.x = esquerda + no.espaco / 2;
  no.y = 12 + nivel * PASSO_Y;
  let cursor = esquerda + (no.espaco - no.espacoFilhos) / 2;
  let fundo = no.y;
  for (const f of no.filhos) {
    fundo = Math.max(fundo, colocar(f, cursor, nivel + 1));
    cursor += f.espaco + FOLGA_X;
  }
  return fundo;
}

function contar(no) {
  return no.filhos.reduce((s, f) => s + contar(f), 1);
}

function svgEl(tag, atributos, texto) {
  const n = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(atributos)) n.setAttribute(k, String(v));
  if (texto !== undefined) n.textContent = texto;
  return n;
}

function desenharNo(no, svg) {
  for (const f of no.filhos) {
    const meio = (no.y + ALTURA_NO + f.y) / 2;
    svg.append(svgEl("path", {
      class: "aresta",
      d: `M${no.x} ${no.y + ALTURA_NO}C${no.x} ${meio} ${f.x} ${meio} ${f.x} ${f.y}`,
    }));
    desenharNo(f, svg);
  }
  const g = svgEl("g", { class: `no no-${no.classe}` });
  g.append(svgEl("rect", { x: no.x - no.largura / 2, y: no.y, width: no.largura, height: ALTURA_NO, rx: no.classe === "grupo" ? 15 : 3 }));
  g.append(svgEl("text", { x: no.x, y: no.y + 20, "text-anchor": "middle" }, no.rotulo));
  svg.append(g);
}

function desenharArvore() {
  const alvo = $("painel-arvore-corpo");
  if (!resultado) return avisoErro(alvo, "a árvore");
  const raiz = converter(resultado.arvore);
  const total = contar(raiz);
  if (total > MAX_NOS_ARVORE) return aviso(alvo, `Esta árvore tem ${total} nós, mais do que cabe em um desenho legível (limite de ${MAX_NOS_ARVORE}).`);
  medir(raiz);
  const fundo = colocar(raiz, 12, 0);
  const largura = raiz.espaco + 24;
  const altura = fundo + ALTURA_NO + 14;
  const svg = svgEl("svg", {
    viewBox: `0 0 ${largura} ${altura}`, width: largura, height: altura, role: "img",
    "aria-label": `Árvore sintática com ${total} nós`,
  });
  desenharNo(raiz, svg);
  limpar(alvo).append(svg);
  alvo.scrollLeft = raiz.x - alvo.clientWidth / 2;
}

// Aba Bytecode
function desenharBytecode() {
  const alvo = $("painel-bytecode-corpo");
  if (!resultado) return avisoErro(alvo, "o bytecode");
  limpar(alvo);
  const estadoMaq = carregado && maquina ? maquina.estado() : null;
  const emAndamento = estadoMaq && estadoMaq.passos > 0;
  alvo.append(el("p", "resumo-bytecode",
    `Este programa virou ${resultado.listagem.length} instruções em ${resultado.bytes.length} bytes, incluindo a tabela que liga cada instrução à linha e à coluna do texto.`));
  const tabela = el("table", "listagem");
  const cabeca = el("tr");
  for (const c of ["End.", "Instrução", "Arg.", "Detalhe", "Linha"]) {
    const th = el("th", "", c);
    th.scope = "col";
    cabeca.append(th);
  }
  const thead = el("thead");
  thead.append(cabeca);
  tabela.append(thead);
  const corpo = el("tbody");
  for (const r of resultado.listagem.slice(0, MAX_LINHAS_BYTECODE)) {
    const tr = el("tr");
    if (emAndamento && r.pc === estadoMaq.pc) tr.className = "atual";
    tr.append(el("td", "", String(r.pc)), el("td", "mnemonico", r.nome),
      el("td", "", r.operando === null ? "" : String(r.operando)), el("td", "nota", r.nota),
      el("td", "", String(r.linha)));
    corpo.append(tr);
  }
  tabela.append(corpo);
  alvo.append(tabela);
  if (resultado.listagem.length > MAX_LINHAS_BYTECODE) {
    alvo.append(el("p", "aviso", `Mostrando ${MAX_LINHAS_BYTECODE} de ${resultado.listagem.length} instruções.`));
  }
}

// Execução: sempre no WebAssembly.
function garantirCarga() {
  if (carregado || !resultado || !maquina) return carregado;
  carregado = maquina.carregar(resultado.bytes, Number($("limite").value));
  return carregado;
}

function textoSaida(saida) {
  $("saida").textContent = saida;
  $("saida-passos").textContent = saida;
}

function mostrarErro(erro) {
  const caixa = $("erro");
  if (!erro) {
    caixa.hidden = true;
    caixa.textContent = "";
    return;
  }
  const linha = editor.value.split("\n")[erro.linha - 1] ?? "";
  const prefixo = `${erro.linha} | `;
  caixa.textContent = `Erro na linha ${erro.linha}, coluna ${erro.coluna}: ${erro.mensagem}\n` +
    `${prefixo}${linha.replace(/\r$/, "")}\n${" ".repeat(prefixo.length + erro.coluna - 1)}^`;
  caixa.hidden = false;
}

function marcarErro(erro) {
  erroAtual = erro;
  mostrarErro(erro);
}

function refletirFim(estado) {
  const e = maquina.estado();
  textoSaida(maquina.saida());
  if (estado === ERRO) {
    marcarErro({ linha: e.linha, coluna: e.coluna, mensagem: maquina.erro() });
    $("resumo").textContent = `Parou com erro depois de ${e.passos.toLocaleString("pt-BR")} passos. Veja o erro logo abaixo.`;
  } else if (estado === TERMINOU) {
    marcarErro(null);
    $("resumo").textContent = `Pronto: o programa terminou em ${e.passos.toLocaleString("pt-BR")} passos, executado em WebAssembly.`;
  }
  linhaMarcada = null;
}

function executarTudo() {
  if (!resultado) {
    irParaErro();
    return;
  }
  if (!maquina) return;
  carregado = false;
  if (!garantirCarga()) {
    $("resumo").textContent = "A máquina não aceitou este programa. Recarregue a página e tente de novo.";
    return;
  }
  refletirFim(maquina.executar());
  desenharEditor();
  desenharAba();
}

function irParaErro() {
  if (!erroAtual) return;
  const linhas = editor.value.split("\n");
  let i = 0;
  for (let k = 0; k < erroAtual.linha - 1; k++) i += linhas[k].length + 1;
  i += erroAtual.coluna - 1;
  editor.focus({ preventScroll: true });
  editor.setSelectionRange(i, i);
}

function passoUnico() {
  if (!garantirCarga()) return;
  const estado = maquina.passo();
  if (estado === RODANDO) {
    textoSaida(maquina.saida());
    linhaMarcada = maquina.estado().linha;
    $("resumo").textContent = "";
  } else {
    refletirFim(estado);
  }
  desenharEditor();
  desenharExecucao();
}

function ateOFim() {
  if (!garantirCarga()) return;
  refletirFim(maquina.executar());
  desenharEditor();
  desenharExecucao();
}

function reiniciar() {
  carregado = false;
  linhaMarcada = null;
  textoSaida("");
  $("resumo").textContent = "";
  if (resultado) marcarErro(null);
  garantirCarga();
  if (carregado) linhaMarcada = maquina.estado().linha;
  desenharEditor();
  desenharExecucao();
}

function cartao(rotulo, valor, classe = "") {
  const c = el("li", `cartao ${classe}`);
  if (rotulo) c.append(el("span", "cartao-rotulo", rotulo));
  c.append(el("span", "cartao-valor", valor ?? "sem valor"));
  return c;
}

function desenharPilha(e) {
  const alvo = limpar($("pilha"));
  let restantes = MAX_CARTOES;
  let ocultos = 0;
  for (let q = e.quadros.length - 1; q >= 0; q--) {
    const quadro = e.quadros[q];
    const fimOperandos = q === e.quadros.length - 1 ? e.topo : e.quadros[q + 1].base;
    const totalQuadro = fimOperandos - quadro.base;
    if (restantes <= 0) {
      ocultos += totalQuadro;
      continue;
    }
    const info = quadro.funcao === 0xffff ? null : resultado.funcoes[quadro.funcao];
    const grupo = el("li", "quadro");
    grupo.append(el("p", "quadro-titulo", info ? `Dentro de ${info.nome}` : "Programa principal"));
    const lista = el("ol", "cartoes");
    for (let i = fimOperandos - 1; i >= quadro.base; i--) {
      if (restantes <= 0) {
        ocultos += i - quadro.base + 1;
        break;
      }
      if (i >= quadro.piso) lista.append(cartao("", maquina.pilha(i)));
      else lista.append(cartao(info.nomesLocais[i - quadro.base], maquina.pilha(i), "cartao-local"));
      restantes--;
    }
    if (lista.children.length === 0) lista.append(el("li", "vazio", "Nada empilhado aqui."));
    grupo.append(lista);
    alvo.append(grupo);
  }
  if (ocultos > 0) alvo.append(el("li", "aviso", `Mais ${ocultos} valores abaixo destes.`));
}

function desenharGlobais() {
  const alvo = limpar($("globais"));
  if (resultado.nomesGlobais.length === 0) {
    alvo.append(el("li", "vazio", "Este programa não tem variáveis fora das funções."));
    return;
  }
  resultado.nomesGlobais.forEach((nome, i) => {
    alvo.append(cartao(nome, maquina.global(i), "cartao-global"));
  });
}

function desenharExecucao() {
  const painel = $("painel-execucao");
  const botoes = [$("passo"), $("ate-o-fim"), $("reiniciar")];
  if (!resultado || !maquina) {
    painel.classList.add("sem-programa");
    for (const b of botoes) b.disabled = true;
    if (!maquina) aviso($("execucao-aviso"), "A máquina que executa os programas (WebAssembly) não carregou. Recarregue a página.");
    else avisoErro($("execucao-aviso"), "a execução");
    return;
  }
  painel.classList.remove("sem-programa");
  limpar($("execucao-aviso"));
  if (!garantirCarga()) return;
  if (linhaMarcada === null && maquina.estado().passos === 0) {
    linhaMarcada = maquina.estado().linha;
    desenharEditor();
  }
  const e = maquina.estado();
  const instrucao = resultado.listagem.find((r) => r.pc === e.pc);
  const encerrado = e.situacao !== RODANDO;
  $("passo").disabled = encerrado;
  $("ate-o-fim").disabled = encerrado;
  $("reiniciar").disabled = false;
  $("contador").textContent = `Passo ${e.passos.toLocaleString("pt-BR")}`;
  if (instrucao) {
    const arg = instrucao.operando === null ? "" : ` ${instrucao.operando}`;
    const nota = instrucao.nota ? ` (${instrucao.nota})` : "";
    $("instrucao").textContent = `${encerrado ? "Última" : "Próxima"}: ${instrucao.nome}${arg}${nota}`;
    const fonte = editor.value.split("\n")[e.linha - 1] ?? "";
    $("linha-atual").textContent = `${e.linha} | ${fonte.trim()}`;
  }
  desenharPilha(e);
  desenharGlobais();
}

// Compilação a cada alteração: as abas sempre refletem o que está no editor.
function recompilar() {
  carregado = false;
  linhaMarcada = null;
  textoSaida("");
  $("resumo").textContent = "";
  try {
    resultado = compilar(editor.value);
    marcarErro(null);
  } catch (erro) {
    if (!(erro instanceof ErroLinha)) throw erro;
    resultado = null;
    marcarErro({ linha: erro.linha, coluna: erro.coluna, mensagem: erro.mensagem });
  }
  desenharEditor();
  desenharAba();
}

function iniciarInterface() {
  for (const [i, ex] of EXEMPLOS.entries()) {
    const op = el("option", "", ex.nome);
    op.value = String(i);
    $("exemplos").append(op);
  }
  $("exemplos").addEventListener("change", (ev) => {
    editor.value = EXEMPLOS[Number(ev.target.value)].fonte;
    editor.scrollTop = 0;
    editor.scrollLeft = 0;
    recompilar();
    if (resultado) executarTudo();
  });
  editor.addEventListener("input", recompilar);
  editor.addEventListener("scroll", sincronizarRolagem);
  editor.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) {
      ev.preventDefault();
      executarTudo();
    }
  });
  $("executar").addEventListener("click", executarTudo);
  $("passo").addEventListener("click", passoUnico);
  $("ate-o-fim").addEventListener("click", ateOFim);
  $("reiniciar").addEventListener("click", reiniciar);
  $("limite").addEventListener("change", () => {
    carregado = false;
    linhaMarcada = null;
    desenharAba();
  });
  ABAS.forEach((a, i) => {
    const aba = $(`aba-${a}`);
    aba.addEventListener("click", () => ativarAba(a));
    aba.addEventListener("keydown", (ev) => {
      const delta = ev.key === "ArrowRight" ? 1 : ev.key === "ArrowLeft" ? -1 : 0;
      if (delta) ativarAba(ABAS[(i + delta + ABAS.length) % ABAS.length], true);
    });
  });
}

async function iniciar() {
  iniciarInterface();
  editor.value = EXEMPLOS[0].fonte;
  recompilar();
  try {
    const resposta = await fetch("playground/vm.wasm");
    if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);
    maquina = await criarMaquina(await resposta.arrayBuffer());
    executarTudo();
  } catch {
    $("executar").disabled = true;
    $("resumo").textContent = "Não foi possível carregar a máquina que executa os programas (WebAssembly). Recarregue a página e tente de novo.";
    desenharAba();
  }
}

iniciar();
