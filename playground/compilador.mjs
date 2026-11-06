// Lexer, parser e gerador de bytecode em JavaScript. Espelha o pacote linha/ em
// Python: o teste cruzado exige tokens, erros e bytecode idênticos, byte a byte.

export class ErroLinha extends Error {
  constructor(mensagem, linha, coluna) {
    super(mensagem);
    this.mensagem = mensagem;
    this.linha = linha;
    this.coluna = coluna;
  }
  texto() {
    return `Erro na linha ${this.linha}, coluna ${this.coluna}: ${this.mensagem}`;
  }
}

const PALAVRAS = new Set(["if", "else", "while", "func", "return", "print"]);
const DUPLOS = new Set(["==", "!=", "<=", ">="]);
const SIMBOLOS = new Set("+-*/%=<>(){},;");

const iniciaNome = (c) =>
  c === "_" || (c >= "a" && c <= "z") || (c >= "A" && c <= "Z") ||
  (c >= "À" && c <= "ÿ" && c !== "×" && c !== "÷");
const digito = (c) => c >= "0" && c <= "9";

export function tokenizar(fonte) {
  const tokens = [];
  let i = 0, linha = 1, inicioLinha = 0, parenteses = 0;
  const n = fonte.length;
  while (i < n) {
    const c = fonte[i];
    const coluna = i - inicioLinha + 1;
    if (c === "\n") {
      if (parenteses === 0 && tokens.length && tokens[tokens.length - 1].tipo !== "FIM_LINHA") {
        tokens.push({ tipo: "FIM_LINHA", texto: "\n", linha, coluna });
      }
      i++;
      linha++;
      inicioLinha = i;
    } else if (c === " " || c === "\t" || c === "\r") {
      i++;
    } else if (c === "#") {
      while (i < n && fonte[i] !== "\n") i++;
    } else if (digito(c)) {
      let fim = i;
      while (fim < n && digito(fonte[fim])) fim++;
      if (fim < n && fonte[fim] === ".") {
        fim++;
        if (fim >= n || !digito(fonte[fim])) {
          throw new ErroLinha("número incompleto: falta um dígito depois do ponto", linha, coluna);
        }
        while (fim < n && digito(fonte[fim])) fim++;
      }
      tokens.push({ tipo: "NUMERO", texto: fonte.slice(i, fim), linha, coluna });
      i = fim;
    } else if (iniciaNome(c)) {
      let fim = i;
      while (fim < n && (iniciaNome(fonte[fim]) || digito(fonte[fim]))) fim++;
      const texto = fonte.slice(i, fim);
      tokens.push({ tipo: PALAVRAS.has(texto) ? texto : "NOME", texto, linha, coluna });
      i = fim;
    } else if (DUPLOS.has(fonte.slice(i, i + 2))) {
      const texto = fonte.slice(i, i + 2);
      tokens.push({ tipo: texto, texto, linha, coluna });
      i += 2;
    } else if (SIMBOLOS.has(c)) {
      if (c === "(") parenteses++;
      else if (c === ")" && parenteses > 0) parenteses--;
      tokens.push({ tipo: c, texto: c, linha, coluna });
      i++;
    } else {
      const inteiro = String.fromCodePoint(fonte.codePointAt(i));
      throw new ErroLinha(`caractere inesperado '${inteiro}'`, linha, coluna);
    }
  }
  tokens.push({ tipo: "FIM", texto: "", linha, coluna: n - inicioLinha + 1 });
  return tokens;
}

const MAX_ANINHAMENTO = 64;
const MAX_PROFUNDIDADE = 200;
const COMPARACOES = new Set(["==", "!=", "<", "<=", ">", ">="]);

function descrever(t) {
  if (t.tipo === "FIM") return "o fim do programa";
  if (t.tipo === "FIM_LINHA") return "o fim da linha";
  return `'${t.texto}'`;
}

