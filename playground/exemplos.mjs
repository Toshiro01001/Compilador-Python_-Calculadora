// Programas prontos do playground. Os valores são apenas ilustrativos.
export const EXEMPLOS = [
  {
    nome: "Regra de desconto",
    fonte: `# Regra de negócio escrita como programa:
# mudar a política é mudar este texto, não o sistema.
func desconto(total, cliente_novo) {
  if total >= 1000 {
    return total * 0.10
  }
  if cliente_novo == 1 {
    return total * 0.05
  }
  return 0
}

print(1250 - desconto(1250, 0))
print(400 - desconto(400, 1))
print(400 - desconto(400, 0))
`,
  },
  {
    nome: "Parcela com juros",
    fonte: `# Fórmula de parcela fixa (tabela Price)
func potencia(base, n) {
  r = 1
  while n > 0 {
    r = r * base
    n = n - 1
  }
  return r
}

func parcela(valor, juros, meses) {
  f = potencia(1 + juros, meses)
  return valor * juros * f / (f - 1)
}

print(parcela(10000, 0.02, 12))
`,
  },
  {
    nome: "Dígito verificador",
    fonte: `# Validação: dígito de conferência por módulo 11,
# com pesos de 2 a 9 da direita para a esquerda.
func digito(numero) {
  soma = 0
  peso = 2
  while numero > 0 {
    d = numero % 10
    soma = soma + d * peso
    peso = peso + 1
    if peso > 9 {
      peso = 2
    }
    numero = (numero - d) / 10
  }
  r = soma % 11
  if r < 2 {
    return 0
  }
  return 11 - r
}

print(digito(261533))
`,
  },
  {
    nome: "Fatorial (recursão)",
    fonte: `func fatorial(n) {
  if n <= 1 {
    return 1
  }
  return n * fatorial(n - 1)
}

print(fatorial(6))
`,
  },
  {
    nome: "Fibonacci (while)",
    fonte: `a = 0
b = 1
i = 0
while i < 10 {
  print(a)
  proximo = a + b
  a = b
  b = proximo
  i = i + 1
}
`,
  },
  {
    nome: "Erro de sintaxe",
    fonte: `# A conta termina sem o segundo valor.
total = 10 +
print(total)
`,
  },
  {
    nome: "Laço infinito",
    fonte: `# Sem o limite de passos, isto travaria a página.
x = 0
while 1 {
  x = x + 1
}
`,
  },
];
