import type { Cor, Grau, IdTema, Paleta } from './tipos'

function luminancia(cor: Cor): number {
  if (!/^#[\da-f]{6}$/i.test(cor)) throw new Error(`Cor inválida (esperado #rrggbb): ${cor}`)
  const canais = [1, 3, 5].map((inicio) => {
    const canal = parseInt(cor.slice(inicio, inicio + 2), 16) / 255
    return canal <= 0.04045 ? canal / 12.92 : ((canal + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * canais[0]! + 0.7152 * canais[1]! + 0.0722 * canais[2]!
}

/** Razão WCAG 2.x, entre 1 (iguais) e 21 (preto/branco). */
export function razaoContraste(a: Cor, b: Cor): number {
  const la = luminancia(a)
  const lb = luminancia(b)
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)
}

export function corDoTexto(fundo: Cor): Cor {
  const preto = razaoContraste(fundo, '#000000')
  const branco = razaoContraste(fundo, '#ffffff')
  if (Math.max(preto, branco) < 4.5) throw new Error(`Sem texto com contraste 4,5:1 no fundo ${fundo}`)
  return preto >= branco ? '#000000' : '#ffffff'
}

const CLASSES_CLARAS = [
  '#8c2244', '#914600', '#725300', '#4a6000', '#176032', '#00645c',
  '#006273', '#005b91', '#284e9d', '#60419a', '#83317c', '#932857',
] as const
const CLASSES_ESCURAS = [
  '#ff8ca8', '#ffad70', '#eacb65', '#bad36b', '#80d698', '#63d7bb',
  '#66cfe2', '#7dc2ff', '#a6b3ff', '#c7a4f4', '#e69de1', '#f69bc0',
] as const

// Família azul/laranja da paleta Okabe–Ito com variações de luminosidade.
// O rótulo complementa as cores: não há promessa de 12 matizes distinguíveis.
const CLASSES_DALTONICAS = [
  '#004c72', '#005780', '#00628f', '#006d9e', '#0078ad', '#0083b8',
  '#713600', '#7e3f00', '#8b4800', '#985100', '#a55a00', '#b26300',
] as const

function graus(cores: readonly Cor[]): Readonly<Record<string, Cor>> {
  return Object.fromEntries(['2', '3', '4', '5', '6', '7', '9', '11', '13']
    .map((grau, indice) => [grau, cores[indice]!]))
}

export const PALETAS: Record<IdTema, Paleta> = {
  claro: {
    id: 'claro', braco: { madeira: '#f5ead6', traste: '#e3dbce', corda: '#d5cec1', marcacao: '#786c58' },
    porClasse: CLASSES_CLARAS, tonica: '#181818', porGrau: graus(CLASSES_CLARAS),
  },
  escuro: {
    id: 'escuro', braco: { madeira: '#211a14', traste: '#35302a', corda: '#49433b', marcacao: '#a2937d' },
    porClasse: CLASSES_ESCURAS, tonica: '#ffffff', porGrau: graus(CLASSES_ESCURAS),
  },
  daltonico: {
    id: 'daltonico', braco: { madeira: '#fff5e5', traste: '#f0e7d9', corda: '#e7dfd2', marcacao: '#746957' },
    porClasse: CLASSES_DALTONICAS, tonica: '#181818', porGrau: graus(CLASSES_DALTONICAS),
  },
}

export function corDoGrau(paleta: Paleta, grau: Grau): Cor {
  if (grau === '1') return paleta.tonica
  const partes = /^(?:#{1,2}|b{1,2})?([1-9]\d*)$/.exec(grau)
  const cor = partes ? paleta.porGrau[partes[1]!] : undefined
  if (!cor) throw new Error(`Grau sem cor na paleta ${paleta.id}: ${grau}`)
  return cor
}
