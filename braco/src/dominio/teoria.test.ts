import { describe, expect, it } from 'vitest'
import { PADROES, notasDoPadrao, grauCromatico, grauNoPadrao } from './teoria'
import type { Padrao } from './tipos'

const ESCALAS: Record<string, string> = {
  maior: '1 2 3 4 5 6 7', 'menor-natural': '1 2 b3 4 5 b6 b7',
  'menor-harmonica': '1 2 b3 4 5 b6 7', 'menor-melodica': '1 2 b3 4 5 6 7',
  'pentatonica-maior': '1 2 3 5 6', 'pentatonica-menor': '1 b3 4 5 b7', blues: '1 b3 4 #4 5 b7',
  jonio: '1 2 3 4 5 6 7', dorico: '1 2 b3 4 5 6 b7', frigio: '1 b2 b3 4 5 b6 b7',
  lidio: '1 2 3 #4 5 6 7', mixolidio: '1 2 3 4 5 6 b7', eolio: '1 2 b3 4 5 b6 b7',
  locrio: '1 b2 b3 4 b5 b6 b7',
}
const ACORDES: Record<string, string> = {
  maior: '1 3 5', menor: '1 b3 5', diminuto: '1 b3 b5', aumentado: '1 3 #5',
  sus2: '1 2 5', sus4: '1 4 5', '7M': '1 3 5 7', '7': '1 3 5 b7',
  m7: '1 b3 5 b7', m7b5: '1 b3 b5 b7', '°7': '1 b3 b5 bb7', m7M: '1 b3 5 7',
  add9: '1 3 5 9', '6': '1 3 5 6', m6: '1 b3 5 6',
}
function padrao(id: string): Padrao {
  const encontrado = PADROES.find((p) => p.id === id)
  if (!encontrado) throw new Error(`Padrão ausente: ${id}`)
  return encontrado
}

describe('catálogo de teoria', () => {
  it.each(Object.entries(ESCALAS))('escala %s guarda graus grafados', (id, graus) => {
    expect(padrao(`escala-${id}`)).toMatchObject({ tipo: 'escala', graus: graus.split(' ') })
  })
  it.each(Object.entries(ACORDES))('acorde %s guarda graus grafados', (id, graus) => {
    expect(padrao(`acorde-${id}`)).toMatchObject({ tipo: 'acorde', graus: graus.split(' ') })
  })
  it('tem ids únicos e 13 intervalos da uníssona à oitava', () => {
    expect(new Set(PADROES.map((p) => p.id)).size).toBe(PADROES.length)
    const intervalos = PADROES.filter((p) => p.tipo === 'intervalo')
    expect(intervalos).toHaveLength(13)
    expect(intervalos.map((p) => notasDoPadrao(0, p).map((n) => n.classe)))
      .toEqual(Array.from({ length: 13 }, (_, i) => [0, i % 12]))
    expect(intervalos.at(-1)?.graus).toEqual(['1', '8'])
  })
})

describe('grafia por grau', () => {
  it.each([
    [5, 'escala-maior', 'sustenido', ['F', 'G', 'A', 'Bb', 'C', 'D', 'E']],
    [3, 'escala-menor-natural', 'sustenido', ['D#', 'E#', 'F#', 'G#', 'A#', 'B', 'C#']],
    [3, 'escala-menor-natural', 'bemol', ['Eb', 'F', 'Gb', 'Ab', 'Bb', 'Cb', 'Db']],
    [8, 'escala-maior', 'sustenido', ['G#', 'A#', 'B#', 'C#', 'D#', 'E#', 'F##']],
    [1, 'acorde-°7', 'bemol', ['Db', 'Fb', 'Abb', 'Cbb']],
    [0, 'acorde-add9', 'sustenido', ['C', 'E', 'G', 'D']],
  ] as const)('%s %s %s tem nomes coerentes', (tonica, id, acidente, nomes) => {
    expect(notasDoPadrao(tonica, padrao(id), acidente).map((n) => n.nome)).toEqual(nomes)
  })
  it('calcula classes, graus e grafia de fá maior', () => {
    expect(notasDoPadrao(5, padrao('escala-maior'))[3]).toEqual({ classe: 10, grau: '4', nome: 'Bb' })
  })
  it('transpõe cada padrão para as 12 tônicas e preserva o grau grafado', () => {
    for (const p of PADROES) {
      const emDo = notasDoPadrao(0, p)
      for (let tonica = 0; tonica < 12; tonica++) {
        expect(notasDoPadrao(tonica, p).map((n) => [n.classe, n.grau]))
          .toEqual(emDo.map((n) => [(n.classe + tonica) % 12, n.grau]))
      }
    }
  })
  it('distingue o grau no padrão da função cromática e retorna null fora dele', () => {
    expect(grauNoPadrao(0, 6, padrao('escala-lidio'))).toBe('#4')
    expect(grauNoPadrao(0, 6, padrao('acorde-diminuto'))).toBe('b5')
    expect(grauNoPadrao(0, 1, padrao('escala-maior'))).toBeNull()
    expect(Array.from({ length: 12 }, (_, i) => grauCromatico(5, (5 + i) % 12)))
      .toEqual(['1', 'b2', '2', 'b3', '3', '4', '#4', '5', 'b6', '6', 'b7', '7'])
    expect(grauCromatico(12, -1)).toBe('7')
  })
  it('rejeita grau malformado em vez de produzir nota silenciosamente', () => {
    expect(() => notasDoPadrao(0, { id: 'ruim', nome: 'Ruim', tipo: 'escala', graus: ['1', 'x3'] }))
      .toThrow(/x3/)
  })
})

describe('consistência independente de grafia e altura', () => {
  it('cada nome grafado representa a classe devolvida, com ambas as grafias de tônica', () => {
    const naturais: Record<string, number> = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 }
    for (const acidente of ['sustenido', 'bemol'] as const) {
      for (let tonica = 0; tonica < 12; tonica++) {
        for (const p of PADROES) {
          for (const nota of notasDoPadrao(tonica, p, acidente)) {
            expect(nota.nome).toMatch(/^[A-G](#{1,2}|b{1,2})?$/)
            const alteracao = [...nota.nome.slice(1)].reduce((soma, a) => soma + (a === '#' ? 1 : -1), 0)
            expect(((naturais[nota.nome[0]!]! + alteracao) % 12 + 12) % 12).toBe(nota.classe)
          }
        }
      }
    }
  })
  it('confere as alturas de graus naturais, alterados, compostos e da oitava', () => {
    const graus = ['1', 'b2', '2', 'b3', '3', '4', '#4', 'b5', '5', '#5', 'b6', '6', 'bb7', 'b7', '7', '8', '9', '11', '13']
    expect(notasDoPadrao(0, { id: 'referencia', nome: 'Referência', tipo: 'escala', graus }).map((n) => n.classe))
      .toEqual([0, 1, 2, 3, 4, 5, 6, 6, 7, 8, 8, 9, 9, 10, 11, 0, 2, 5, 9])
  })
})
