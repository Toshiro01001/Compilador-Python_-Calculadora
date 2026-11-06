/* Máquina de pilha da linguagem Linha. Espelho de linha/maquina.py: mesmas
   instruções, limites e mensagens. Todo acesso é verificado, porque o bytecode
   é tratado como dado não confiável. */
#include "vm.h"

#define MAX_PROGRAMA (1u << 20)
#define MAX_PILHA 65536u
#define MAX_QUADROS 2048u
#define MAX_GLOBAIS 4096u
#define MAX_SAIDA 65536u
#define MAX_ERRO 512u
#define LIMITE_PADRAO 1000000u
#define SEM_NOME 0xFFFFu
#define TAM_FUNCAO 10u
#define TAM_POSICAO 14u

enum {
    PARA, CONST_, LE_GLOBAL, GRAVA_GLOBAL, LE_LOCAL, GRAVA_LOCAL,
    SOMA, SUB, MUL, DIV, RESTO, NEG,
    IGUAL, DIFERENTE, MENOR, MENOR_IGUAL, MAIOR, MAIOR_IGUAL,
    PULA, PULA_SE_ZERO, CHAMA, RETORNA, IMPRIME, DESCARTA
};

typedef struct {
    uint32_t retorno, base, piso, funcao;
} Quadro;

static uint8_t programa[MAX_PROGRAMA];
static double pilha[MAX_PILHA];
static double globais[MAX_GLOBAIS];
static Quadro quadros[MAX_QUADROS];
static uint8_t saida[MAX_SAIDA];
static uint8_t erro[MAX_ERRO];
static uint8_t texto[64];

/* Seções do programa carregado (deslocamentos em `programa`). */
static uint32_t tam_programa, ini_const, n_const, ini_nomes, n_nomes, n_globais;
static uint32_t ini_func, n_func, ini_cod, tam_cod, ini_pos, n_pos;

static uint32_t pc, sp, nq, passos, limite = LIMITE_PADRAO, tam_saida, tam_erro;
static int32_t estado = VM_TERMINOU;

/* Marca de "sem valor": um NaN com carga que a aritmética nunca produz. Só é
   gravada em vagas de variáveis e sempre comparada pelos bits. */
#define VAZIO_BITS 0x7FF8DEADBEEF0000ull

typedef union {
    double d;
    uint64_t u;
} Bits;

static double vazio(void) {
    Bits b;
    b.u = VAZIO_BITS;
    return b.d;
}

static int eh_vazio(double x) {
    Bits b;
    b.d = x;
    return b.u == VAZIO_BITS;
}

static uint32_t ler16(uint32_t i) {
    return (uint32_t)programa[i] | ((uint32_t)programa[i + 1] << 8);
}

static uint32_t ler32(uint32_t i) {
    return (uint32_t)programa[i] | ((uint32_t)programa[i + 1] << 8) |
           ((uint32_t)programa[i + 2] << 16) | ((uint32_t)programa[i + 3] << 24);
}

static double ler_double(uint32_t i) {
    Bits b;
    b.u = 0;
    for (uint32_t k = 0; k < 8; k++) b.u |= (uint64_t)programa[i + k] << (8 * k);
    return b.d;
}

/* Formatação: até 6 casas, sem zeros à direita. Só usa operações IEEE 754
   básicas, por isso dá o mesmo texto em qualquer plataforma. */
static uint32_t escreve_inteiro(uint8_t *s, uint64_t v) {
    uint8_t inv[24];
    uint32_t n = 0, k = 0;
    do {
        inv[n++] = (uint8_t)('0' + v % 10);
        v /= 10;
    } while (v);
    while (n) s[k++] = inv[--n];
    return k;
}

static uint32_t escreve_literal(uint8_t *s, const char *t) {
    uint32_t k = 0;
    while (t[k]) {
        s[k] = (uint8_t)t[k];
        k++;
    }
    return k;
}

static void partes(double a, uint64_t *inteira, uint32_t *decimais) {
    double ip = __builtin_floor(a);
    double esc = __builtin_floor((a - ip) * 1e6 + 0.5);
    if (esc >= 1000000.0) {
        ip += 1.0;
        esc = 0.0;
    }
    *inteira = (uint64_t)ip;
    *decimais = (uint32_t)esc;
}

