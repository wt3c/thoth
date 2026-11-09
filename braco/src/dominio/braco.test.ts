import { describe, expect, it } from 'vitest'
import { gerarBraco } from './braco'
import { frequencia } from './frequencia'
import type { Afinacao } from './tipos'

const BAIXO_4: Afinacao = { id: 'baixo-4', nome: 'E A D G', instrumento: 'baixo', cordas: [28, 33, 38, 43] }
const BAIXO_5: Afinacao = { id: 'baixo-5', nome: 'B E A D G', instrumento: 'baixo', cordas: [23, 28, 33, 38, 43] }
const E = 4
const A = 9
const B = 11

function em(afinacao: Afinacao, corda: number, casa: number) {
  const posicao = gerarBraco(afinacao, 24).find((p) => p.corda === corda && p.casa === casa)
  if (!posicao) throw new Error(`sem posição ${corda}/${casa}`)
  return posicao
}

describe('gerarBraco', () => {
  it('baixo de 4 cordas: corda grave solta é E, casa 12 é E, casa 5 é A', () => {
    expect(em(BAIXO_4, 0, 0).classe).toBe(E)
    expect(em(BAIXO_4, 0, 12).classe).toBe(E)
    expect(em(BAIXO_4, 0, 12).altura).toBe(40)
    expect(em(BAIXO_4, 0, 5).classe).toBe(A)
  })

  it('baixo de 5 cordas: corda grave solta é B, casa 5 é E', () => {
    expect(em(BAIXO_5, 0, 0).classe).toBe(B)
    expect(em(BAIXO_5, 0, 5).classe).toBe(E)
  })

  it('gera da casa 0 até a última em todas as cordas', () => {
    const braco = gerarBraco(BAIXO_4, 12)
    expect(braco).toHaveLength(4 * 13)
    expect(Math.max(...braco.map((p) => p.casa))).toBe(12)
  })
})

describe('frequencia', () => {
  it('A4 é 440 Hz e a oitava dobra', () => {
    expect(frequencia(69)).toBe(440)
    expect(frequencia(81)).toBeCloseTo(880, 10)
    expect(frequencia(28)).toBeCloseTo(41.2034, 3)
  })
})