class Parser {
  constructor(tokens) {
    this.tokens = tokens;
    this.i = 0;
    this.nivel = 0;
  }
  get atual() { return this.tokens[this.i]; }
  avancar() { return this.tokens[this.i++]; }
  falhar(mensagem, token = this.atual) {
    throw new ErroLinha(mensagem, token.linha, token.coluna);
  }
  exigir(tipo, descricao) {
    if (this.atual.tipo !== tipo) {
      this.falhar(`esperava ${descricao}, mas encontrei ${descrever(this.atual)}`);
    }
    return this.avancar();
  }
  entrar() {
    this.nivel++;
    if (this.nivel > MAX_ANINHAMENTO) {
      this.falhar(`aninhamento profundo demais (limite de ${MAX_ANINHAMENTO} níveis)`);
    }
  }
  pularSeparadores() {
    while (this.atual.tipo === "FIM_LINHA" || this.atual.tipo === ";") this.avancar();
  }
  fimInstrucao() {
    if (this.atual.tipo === "FIM_LINHA" || this.atual.tipo === ";") this.pularSeparadores();
    else if (this.atual.tipo !== "}" && this.atual.tipo !== "FIM") {
      this.falhar(`esperava o fim da instrução, mas encontrei ${descrever(this.atual)}`);
    }
  }
  programa() {
    const itens = [];
    this.pularSeparadores();
    while (this.atual.tipo !== "FIM") {
      itens.push(this.instrucao(true));
      this.fimInstrucao();
    }
    return { tipo: "Programa", linha: this.atual.linha, coluna: this.atual.coluna, itens };
  }
  instrucao(noTopo = false) {
    const t = this.atual;
    if (t.tipo === "func") {
      if (!noTopo) this.falhar("funções só podem ser declaradas fora de blocos");
      return this.funcao();
    }
    if (t.tipo === "if") return this.se();
    if (t.tipo === "while") return this.enquanto();
    if (t.tipo === "return") return this.retorna();
    if (t.tipo === "print") return this.imprime();
    if (t.tipo === "NOME" && this.tokens[this.i + 1].tipo === "=") {
      this.avancar();
      this.avancar();
      return { tipo: "Atribuicao", linha: t.linha, coluna: t.coluna, nome: t.texto, valor: this.expressao() };
    }
    if (t.tipo === "else") this.falhar("'else' sem um 'if' antes");
    return { tipo: "ExpressaoSolta", linha: t.linha, coluna: t.coluna, valor: this.expressao() };
  }
  funcao() {
    const inicio = this.avancar();
    const nome = this.exigir("NOME", "o nome da função");
    this.exigir("(", "'(' depois do nome da função");
    const parametros = [];
    if (this.atual.tipo !== ")") {
      for (;;) {
        const p = this.exigir("NOME", "o nome de um parâmetro");
        if (parametros.includes(p.texto)) this.falhar(`parâmetro '${p.texto}' repetido`, p);
        parametros.push(p.texto);
        if (this.atual.tipo !== ",") break;
        this.avancar();
      }
    }
    this.exigir(")", "')' depois dos parâmetros");
    const [corpo, fim] = this.bloco();
    return {
      tipo: "Funcao", linha: inicio.linha, coluna: inicio.coluna, nome: nome.texto,
      parametros, corpo, fimLinha: fim.linha, fimColuna: fim.coluna,
    };
  }
  se() {
    const inicio = this.avancar();
    const condicao = this.expressao();
    const [entao] = this.bloco();
    let senao = null;
    const volta = this.i;
    while (this.atual.tipo === "FIM_LINHA") this.avancar();
    if (this.atual.tipo === "else") {
      this.avancar();
      if (this.atual.tipo === "if") {
        this.entrar();
        senao = [this.se()];
        this.nivel--;
      } else {
        [senao] = this.bloco();
      }
    } else {
      this.i = volta;
    }
    return { tipo: "Se", linha: inicio.linha, coluna: inicio.coluna, condicao, entao, senao };
  }
  enquanto() {
    const inicio = this.avancar();
    const condicao = this.expressao();
    const [corpo] = this.bloco();
    return { tipo: "Enquanto", linha: inicio.linha, coluna: inicio.coluna, condicao, corpo };
  }
  retorna() {
    const inicio = this.avancar();
    let valor = null;
    if (!["FIM_LINHA", ";", "}", "FIM"].includes(this.atual.tipo)) valor = this.expressao();
    return { tipo: "Retorna", linha: inicio.linha, coluna: inicio.coluna, valor };
  }
  imprime() {
    const inicio = this.avancar();
    this.exigir("(", "'(' depois de print");
    const valor = this.expressao();
    this.exigir(")", "')' para fechar o print");
    return { tipo: "Imprime", linha: inicio.linha, coluna: inicio.coluna, valor };
  }
  bloco() {
    this.exigir("{", "'{' para abrir o bloco");
    this.entrar();
    const corpo = [];
    this.pularSeparadores();
    while (this.atual.tipo !== "}") {
      if (this.atual.tipo === "FIM") this.falhar("esperava '}' para fechar o bloco, mas o programa acabou");
      corpo.push(this.instrucao());
      this.fimInstrucao();
    }
    this.nivel--;
    return [corpo, this.avancar()];
  }
  binaria(op, esquerda, direita) {
    const profundidade = Math.max(esquerda.profundidade ?? 1, direita.profundidade ?? 1) + 1;
    if (profundidade > MAX_PROFUNDIDADE) {
      this.falhar(`expressão longa demais (limite de ${MAX_PROFUNDIDADE} operações encadeadas)`, op);
    }
    return { tipo: "Binaria", linha: op.linha, coluna: op.coluna, op: op.tipo, esquerda, direita, profundidade };
  }
  expressao() {
    this.entrar();
    let no = this.soma();
    while (COMPARACOES.has(this.atual.tipo)) {
      const op = this.avancar();
      no = this.binaria(op, no, this.soma());
    }
    this.nivel--;
    return no;
  }
  soma() {
    let no = this.produto();
    while (this.atual.tipo === "+" || this.atual.tipo === "-") {
      const op = this.avancar();
      no = this.binaria(op, no, this.produto());
    }
    return no;
  }
  produto() {
    let no = this.unario();
    while (this.atual.tipo === "*" || this.atual.tipo === "/" || this.atual.tipo === "%") {
      const op = this.avancar();
      no = this.binaria(op, no, this.unario());
    }
    return no;
  }
  unario() {
    if (this.atual.tipo === "-") {
      const op = this.avancar();
      this.entrar();
      const valor = this.unario();
      this.nivel--;
      return { tipo: "Negativo", linha: op.linha, coluna: op.coluna, valor };
    }
    return this.primario();
  }
  primario() {
    const t = this.atual;
    if (t.tipo === "NUMERO") {
      this.avancar();
      return { tipo: "Numero", linha: t.linha, coluna: t.coluna, valor: Number(t.texto), texto: t.texto };
    }
    if (t.tipo === "NOME") {
      this.avancar();
      if (this.atual.tipo === "(") return this.chamada(t);
      return { tipo: "Variavel", linha: t.linha, coluna: t.coluna, nome: t.texto };
    }
    if (t.tipo === "(") {
      this.avancar();
      const no = this.expressao();
      this.exigir(")", "')' para fechar o parêntese");
      return no;
    }
    return this.falhar(`esperava um valor, mas encontrei ${descrever(t)}`);
  }
  chamada(nome) {
    this.avancar();
    const argumentos = [];
    if (this.atual.tipo !== ")") {
      for (;;) {
        argumentos.push(this.expressao());
        if (this.atual.tipo !== ",") break;
        this.avancar();
      }
    }
    this.exigir(")", "')' para fechar a chamada");
    return { tipo: "Chamada", linha: nome.linha, coluna: nome.coluna, nome: nome.texto, argumentos };
  }
}

