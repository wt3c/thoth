import { describe, expect, it } from 'vitest'
import { nomeDaClasse, exibirNome } from './nomes'

describe('nomeDaClasse', () => {
  it('cifra com sustenido por padrão', () => {
    expect([0, 1, 4, 9, 11].map((c) => nomeDaClasse(c))).toEqual(['C', 'C#', 'E', 'A', 'B'])
  })
})

// A grafia ASCII permanece disponível para serialização e teoria.
describe('opções de nome e exibição', () => {
  it('seleciona bemóis e solfejo sem perder a grafia ASCII da cifra', () => {
    expect(nomeDaClasse(1, { nomenclatura: 'cifra', acidente: 'bemol' })).toBe('Db')
    expect(nomeDaClasse(6, { nomenclatura: 'solfejo', acidente: 'sustenido' })).toBe('Fá♯')
    expect(nomeDaClasse(10, { nomenclatura: 'solfejo', acidente: 'bemol' })).toBe('Si♭')
    expect(Array.from({ length: 7 }, (_, i) => [0, 2, 4, 5, 7, 9, 11][i]!)
      .map((c) => nomeDaClasse(c, { nomenclatura: 'solfejo', acidente: 'bemol' })))
      .toEqual(['Dó', 'Ré', 'Mi', 'Fá', 'Sol', 'Lá', 'Si'])
  })
  it('normaliza classes negativas e acima da oitava', () => {
    expect(nomeDaClasse(-1)).toBe('B')
    expect(nomeDaClasse(13)).toBe('C#')
  })
  it.each([
    ['Bb', 'B♭', 'Si♭'], ['F#', 'F♯', 'Fá♯'], ['Cbb', 'C𝄫', 'Dó𝄫'],
    ['E#', 'E♯', 'Mi♯'], ['F##', 'F𝄪', 'Fá𝄪'], ['C', 'C', 'Dó'],
  ])('exibe %s preservando a grafia', (ascii, cifra, solfejo) => {
    expect(exibirNome(ascii, 'cifra')).toBe(cifra)
    expect(exibirNome(ascii, 'solfejo')).toBe(solfejo)
  })
  it('rejeita nomes inválidos com contexto', () => {
    expect(() => exibirNome('H#', 'cifra')).toThrow(/H#/)
    expect(() => exibirNome('Cb#', 'cifra')).toThrow(/Cb#/)
  })
})