static uint32_t escreve_partes(uint8_t *s, uint64_t inteira, uint32_t decimais) {
    uint32_t k = escreve_inteiro(s, inteira);
    if (decimais) {
        uint32_t divisor = 100000;
        s[k++] = '.';
        while (decimais) {
            s[k++] = (uint8_t)('0' + decimais / divisor);
            decimais %= divisor;
            divisor /= 10;
        }
    }
    return k;
}

static uint32_t formatar(double x, uint8_t *s) {
    uint64_t inteira;
    uint32_t decimais, k = 0, ini;
    double a;
    if (x != x) return escreve_literal(s, "nan");
    if (x > 1.7976931348623157e308) return escreve_literal(s, "inf");
    if (x < -1.7976931348623157e308) return escreve_literal(s, "-inf");
    a = x < 0 ? -x : x;
    ini = x < 0 ? 1 : 0;
    if (a >= 1e15) {
        uint64_t expoente = 0;
        while (a >= 10.0) {
            a /= 10.0;
            expoente++;
        }
        partes(a, &inteira, &decimais);
        if (inteira >= 10) {
            inteira = 1;
            decimais = 0;
            expoente++;
        }
        k = ini + escreve_partes(s + ini, inteira, decimais);
        s[k++] = 'e';
        s[k++] = '+';
        k += escreve_inteiro(s + k, expoente);
    } else {
        partes(a, &inteira, &decimais);
        if (inteira == 0 && decimais == 0) {
            s[0] = '0';
            return 1;
        }
        k = ini + escreve_partes(s + ini, inteira, decimais);
    }
    if (ini) s[0] = '-';
    return k;
}

/* Posições: tabela ordenada por pc; vale a última entrada com pc <= alvo. */
static uint32_t acha_posicao(uint32_t alvo) {
    uint32_t ini = 0, fim = n_pos;
    while (fim - ini > 1) {
        uint32_t meio = ini + (fim - ini) / 2;
        if (ler32(ini_pos + meio * TAM_POSICAO) <= alvo)
            ini = meio;
        else
            fim = meio;
    }
    return ini;
}

static void erro_texto(const char *t) {
    while (*t && tam_erro < MAX_ERRO) erro[tam_erro++] = (uint8_t)*t++;
}

static void erro_nome_em(uint32_t alvo) {
    uint32_t i, nome, cursor = ini_nomes;
    if (n_pos == 0) return;
    i = acha_posicao(alvo);
    nome = ler16(ini_pos + i * TAM_POSICAO + 12);
    if (nome == SEM_NOME || nome >= n_nomes || ler32(ini_pos + i * TAM_POSICAO) != alvo) {
        erro_texto("?");
        return;
    }
    while (nome--) cursor += 2 + ler16(cursor);
    i = ler16(cursor);
    cursor += 2;
    while (i-- && tam_erro < MAX_ERRO) erro[tam_erro++] = programa[cursor++];
}

static int32_t falhar(const char *mensagem) {
    tam_erro = 0;
    erro_texto(mensagem);
    estado = VM_ERRO;
    return estado;
}

static int32_t falhar_variavel(void) {
    tam_erro = 0;
    erro_texto("variável '");
    erro_nome_em(pc);
    erro_texto("' não tem valor");
    estado = VM_ERRO;
    return estado;
}

static int32_t invalido(void) {
    return falhar("bytecode inválido");
}

uint8_t *vm_buffer(void) { return programa; }
uint32_t vm_buffer_capacidade(void) { return MAX_PROGRAMA; }
void vm_definir_limite(uint32_t p) { limite = p; }

void vm_reiniciar(void) {
    for (uint32_t i = 0; i < n_globais; i++) globais[i] = vazio();
    pc = 0;
    sp = 0;
    passos = 0;
    tam_saida = 0;
    tam_erro = 0;
    nq = 1;
    quadros[0].retorno = 0;
    quadros[0].base = 0;
    quadros[0].piso = 0;
    quadros[0].funcao = SEM_NOME;
    estado = VM_RODANDO;
}

