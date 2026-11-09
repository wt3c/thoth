/**
 * Onde cada coisa do braço fica no desenho (ADR-063). Calcula num eixo "ao longo" (casas) e
 * num "através" (cordas) e só no fim troca para x/y conforme a orientação:
 *
 * - horizontal: pestana à esquerda, corda grave embaixo — o baixo visto por quem toca;
 * - vertical: pestana em cima, corda grave à esquerda — o diagrama de acorde, que cabe num
 *   celular em pé com até 7 cordas.
 *
 * Sem DOM e sem Vue: o componente só desenha o que sai daqui.
 */
export type Orientacao = 'horizontal' | 'vertical'

export interface Ponto {
  readonly x: number
  readonly y: number
}
export interface Segmento {
  readonly x1: number
  readonly y1: number
  readonly x2: number
  readonly y2: number
}
export interface Caixa {
  readonly x: number
  readonly y: number
  readonly largura: number
  readonly altura: number
}

export interface GeometriaDoBraco {
  readonly orientacao: Orientacao
  readonly largura: number
  readonly altura: number
  readonly madeira: Caixa
  /** Índice 0 é a pestana. */
  readonly trastes: readonly Segmento[]
  /** Índice = corda (0 é a grave). */
  readonly cordas: readonly Segmento[]
  readonly marcacoes: readonly (Ponto & { readonly casa: number })[]
  readonly numeros: readonly (Ponto & { readonly casa: number })[]
  /** Tamanho do alvo de toque de cada nota, já em x/y. */
  readonly alvo: { readonly largura: number; readonly altura: number }
  centro(corda: number, casa: number): Ponto
}

/** WCAG 2.5.5: alvo de toque de pelo menos 44 × 44 px. */
export const ALVO_MINIMO = 44
/** O alvo ao longo da corda é um pouco maior; casas nunca ficam mais estreitas que ele + folga. */
const ALVO_AO_LONGO = 48
const CASA_MINIMA = ALVO_AO_LONGO + 6
/** Casa 1; as seguintes encolhem como num braço real, até o piso. */
const PRIMEIRA_CASA = 112
const MARGEM = 28
const LARGURA_SOLTA = 56
const CASAS_MARCADAS = [3, 5, 7, 9, 15, 17, 19, 21]

/** Medidas no eixo "através", que mudam com a orientação para caber 7 cordas em pé. */
const ATRAVES = {
  // Margem antes da primeira corda, espaço por corda, faixa dos números, margem final.
  horizontal: { antes: 14, espaco: 52, numeros: 24, depois: 0 },
  vertical: { antes: 24, espaco: 46, numeros: 0, depois: 4 },
} as const

export function geometriaDoBraco(numCordas: number, casas: number, orientacao: Orientacao): GeometriaDoBraco {
  const m = ATRAVES[orientacao]

  // Ao longo: posição de cada traste, pestana em índice 0.
  const trastesAo: number[] = [MARGEM + LARGURA_SOLTA]
  for (let i = 0; i < casas; i++) {
    trastesAo.push((trastesAo.at(-1) ?? 0) + Math.max(CASA_MINIMA, PRIMEIRA_CASA * 2 ** (-i / 12)))
  }
  const fimAo = trastesAo.at(-1) ?? 0
  const comprimento = fimAo + MARGEM
  const centroAo = (casa: number) =>
    casa === 0 ? MARGEM + LARGURA_SOLTA / 2 : ((trastesAo[casa - 1] ?? 0) + (trastesAo[casa] ?? 0)) / 2

  // Através: a ordem visual das cordas. Horizontal põe a grave embaixo; vertical, à esquerda.
  const inicioMadeira = m.antes
  const fimMadeira = m.antes + numCordas * m.espaco
  const espessura = fimMadeira + m.numeros + m.depois
  const ordem = (corda: number) => (orientacao === 'horizontal' ? numCordas - 1 - corda : corda)
  const centroAtraves = (corda: number) => inicioMadeira + ordem(corda) * m.espaco + m.espaco / 2
  const faixaNumeros = orientacao === 'horizontal' ? fimMadeira + m.numeros / 2 : m.antes / 2

  const ponto = (ao: number, atraves: number): Ponto =>
    orientacao === 'horizontal' ? { x: ao, y: atraves } : { x: atraves, y: ao }
  const segmento = (ao1: number, at1: number, ao2: number, at2: number): Segmento => {
    const a = ponto(ao1, at1)
    const b = ponto(ao2, at2)
    return { x1: a.x, y1: a.y, x2: b.x, y2: b.y }
  }

  const canto = ponto(MARGEM + LARGURA_SOLTA, inicioMadeira)
  const extensao = ponto(fimAo - MARGEM - LARGURA_SOLTA, numCordas * m.espaco)
  const tamanho = ponto(comprimento, espessura)
  const alvo = ponto(ALVO_AO_LONGO, ALVO_MINIMO)
  const marcadas = Array.from({ length: casas }, (_, i) => i + 1).filter(
    (c) => c % 12 === 0 || CASAS_MARCADAS.includes(c),
  )
  const largo = fimMadeira - inicioMadeira

  return {
    orientacao,
    largura: tamanho.x,
    altura: tamanho.y,
    madeira: { x: canto.x, y: canto.y, largura: extensao.x, altura: extensao.y },
    trastes: trastesAo.map((ao) => segmento(ao, inicioMadeira, ao, fimMadeira)),
    cordas: Array.from({ length: numCordas }, (_, c) => segmento(MARGEM, centroAtraves(c), fimAo, centroAtraves(c))),
    marcacoes: marcadas.flatMap((casa) => {
      const fracoes = casa % 12 === 0 ? [1 / 4, 3 / 4] : [1 / 2]
      return fracoes.map((f) => ({ casa, ...ponto(centroAo(casa), inicioMadeira + largo * f) }))
    }),
    numeros: marcadas.map((casa) => ({ casa, ...ponto(centroAo(casa), faixaNumeros) })),
    alvo: { largura: alvo.x, altura: alvo.y },
    centro: (corda, casa) => ponto(centroAo(casa), centroAtraves(corda)),
  }
}