export function analisar(fonte) {
  return new Parser(tokenizar(fonte)).programa();
}

// Instruções: [mnemônico, tamanho do operando em bytes]. O índice é o código.
export const INSTRUCOES = [
  ["PARA", 0], ["CONST", 2], ["LE_GLOBAL", 2], ["GRAVA_GLOBAL", 2], ["LE_LOCAL", 2], ["GRAVA_LOCAL", 2],
  ["SOMA", 0], ["SUB", 0], ["MUL", 0], ["DIV", 0], ["RESTO", 0], ["NEG", 0],
  ["IGUAL", 0], ["DIFERENTE", 0], ["MENOR", 0], ["MENOR_IGUAL", 0], ["MAIOR", 0], ["MAIOR_IGUAL", 0],
  ["PULA", 4], ["PULA_SE_ZERO", 4], ["CHAMA", 2], ["RETORNA", 0], ["IMPRIME", 0], ["DESCARTA", 0],
];
const OP = Object.fromEntries(INSTRUCOES.map(([nome], i) => [nome, i]));
const BINARIAS = {
  "+": "SOMA", "-": "SUB", "*": "MUL", "/": "DIV", "%": "RESTO", "==": "IGUAL", "!=": "DIFERENTE",
  "<": "MENOR", "<=": "MENOR_IGUAL", ">": "MAIOR", ">=": "MAIOR_IGUAL",
};
const SEM_NOME = 0xffff;
const MAX_INDICE = 0xffff;
const MAX_GLOBAIS = 4096;
const MAX_PROGRAMA = 1 << 20;

