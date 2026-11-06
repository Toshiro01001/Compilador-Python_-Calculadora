// Percorre o playground em um navegador de verdade (Playwright + Chromium).
// Uso: NODE_PATH=$(npm root -g) node testes/navegador.cjs [pasta-das-capturas]
// Serve a raiz do repositório por localhost; não baixa nada.
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert");
const { chromium, devices } = require("playwright");

const RAIZ = path.resolve(__dirname, "..");
const CAPTURAS = process.argv[2];
const TIPOS = { ".html": "text/html; charset=utf-8", ".css": "text/css", ".mjs": "text/javascript", ".wasm": "application/wasm", ".svg": "image/svg+xml" };

const servidor = http.createServer((req, res) => {
  const relativo = decodeURIComponent(new URL(req.url, "http://x").pathname).replace(/^\/+/, "") || "index.html";
  const arquivo = path.resolve(RAIZ, relativo);
  if (!arquivo.startsWith(RAIZ + path.sep) || !fs.existsSync(arquivo) || fs.statSync(arquivo).isDirectory()) {
    res.writeHead(404);
    res.end();
    return;
  }
  res.writeHead(200, { "Content-Type": TIPOS[path.extname(arquivo)] ?? "application/octet-stream" });
  fs.createReadStream(arquivo).pipe(res);
});