/* Valida a estrutura do arquivo; o conteúdo do código é verificado ao executar. */
int32_t vm_carregar(uint32_t tamanho) {
    uint32_t c = 4, n;
    estado = VM_TERMINOU;
    n_globais = 0;
    if (tamanho > MAX_PROGRAMA || tamanho < 4) return 1;
    if (programa[0] != 'L' || programa[1] != 'I' || programa[2] != 'N' || programa[3] != '1') return 1;
    tam_programa = tamanho;

#define PRECISA_BYTES(q) \
    if ((uint64_t)c + (uint64_t)(q) > tam_programa) return 1

    PRECISA_BYTES(2);
    n_const = ler16(c);
    c += 2;
    ini_const = c;
    PRECISA_BYTES((uint64_t)n_const * 8);
    c += n_const * 8;

    PRECISA_BYTES(2);
    n_nomes = ler16(c);
    c += 2;
    ini_nomes = c;
    for (uint32_t i = 0; i < n_nomes; i++) {
        PRECISA_BYTES(2);
        n = ler16(c);
        c += 2;
        PRECISA_BYTES(n);
        c += n;
    }

    PRECISA_BYTES(4);
    n = ler16(c);
    if (n > MAX_GLOBAIS) return 1;
    n_func = ler16(c + 2);
    c += 4;
    ini_func = c;
    PRECISA_BYTES((uint64_t)n_func * TAM_FUNCAO);
    c += n_func * TAM_FUNCAO;

    PRECISA_BYTES(4);
    tam_cod = ler32(c);
    c += 4;
    ini_cod = c;
    PRECISA_BYTES(tam_cod);
    c += tam_cod;

    PRECISA_BYTES(4);
    n_pos = ler32(c);
    c += 4;
    ini_pos = c;
    PRECISA_BYTES((uint64_t)n_pos * TAM_POSICAO);

    for (uint32_t i = 0; i < n_func; i++) {
        uint32_t f = ini_func + i * TAM_FUNCAO;
        if (ler16(f + 6) < ler16(f + 4)) return 1;
    }
#undef PRECISA_BYTES
    n_globais = n;
    vm_reiniciar();
    return 0;
}

/* Quantos valores a instrução pode retirar sem invadir as variáveis do quadro. */
#define EXIGE(q)                                   \
    do {                                           \
        if (sp - quadros[nq - 1].piso < (q)) return invalido(); \
    } while (0)

#define EMPILHA(v)                                 \
    do {                                           \
        if (sp >= MAX_PILHA) return falhar("pilha cheia"); \
        pilha[sp++] = (v);                         \
    } while (0)

