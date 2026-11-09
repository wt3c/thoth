import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MetronomoAgendado } from '@/som/metronomo'
import { SequenciaNoMetronomo } from '@/som/reproducao'
import type { Despertador, OpcoesDoClique, Sintetizador } from '@/som/tipos'
import { useMetronomoStore } from './metronomo'

/** Só a fronteira de áudio é falsa: o metrônomo e a sequência são os de verdade (ADR-057). */
const falso = vi.hoisted(() => ({ motor: null as unknown }))
vi.mock('@/composables/motor', () => ({ obterMotor: () => Promise.resolve(falso.motor) }))

class Relogio {
  t = 10
  agora() {
    return this.t
  }
}
class Despertador1 implements Despertador {
  aoTique: (() => void) | null = null
  iniciar(cb: () => void) {
    this.aoTique = cb
  }
  parar() {
    this.aoTique = null
  }
}
class Gravador implements Sintetizador {
  cliques: { tempo: number; opcoes: OpcoesDoClique }[] = []
  notas: { altura: number; tempo: number; duracao: number }[] = []
  clique(tempo: number, opcoes: OpcoesDoClique) {
    this.cliques.push({ tempo, opcoes })
  }
  nota(altura: number, tempo: number, duracao: number) {
    this.notas.push({ altura, tempo, duracao })
  }
  silenciar() {}
}

function montarMotor() {
  const relogio = new Relogio()
  const despertador = new Despertador1()
  const sintetizador = new Gravador()
  const metronomo = new MetronomoAgendado({ relogio, despertador, sintetizador })
  const sequencia = new SequenciaNoMetronomo(metronomo, sintetizador)
  falso.motor = { relogio, sintetizador, metronomo, sequencia }
  const andar = (s: number) => {
    for (let i = 0; i < Math.round(s / 0.025); i++) {
      relogio.t += 0.025
      despertador.aoTique?.()
    }
  }
  return { relogio, sintetizador, metronomo, andar }
}

describe('useMetronomoStore', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('alternar liga com a configuração do store e desliga', async () => {
    const { sintetizador, andar } = montarMotor()
    const metro = useMetronomoStore()
    await metro.atualizar({ bpm: 120, som: 'madeira' })
    await metro.alternar()
    expect(metro.tocando).toBe(true)
    andar(0.6)
    expect(sintetizador.cliques.map((c) => c.opcoes.som)).toEqual(['madeira', 'madeira'])
    await metro.alternar()
    expect(metro.tocando).toBe(false)
  })

  it('o indicador visual acompanha o pulso que soou (M7)', async () => {
    const { andar } = montarMotor()
    const metro = useMetronomoStore()
    await metro.atualizar({ bpm: 120 })
    await metro.alternar()
    andar(0.6)
    expect(metro.pulso).toMatchObject({ batida: 2, compasso: 0 })
  })

  it('configuração inválida é recusada e o store não muda', async () => {
    montarMotor()
    const metro = useMetronomoStore()
    await expect(metro.atualizar({ bpm: 500 })).rejects.toThrow(RangeError)
    expect(metro.config.bpm).toBe(100)
  })

  it('tap tempo ajusta o andamento', async () => {
    montarMotor()
    const metro = useMetronomoStore()
    await metro.tap(0)
    await metro.tap(500)
    await metro.tap(1000)
    expect(metro.config.bpm).toBe(120)
  })

  it('S6: a sequência toca nos pulsos e o visual diz qual altura está soando', async () => {
    const { sintetizador, andar } = montarMotor()
    const metro = useMetronomoStore()
    await metro.atualizar({ bpm: 120, subdivisao: 2 })
    await metro.tocarSequencia([40, 43])
    expect(metro.tocando).toBe(true)
    andar(0.325)
    expect(sintetizador.notas.map((n) => n.altura)).toEqual([40, 43])
    expect(sintetizador.notas[0]?.duracao).toBeCloseTo(0.225, 6)
    expect(metro.soando).toBe(43)
    metro.pararSequencia()
    expect(metro.sequenciaAtiva).toBe(false)
    expect(metro.soando).toBeNull()
  })

  it('parar o metrônomo para a sequência', async () => {
    montarMotor()
    const metro = useMetronomoStore()
    await metro.tocarSequencia([40])
    await metro.alternar()
    expect(metro.sequenciaAtiva).toBe(false)
  })
})