const PERFIS = [
  { nome: "computador", contexto: { viewport: { width: 1366, height: 800 }, deviceScaleFactor: 2 } },
  { nome: "iphone13", contexto: { ...devices["iPhone 13"], deviceScaleFactor: 2 } },
  { nome: "320px", contexto: { viewport: { width: 320, height: 640 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true } },
];

async function semRolagemLateral(pagina, momento) {
  const r = await pagina.evaluate(() => ({
    doc: document.documentElement.scrollWidth,
    corpo: document.body.scrollWidth,
    janela: window.innerWidth,
  }));
  assert.ok(r.doc <= r.janela && r.corpo <= r.janela, `rolagem lateral em ${momento}: ${JSON.stringify(r)}`);
}

async function foto(pagina, perfil, nome, inteira = false) {
  if (CAPTURAS) await pagina.screenshot({ path: path.join(CAPTURAS, `${perfil}-${nome}.png`), fullPage: inteira });
}

async function percorrer(navegador, perfil, url) {
  const contexto = await navegador.newContext(perfil.contexto);
  const pagina = await contexto.newPage();
  const problemas = [];
  pagina.on("console", (m) => { if (["error", "warning"].includes(m.type())) problemas.push(`console ${m.type()}: ${m.text()}`); });
  pagina.on("pageerror", (e) => problemas.push(`exceção: ${e.message}`));
  pagina.on("requestfailed", (r) => problemas.push(`falhou: ${r.url()}`));
  pagina.on("request", (r) => { if (!r.url().startsWith(url)) problemas.push(`terceiro: ${r.url()}`); });
  pagina.on("response", (r) => { if (r.status() >= 400) problemas.push(`HTTP ${r.status()}: ${r.url()}`); });

  await pagina.goto(url);
  await pagina.waitForFunction(() => document.getElementById("resumo").textContent.includes("WebAssembly"));
  assert.strictEqual(await pagina.textContent("#saida"), "1125\n380\n400\n");
  await semRolagemLateral(pagina, "início");
  await foto(pagina, perfil.nome, "1-inicio");

  // CSP e rodapé
  const csp = await pagina.getAttribute('meta[http-equiv="Content-Security-Policy"]', "content");
  assert.ok(csp.includes("'wasm-unsafe-eval'") && !csp.includes("'unsafe-eval'") && !csp.includes("'unsafe-inline'"));
  assert.strictEqual((await pagina.textContent(".rodape p")).trim(), "Demonstração feita por Mil e Uma Linhas!");
  assert.strictEqual(await pagina.getAttribute(".rodape a", "href"), "https://mileumalinhas.com.br");

  // Abas: conteúdo real em cada uma
  assert.ok((await pagina.locator(".ficha").count()) > 20);
  await pagina.click("#aba-arvore");
  assert.ok((await pagina.locator("#painel-arvore-corpo svg .no").count()) > 10);
  // A raiz tem de aparecer sem o visitante precisar rolar o painel.
  const raizVisivel = await pagina.evaluate(() => {
    const raiz = [...document.querySelectorAll("#painel-arvore-corpo .no")].at(-1).getBoundingClientRect();
    const janela = document.getElementById("painel-arvore-corpo").getBoundingClientRect();
    return raiz.width > 0 && raiz.left >= janela.left && raiz.right <= janela.right;
  });
  assert.ok(raizVisivel, "raiz da árvore fora do painel");
  await semRolagemLateral(pagina, "árvore");
  await pagina.locator("#painel-arvore").scrollIntoViewIfNeeded();
  await foto(pagina, perfil.nome, "2-arvore");

  await pagina.click("#aba-bytecode");
  assert.ok((await pagina.locator(".listagem tbody tr").count()) > 10);
  await semRolagemLateral(pagina, "bytecode");
  await foto(pagina, perfil.nome, "3-bytecode");

  // Passo a passo: a pilha muda e o resultado final é o mesmo
  await pagina.selectOption("#exemplos", { label: "Fatorial (recursão)" });
  await pagina.click("#aba-execucao");
  await pagina.click("#reiniciar");
  assert.strictEqual((await pagina.textContent("#contador")).trim(), "Passo 0");
  for (let i = 0; i < 24; i++) await pagina.click("#passo");
  assert.strictEqual((await pagina.textContent("#contador")).trim(), "Passo 24");
  assert.ok((await pagina.locator("#pilha .quadro").count()) >= 2, "esperava quadros de chamada");
  assert.ok((await pagina.locator("#pilha .cartao").count()) >= 2, "esperava cartões na pilha");
  assert.strictEqual(await pagina.locator(".linha.marcada").count(), 1);
  await semRolagemLateral(pagina, "passo a passo");
  await pagina.locator("#painel-execucao").scrollIntoViewIfNeeded();
  await foto(pagina, perfil.nome, "4-passo-a-passo");
  await pagina.click("#ate-o-fim");
  assert.strictEqual(await pagina.textContent("#saida-passos"), "720\n");
  assert.ok(await pagina.isDisabled("#passo"));

  // Erro de sintaxe: linha, coluna e abas protegidas
  await pagina.selectOption("#exemplos", { label: "Erro de sintaxe" });
  const erroSintaxe = await pagina.textContent("#erro");
  assert.ok(erroSintaxe.includes("Erro na linha 2, coluna 13: esperava um valor"), erroSintaxe);
  assert.strictEqual(await pagina.locator(".t-erro").count(), 1);
  assert.ok((await pagina.textContent("#execucao-aviso")).includes("linha 2"));
  await semRolagemLateral(pagina, "erro de sintaxe");
  await pagina.locator(".folha-programa").scrollIntoViewIfNeeded();
  await foto(pagina, perfil.nome, "5-erro-de-sintaxe");

  // Laço infinito: a página continua respondendo e o erro aponta o laço
  await pagina.selectOption("#exemplos", { label: "Laço infinito" });
  await pagina.selectOption("#limite", "20000000");
  const inicio = Date.now();
  await pagina.click("#executar");
  assert.ok(Date.now() - inicio < 5000, "o limite de passos demorou demais");
  assert.ok((await pagina.textContent("#erro")).includes("limite de passos atingido"));
  assert.ok((await pagina.textContent("#resumo")).includes("20.000.000"));
  await semRolagemLateral(pagina, "laço infinito");
  await foto(pagina, perfil.nome, "6-laco-infinito");
  await pagina.selectOption("#limite", "1000000");

  // Digitação: compila ao vivo, sem interpretar HTML como marcação
  await pagina.fill("#codigo", "total = 2 * (3 + 4)\nprint(total)\n<img src=x onerror=alert(1)>");
  assert.ok((await pagina.textContent("#erro")).includes("linha 3, coluna 1: esperava um valor, mas encontrei '<'"));
  assert.strictEqual(await pagina.locator(".camada img, #erro img").count(), 0);
  await pagina.fill("#codigo", "total = 2 * (3 + 4)\nprint(total)\n");
  await pagina.click("#executar");
  assert.strictEqual(await pagina.textContent("#saida"), "14\n");
  assert.strictEqual(await pagina.locator("#erro").isVisible(), false);

  // Texto explicativo e página inteira
  await pagina.locator(".folha-texto").scrollIntoViewIfNeeded();
  assert.ok((await pagina.textContent(".folha-texto")).includes("Regras de negócio configuráveis"));
  await semRolagemLateral(pagina, "fim");
  await pagina.selectOption("#exemplos", { index: 0 });
  await pagina.click("#aba-tokens");
  await foto(pagina, perfil.nome, "7-pagina-inteira", true);

  assert.deepStrictEqual(problemas, [], `problemas em ${perfil.nome}`);
  await contexto.close();
  console.log(`ok: ${perfil.nome}`);
}

(async () => {
  await new Promise((pronto) => servidor.listen(0, "127.0.0.1", pronto));
  const url = `http://127.0.0.1:${servidor.address().port}/`;
  const navegador = await chromium.launch();
  try {
    for (const perfil of PERFIS) await percorrer(navegador, perfil, url);
    console.log("Todos os perfis passaram.");
  } finally {
    await navegador.close();
    servidor.close();
  }
})().catch((erro) => {
  console.error(erro);
  process.exit(1);
});
