import { describe, expect, it } from 'vitest'
import { PADROES } from './teoria'
import { PALETAS } from './cores'
import { alturasDaSequencia, alturasVisiveis } from './sequencia'
import type { Afinacao } from './tipos'
import { TODAS_AS_CLASSES, type EscolhasDaVista } from './vista'

const BAIXO_4: Afinacao = { id: 'baixo-4', nome: 'E A D G', instrumento: 'baixo', cordas: [28, 33, 38, 43] }
const padrao = (id: string) => PADROES.find((p) => p.id === id) ?? null

describe('alturasDaSequencia (S6)', () => {
  it('escala: da tônica mais grave do braço até a oitava, subindo', () => {
    // Lá mais grave no baixo de 4 cordas: corda E, casa 5 = 33.
    expect(alturasDaSequencia(BAIXO_4, 12, 9, padrao('escala-pentatonica-menor'))).toEqual([33, 36, 38, 40, 43, 45])
  })

  it('a tônica na corda solta mais grave começa nela', () => {
    expect(alturasDaSequencia(BAIXO_4, 12, 4, padrao('acorde-maior'))).toEqual([28, 32, 35, 40])
  })

  it('grau composto sobe acima da oitava: o 9 de add9 fica depois do 5, sem oitava a seguir', () => {
    expect(alturasDaSequencia(BAIXO_4, 12, 4, padrao('acorde-add9'))).toEqual([28, 32, 35, 42])
  })

  it('sem padrão, a escala cromática de uma oitava', () => {
    expect(alturasDaSequencia(BAIXO_4, 12, 4, null)).toEqual(Array.from({ length: 13 }, (_, i) => 28 + i))
  })

  it('intervalo: as duas notas, sem repetir a oitava', () => {
    expect(alturasDaSequencia(BAIXO_4, 12, 4, padrao('intervalo-quinta-justa'))).toEqual([28, 35])
    expect(alturasDaSequencia(BAIXO_4, 12, 4, padrao('intervalo-oitava'))).toEqual([28, 40])
  })
})

describe('alturasVisiveis', () => {
  const NOTAS: EscolhasDaVista = {
    modo: 'notas',
    filtro: [],
    selecionada: null,
    tonica: null,
    padrao: null,
    rotulo: 'nome',
    nome: { nomenclatura: 'cifra', acidente: 'sustenido' },
    paleta: PALETAS.claro,
  }

  it('as alturas acesas, sem repetir, da mais grave à mais aguda', () => {
    // E (4) e A (9) em 5 casas: E1 28, A1 33 (corda E casa 5 e corda A solta), E2 40, A2 45.
    expect(alturasVisiveis(BAIXO_4, 5, { ...NOTAS, filtro: [9, 4] })).toEqual([28, 33, 38 + 2, 43 + 2])
  })

  it('a nota destacada pelo toque entra mesmo fora do filtro', () => {
    expect(alturasVisiveis(BAIXO_4, 2, { ...NOTAS, filtro: [], selecionada: 5 })).toEqual([29])
  })

  it('nada aceso, nada a tocar', () => {
    expect(alturasVisiveis(BAIXO_4, 12, NOTAS)).toEqual([])
  })

  it('com todas acesas, a cromática do braço inteiro', () => {
    expect(alturasVisiveis(BAIXO_4, 12, { ...NOTAS, filtro: TODAS_AS_CLASSES })).toEqual(
      Array.from({ length: 43 + 12 - 28 + 1 }, (_, i) => 28 + i),
    )
  })
})
