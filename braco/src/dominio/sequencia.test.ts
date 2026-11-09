import { describe, expect, it } from 'vitest'
import { PADROES } from './teoria'
import { PALETAS } from './cores'
import { alturasDaSequencia, posicoesVisiveis } from './sequencia'
import type { Afinacao, Posicao } from './tipos'
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

describe('posicoesVisiveis', () => {
  const NOTAS: EscolhasDaVista = {
    modo: 'notas',
    filtro: [],
    selecionada: null,
    referencia: null,
    tonica: null,
    padrao: null,
    rotulo: 'nome',
    nome: { nomenclatura: 'cifra', acidente: 'sustenido' },
    paleta: PALETAS.claro,
  }
  const lugares = (ps: readonly Posicao[]) => ps.map((p) => `${p.corda}-${p.casa}`)

  it('cada posição acesa uma vez, da mais grave à mais aguda; no mesmo som, a corda grave antes', () => {
    // E (4) e A (9) em 5 casas: E1 corda E solta; A1 na corda E casa 5 e na corda A solta;
    // E2 corda D casa 2; A2 corda G casa 2.
    const posicoes = posicoesVisiveis(BAIXO_4, 5, { ...NOTAS, filtro: [9, 4] })
    expect(lugares(posicoes)).toEqual(['0-0', '0-5', '1-0', '2-2', '3-2'])
    expect(posicoes.map((p) => p.altura)).toEqual([28, 33, 33, 40, 45])
  })

  it('a nota destacada pelo toque entra mesmo fora do filtro', () => {
    expect(lugares(posicoesVisiveis(BAIXO_4, 2, { ...NOTAS, filtro: [], selecionada: 5 }))).toEqual(['0-1'])
  })

  it('nada aceso, nada a tocar', () => {
    expect(posicoesVisiveis(BAIXO_4, 12, NOTAS)).toEqual([])
  })

  it('com todas acesas, todas as posições do braço, em altura que nunca desce', () => {
    const posicoes = posicoesVisiveis(BAIXO_4, 12, { ...NOTAS, filtro: TODAS_AS_CLASSES })
    expect(posicoes).toHaveLength(4 * 13)
    expect(posicoes.every((p, i) => i === 0 || (posicoes[i - 1]?.altura ?? 0) <= p.altura)).toBe(true)
  })
})
