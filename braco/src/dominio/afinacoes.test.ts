import { describe, expect, it } from 'vitest'
import dados from './afinacoes.json'
import { afinacoesDe, afinacaoPadrao, afinacaoPorId } from './afinacoes.js'

const ESPERADAS = {
  'baixo-4': [28, 33, 38, 43],
  'baixo-5': [23, 28, 33, 38, 43],
  'baixo-6': [23, 28, 33, 38, 43, 48],
  'baixo-drop-d': [26, 33, 38, 43],
  'guitarra-6': [40, 45, 50, 55, 59, 64],
  'baixo-7': [23, 28, 33, 38, 43, 48, 53],
  'baixo-7-fa-sustenido': [18, 23, 28, 33, 38, 43, 48],
  'baixo-5-agudo': [28, 33, 38, 43, 48],
  'baixo-meio-tom-abaixo': [27, 32, 37, 42],
  'baixo-d-standard': [26, 31, 36, 41],
  'guitarra-drop-d': [38, 45, 50, 55, 59, 64],
  'guitarra-meio-tom-abaixo': [39, 44, 49, 54, 58, 63],
  'guitarra-dadgad': [38, 45, 50, 55, 57, 62],
  'guitarra-open-g': [38, 43, 50, 55, 59, 62],
} as const

describe('afinações', () => {
  it.each(Object.entries(ESPERADAS))('%s preserva as alturas esperadas', (id, cordas) => {
    expect(afinacaoPorId(id).cordas).toEqual(cordas)
  })
  it('tem ids únicos e alturas MIDI inteiras crescentes do grave ao agudo', () => {
    expect(new Set(dados.map((a) => a.id)).size).toBe(dados.length)
    for (const { cordas } of dados) {
      cordas.forEach((altura, i) => {
        expect(Number.isInteger(altura) && altura >= 0 && altura <= 127).toBe(true)
        if (i > 0) expect(altura).toBeGreaterThan(cordas[i - 1]!)
      })
    }
  })
  it('filtra por instrumento e número de cordas sem misturar presets', () => {
    expect(afinacoesDe('baixo', 7).map((a) => a.id)).toEqual(['baixo-7', 'baixo-7-fa-sustenido'])
    expect(afinacoesDe('guitarra', 6)).toHaveLength(5)
    expect(afinacoesDe('baixo', 8)).toEqual([])
  })
  it.each([4, 5, 6, 7])('seleciona o baixo padrão de %i cordas', (n) => {
    expect(afinacaoPadrao('baixo', n).id).toBe(`baixo-${n}`)
  })
  it('seleciona guitarra padrão e rejeita consultas desconhecidas com contexto', () => {
    expect(afinacaoPadrao('guitarra', 6).id).toBe('guitarra-6')
    expect(() => afinacaoPadrao('baixo', 8)).toThrow(/baixo.*8/)
    expect(() => afinacaoPadrao('guitarra', 7)).toThrow(/guitarra.*7/)
    expect(() => afinacaoPorId('inexistente')).toThrow(/inexistente/)
  })
})
