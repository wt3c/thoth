import { describe, expect, it } from 'vitest'
import { CONFIG_PADRAO } from './agendador'
import { limitarBpm, validarConfig } from './config-metronomo'
import type { ConfigMetronomo } from './tipos'

const com = (parcial: Partial<ConfigMetronomo>): ConfigMetronomo => ({ ...CONFIG_PADRAO, ...parcial })

describe('validarConfig', () => {
  it('aceita o padrão', () => {
    expect(validarConfig(CONFIG_PADRAO)).toBe(CONFIG_PADRAO)
  })

  it.each([
    ['bpm abaixo de 30', com({ bpm: 29 })],
    ['bpm acima de 244', com({ bpm: 245 })],
    ['bpm não finito', com({ bpm: Number.NaN })],
    ['zero tempos', com({ temposPorCompasso: 0 })],
    ['13 tempos', com({ temposPorCompasso: 13 })],
    ['tempos fracionários', com({ temposPorCompasso: 2.5 })],
    ['silenciar 0 compassos', com({ silencio: { ativo: true, tocar: 1, silenciar: 0 } })],
    ['tocar 100 compassos', com({ silencio: { ativo: true, tocar: 100, silenciar: 1 } })],
    ['volume acima de 1', com({ volume: 1.1 })],
    ['contagem de 3 compassos', com({ contagemEntrada: 3 })],
  ])('recusa %s com o campo no erro', (_, config) => {
    expect(() => validarConfig(config)).toThrow(RangeError)
  })
})

describe('limitarBpm', () => {
  it('arredonda e prende entre 30 e 244, como as setas do Musicca', () => {
    expect([limitarBpm(29), limitarBpm(245), limitarBpm(120.6)]).toEqual([30, 244, 121])
  })
})
