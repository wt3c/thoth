import { describe, expect, it } from 'vitest'
import { ALVO_MINIMO, geometriaDoBraco } from './geometria'

const todas = (cordas: number, casas: number) =>
  Array.from({ length: cordas }, (_, corda) => Array.from({ length: casas + 1 }, (_, casa) => ({ corda, casa }))).flat()

describe('geometriaDoBraco', () => {
  it('horizontal: pestana à esquerda, corda grave embaixo, casas avançando para a direita', () => {
    const g = geometriaDoBraco(4, 12, 'horizontal')
    expect(g.centro(0, 0).y).toBeGreaterThan(g.centro(3, 0).y)
    expect(g.centro(0, 5).x).toBeGreaterThan(g.centro(0, 4).x)
    expect(g.trastes[0]?.x1).toBe(g.trastes[0]?.x2)
    expect(g.largura).toBeGreaterThan(g.altura)
  })

  it('vertical: pestana em cima, corda grave à esquerda, casas descendo', () => {
    const g = geometriaDoBraco(4, 12, 'vertical')
    expect(g.centro(0, 0).x).toBeLessThan(g.centro(3, 0).x)
    expect(g.centro(0, 5).y).toBeGreaterThan(g.centro(0, 4).y)
    expect(g.trastes[0]?.y1).toBe(g.trastes[0]?.y2)
    expect(g.altura).toBeGreaterThan(g.largura)
  })

  it('vertical: até 7 cordas cabem na largura de um celular em pé (358 px úteis)', () => {
    for (const cordas of [4, 5, 6, 7]) expect(geometriaDoBraco(cordas, 24, 'vertical').largura).toBeLessThanOrEqual(358)
  })

  it.each(['horizontal', 'vertical'] as const)('%s: todo alvo tem ≥ 44 px e nenhum invade o vizinho', (orientacao) => {
    const g = geometriaDoBraco(7, 24, orientacao)
    expect(g.alvo.largura).toBeGreaterThanOrEqual(ALVO_MINIMO)
    expect(g.alvo.altura).toBeGreaterThanOrEqual(ALVO_MINIMO)
    const caixas = todas(7, 24).map(({ corda, casa }) => g.centro(corda, casa))
    for (const [i, a] of caixas.entries()) {
      for (const b of caixas.slice(i + 1)) {
        const separados = Math.abs(a.x - b.x) >= g.alvo.largura || Math.abs(a.y - b.y) >= g.alvo.altura
        expect(separados).toBe(true)
      }
    }
  })

  it.each(['horizontal', 'vertical'] as const)('%s: todas as notas ficam dentro do desenho', (orientacao) => {
    const g = geometriaDoBraco(6, 24, orientacao)
    for (const { corda, casa } of todas(6, 24)) {
      const c = g.centro(corda, casa)
      expect(c.x - g.alvo.largura / 2).toBeGreaterThanOrEqual(0)
      expect(c.x + g.alvo.largura / 2).toBeLessThanOrEqual(g.largura)
      expect(c.y - g.alvo.altura / 2).toBeGreaterThanOrEqual(0)
      expect(c.y + g.alvo.altura / 2).toBeLessThanOrEqual(g.altura)
    }
  })

  it('números das casas marcadas, fora da madeira', () => {
    for (const orientacao of ['horizontal', 'vertical'] as const) {
      const g = geometriaDoBraco(4, 24, orientacao)
      expect(g.numeros.map((n) => n.casa)).toEqual([3, 5, 7, 9, 12, 15, 17, 19, 21, 24])
      const m = g.madeira
      for (const n of g.numeros) {
        const dentro = n.x > m.x && n.x < m.x + m.largura && n.y > m.y && n.y < m.y + m.altura
        expect(dentro).toBe(false)
      }
    }
  })

  it('uma corda e um traste por posição; dois pontos na casa 12', () => {
    const g = geometriaDoBraco(5, 24, 'vertical')
    expect(g.cordas).toHaveLength(5)
    expect(g.trastes).toHaveLength(25)
    expect(g.marcacoes.filter((m) => m.casa === 12)).toHaveLength(2)
    expect(g.marcacoes.filter((m) => m.casa === 5)).toHaveLength(1)
  })
})