function nomesAtribuidos(corpo, saida) {
  for (const no of corpo) {
    if (no.tipo === "Atribuicao" && !saida.includes(no.nome)) saida.push(no.nome);
    else if (no.tipo === "Se") {
      nomesAtribuidos(no.entao, saida);
      nomesAtribuidos(no.senao ?? [], saida);
    } else if (no.tipo === "Enquanto") nomesAtribuidos(no.corpo, saida);
  }
}

class Gerador {
  constructor() {
    this.constantes = [];
    this.mapaConstantes = new Map();
    this.nomes = [];
    this.mapaNomes = new Map();
    this.globais = new Map();
    this.funcoes = [];
    this.codigo = [];
    this.posicoes = [];
    this.locais = null;
    this.indices = new Map();
    this.declaradas = new Map();
  }
  emitir(nomeOp, no, operando = null, nome = null, largura = 2) {
    this.posicoes.push({
      pc: this.codigo.length, linha: no.linha, coluna: no.coluna,
      nome: nome !== null ? this.nome(nome, no) : SEM_NOME,
    });
    this.codigo.push(OP[nomeOp]);
    const local = this.codigo.length;
    if (operando !== null) {
      for (let k = 0; k < largura; k++) this.codigo.push((operando / 2 ** (8 * k)) & 0xff);
    }
    return local;
  }
  nome(nome, pos) {
    if (!this.mapaNomes.has(nome)) {
      if (this.nomes.length >= MAX_INDICE) throw new ErroLinha("nomes demais no programa", pos.linha, pos.coluna);
      this.mapaNomes.set(nome, this.nomes.length);
      this.nomes.push(nome);
    }
    return this.mapaNomes.get(nome);
  }
  constante(valor, pos) {
    if (!this.mapaConstantes.has(valor)) {
      if (this.constantes.length >= MAX_INDICE) throw new ErroLinha("constantes demais no programa", pos.linha, pos.coluna);
      this.mapaConstantes.set(valor, this.constantes.length);
      this.constantes.push(valor);
    }
    return this.mapaConstantes.get(valor);
  }
  global(nome, pos) {
    if (!this.globais.has(nome)) {
      if (this.globais.size >= MAX_GLOBAIS) {
        throw new ErroLinha(`variáveis globais demais (limite de ${MAX_GLOBAIS})`, pos.linha, pos.coluna);
      }
      this.globais.set(nome, this.globais.size);
    }
    return this.globais.get(nome);
  }
  remendar(local) {
    const alvo = this.codigo.length;
    for (let k = 0; k < 4; k++) this.codigo[local + k] = (alvo / 2 ** (8 * k)) & 0xff;
  }
  compilar(arvore) {
    const principais = [];
    for (const item of arvore.itens) {
      if (item.tipo === "Funcao") {
        if (this.declaradas.has(item.nome)) {
          throw new ErroLinha(`função '${item.nome}' declarada mais de uma vez`, item.linha, item.coluna);
        }
        this.declaradas.set(item.nome, item);
      } else principais.push(item);
    }
    let indice = 0;
    for (const [nome, f] of this.declaradas) {
      this.indices.set(nome, indice);
      const locais = [...f.parametros];
      nomesAtribuidos(f.corpo, locais);
      if (locais.length > MAX_INDICE || indice >= MAX_INDICE) {
        throw new ErroLinha("funções ou variáveis locais demais", f.linha, f.coluna);
      }
      this.funcoes.push({
        inicio: 0, parametros: f.parametros.length, locais: locais.length,
        nomeId: this.nome(nome, f), nome, nomesLocais: locais,
      });
      indice++;
    }
    this.bloco(principais);
    this.emitir("PARA", arvore);
    indice = 0;
    for (const f of this.declaradas.values()) {
      this.funcao(f, indice);
      indice++;
    }
  }
  funcao(f, indice) {
    this.funcoes[indice].inicio = this.codigo.length;
    this.locais = this.funcoes[indice].nomesLocais;
    this.bloco(f.corpo);
    const fim = { linha: f.fimLinha, coluna: f.fimColuna };
    this.emitir("CONST", fim, this.constante(0, fim));
    this.emitir("RETORNA", fim);
    this.locais = null;
  }
  bloco(corpo) {
    for (const no of corpo) this.instrucao(no);
  }
  instrucao(no) {
    switch (no.tipo) {
      case "Atribuicao":
        this.expressao(no.valor);
        if (this.locais !== null && this.locais.includes(no.nome)) {
          this.emitir("GRAVA_LOCAL", no, this.locais.indexOf(no.nome), no.nome);
        } else {
          this.emitir("GRAVA_GLOBAL", no, this.global(no.nome, no), no.nome);
        }
        break;
      case "Imprime":
        this.expressao(no.valor);
        this.emitir("IMPRIME", no);
        break;
      case "ExpressaoSolta":
        this.expressao(no.valor);
        this.emitir("DESCARTA", no);
        break;
      case "Retorna":
        if (this.locais === null) throw new ErroLinha("'return' fora de uma função", no.linha, no.coluna);
        if (no.valor === null) this.emitir("CONST", no, this.constante(0, no));
        else this.expressao(no.valor);
        this.emitir("RETORNA", no);
        break;
      case "Se": {
        this.expressao(no.condicao);
        const paraSenao = this.emitir("PULA_SE_ZERO", no, 0, null, 4);
        this.bloco(no.entao);
        if (no.senao === null) this.remendar(paraSenao);
        else {
          const paraFim = this.emitir("PULA", no, 0, null, 4);
          this.remendar(paraSenao);
          this.bloco(no.senao);
          this.remendar(paraFim);
        }
        break;
      }
      case "Enquanto": {
        const inicio = this.codigo.length;
        this.expressao(no.condicao);
        const paraFim = this.emitir("PULA_SE_ZERO", no, 0, null, 4);
        this.bloco(no.corpo);
        this.emitir("PULA", no, inicio, null, 4);
        this.remendar(paraFim);
        break;
      }
      default:
        throw new Error(`instrução desconhecida: ${no.tipo}`);
    }
  }
  expressao(no) {
    switch (no.tipo) {
      case "Numero":
        this.emitir("CONST", no, this.constante(no.valor, no));
        break;
      case "Variavel":
        if (this.locais !== null && this.locais.includes(no.nome)) {
          this.emitir("LE_LOCAL", no, this.locais.indexOf(no.nome), no.nome);
        } else {
          this.emitir("LE_GLOBAL", no, this.global(no.nome, no), no.nome);
        }
        break;
      case "Binaria":
        this.expressao(no.esquerda);
        this.expressao(no.direita);
        this.emitir(BINARIAS[no.op], no);
        break;
      case "Negativo":
        this.expressao(no.valor);
        this.emitir("NEG", no);
        break;
      case "Chamada": {
        const f = this.declaradas.get(no.nome);
        if (f === undefined) throw new ErroLinha(`função '${no.nome}' não existe`, no.linha, no.coluna);
        if (no.argumentos.length !== f.parametros.length) {
          throw new ErroLinha(
            `função '${no.nome}' espera ${f.parametros.length} argumento(s), mas recebeu ${no.argumentos.length}`,
            no.linha, no.coluna,
          );
        }
        for (const a of no.argumentos) this.expressao(a);
        this.emitir("CHAMA", no, this.indices.get(no.nome), no.nome);
        break;
      }
      default:
        throw new Error(`expressão desconhecida: ${no.tipo}`);
    }
  }
  bytes(fimPos) {
    const cod = new TextEncoder();
    const nomes = this.nomes.map((n) => cod.encode(n));
    const total = 4 + 2 + this.constantes.length * 8 + 2 + nomes.reduce((s, n) => s + 2 + n.length, 0) +
      2 + 2 + this.funcoes.length * 10 + 4 + this.codigo.length + 4 + this.posicoes.length * 14;
    if (total > MAX_PROGRAMA) throw new ErroLinha("programa grande demais", fimPos.linha, fimPos.coluna);
    const saida = new Uint8Array(total);
    const v = new DataView(saida.buffer);
    let c = 0;
    saida.set([0x4c, 0x49, 0x4e, 0x31]);
    c = 4;
    const u16 = (x) => { v.setUint16(c, x, true); c += 2; };
    const u32 = (x) => { v.setUint32(c, x, true); c += 4; };
    u16(this.constantes.length);
    for (const x of this.constantes) { v.setFloat64(c, x, true); c += 8; }
    u16(nomes.length);
    for (const n of nomes) { u16(n.length); saida.set(n, c); c += n.length; }
    u16(this.globais.size);
    u16(this.funcoes.length);
    for (const f of this.funcoes) { u32(f.inicio); u16(f.parametros); u16(f.locais); u16(f.nomeId); }
    u32(this.codigo.length);
    saida.set(this.codigo, c);
    c += this.codigo.length;
    u32(this.posicoes.length);
    for (const p of this.posicoes) { u32(p.pc); u32(p.linha); u32(p.coluna); u16(p.nome); }
    return saida;
  }
  listagem() {
    const linhas = [];
    let pc = 0, indicePos = 0;
    const leitura = (de, largura) => {
      let valor = 0;
      for (let k = 0; k < largura; k++) valor += this.codigo[de + k] * 2 ** (8 * k);
      return valor;
    };
    while (pc < this.codigo.length) {
      const [nome, largura] = INSTRUCOES[this.codigo[pc]];
      const pos = this.posicoes[indicePos++];
      const operando = largura ? leitura(pc + 1, largura) : null;
      linhas.push({
        pc, nome, operando, linha: pos.linha, coluna: pos.coluna,
        nota: nome === "CONST" ? String(this.constantes[operando])
          : pos.nome !== SEM_NOME ? this.nomes[pos.nome]
          : largura === 4 ? `para ${operando}` : "",
      });
      pc += 1 + largura;
    }
    return linhas;
  }
}

// Devolve tudo o que o playground mostra sobre o programa compilado.
export function compilar(fonte) {
  const arvore = analisar(fonte);
  const g = new Gerador();
  g.compilar(arvore);
  return {
    arvore,
    bytes: g.bytes(arvore),
    listagem: g.listagem(),
    funcoes: g.funcoes,
    nomesGlobais: [...g.globais.keys()],
  };
}