int32_t vm_passo(void) {
    uint32_t c, arg, largura;
    uint8_t op;
    double a, b;

    if (estado != VM_RODANDO) return estado;
    if (passos >= limite) return falhar("limite de passos atingido");
    passos++;

    if (pc >= tam_cod) return invalido();
    c = ini_cod + pc;
    op = programa[c];
    if (op > DESCARTA) return invalido();
    largura = (op == CONST_ || (op >= LE_GLOBAL && op <= GRAVA_LOCAL) || op == CHAMA) ? 2u
              : (op == PULA || op == PULA_SE_ZERO) ? 4u : 0u;
    if (tam_cod - pc - 1 < largura) return invalido();
    arg = largura == 2 ? ler16(c + 1) : largura == 4 ? ler32(c + 1) : 0;

    switch (op) {
    case PARA:
        estado = VM_TERMINOU;
        return estado;
    case CONST_:
        if (arg >= n_const) return invalido();
        EMPILHA(ler_double(ini_const + arg * 8));
        break;
    case LE_GLOBAL:
        if (arg >= n_globais) return invalido();
        if (eh_vazio(globais[arg])) return falhar_variavel();
        EMPILHA(globais[arg]);
        break;
    case GRAVA_GLOBAL:
        if (arg >= n_globais) return invalido();
        EXIGE(1u);
        globais[arg] = pilha[--sp];
        break;
    case LE_LOCAL: {
        const Quadro *q = &quadros[nq - 1];
        if (q->base + arg >= q->piso) return invalido();
        if (eh_vazio(pilha[q->base + arg])) return falhar_variavel();
        EMPILHA(pilha[q->base + arg]);
        break;
    }
    case GRAVA_LOCAL: {
        const Quadro *q = &quadros[nq - 1];
        if (q->base + arg >= q->piso) return invalido();
        EXIGE(1u);
        pilha[q->base + arg] = pilha[--sp];
        break;
    }
    case SOMA: case SUB: case MUL: case DIV: case RESTO:
    case IGUAL: case DIFERENTE: case MENOR: case MENOR_IGUAL: case MAIOR: case MAIOR_IGUAL:
        EXIGE(2u);
        b = pilha[sp - 1];
        a = pilha[sp - 2];
        if ((op == DIV || op == RESTO) && b == 0.0) return falhar("divisão por zero");
        switch (op) {
        case SOMA: a = a + b; break;
        case SUB: a = a - b; break;
        case MUL: a = a * b; break;
        case DIV: a = a / b; break;
        case RESTO: a = a - b * __builtin_trunc(a / b); break;
        case IGUAL: a = a == b ? 1.0 : 0.0; break;
        case DIFERENTE: a = a != b ? 1.0 : 0.0; break;
        case MENOR: a = a < b ? 1.0 : 0.0; break;
        case MENOR_IGUAL: a = a <= b ? 1.0 : 0.0; break;
        case MAIOR: a = a > b ? 1.0 : 0.0; break;
        default: a = a >= b ? 1.0 : 0.0; break;
        }
        sp -= 2;
        pilha[sp++] = a;
        break;
    case NEG:
        EXIGE(1u);
        pilha[sp - 1] = -pilha[sp - 1];
        break;
    case PULA:
        pc = arg;
        return estado;
    case PULA_SE_ZERO:
        EXIGE(1u);
        if (pilha[--sp] == 0.0) {
            pc = arg;
            return estado;
        }
        break;
    case CHAMA: {
        uint32_t f, parametros, extras;
        Quadro *q;
        if (arg >= n_func) return invalido();
        f = ini_func + arg * TAM_FUNCAO;
        parametros = ler16(f + 4);
        extras = ler16(f + 6) - parametros;
        if (nq >= MAX_QUADROS) return falhar("chamadas demais: recursão profunda demais");
        if (sp + extras > MAX_PILHA) return falhar("pilha cheia");
        EXIGE(parametros);
        q = &quadros[nq++];
        q->retorno = pc + 3;
        q->base = sp - parametros;
        q->funcao = arg;
        for (uint32_t i = 0; i < extras; i++) pilha[sp++] = vazio();
        q->piso = sp;
        pc = ler32(f);
        return estado;
    }
    case RETORNA: {
        const Quadro *q;
        if (nq <= 1) return invalido();
        EXIGE(1u);
        a = pilha[sp - 1];
        q = &quadros[--nq];
        sp = q->base;
        pilha[sp++] = a;
        pc = q->retorno;
        return estado;
    }
    case IMPRIME: {
        uint32_t n;
        EXIGE(1u);
        n = formatar(pilha[sp - 1], texto);
        if (tam_saida + n + 1 > MAX_SAIDA) return falhar("saída grande demais");
        for (uint32_t i = 0; i < n; i++) saida[tam_saida++] = texto[i];
        saida[tam_saida++] = '\n';
        sp--;
        break;
    }
    default: /* DESCARTA */
        EXIGE(1u);
        sp--;
        break;
    }
    pc += 1 + largura;
    return estado;
}

int32_t vm_executar(void) {
    while (estado == VM_RODANDO) vm_passo();
    return estado;
}

int32_t vm_situacao(void) { return estado; }
uint32_t vm_pc(void) { return pc; }
uint32_t vm_passos(void) { return passos; }
uint32_t vm_topo(void) { return sp; }
uint32_t vm_quadros(void) { return nq; }
uint32_t vm_quadro_base(uint32_t i) { return i < nq ? quadros[i].base : 0; }
uint32_t vm_quadro_piso(uint32_t i) { return i < nq ? quadros[i].piso : 0; }
uint32_t vm_quadro_funcao(uint32_t i) { return i < nq ? quadros[i].funcao : SEM_NOME; }

uint32_t vm_linha(void) {
    return n_pos ? ler32(ini_pos + acha_posicao(pc) * TAM_POSICAO + 4) : 0;
}

uint32_t vm_coluna(void) {
    return n_pos ? ler32(ini_pos + acha_posicao(pc) * TAM_POSICAO + 8) : 0;
}

const uint8_t *vm_saida(void) { return saida; }
uint32_t vm_saida_tamanho(void) { return tam_saida; }
const uint8_t *vm_erro(void) { return erro; }
uint32_t vm_erro_tamanho(void) { return tam_erro; }
const uint8_t *vm_texto(void) { return texto; }
uint32_t vm_formatar(double x) { return formatar(x, texto); }

int32_t vm_pilha_texto(uint32_t i) {
    if (i >= sp || eh_vazio(pilha[i])) return -1;
    return (int32_t)formatar(pilha[i], texto);
}

int32_t vm_global_texto(uint32_t i) {
    if (i >= n_globais || eh_vazio(globais[i])) return -1;
    return (int32_t)formatar(globais[i], texto);
}
