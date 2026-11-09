import { describe, expect, it } from 'vitest'
import { CONFIG_PADRAO, estadoInicial, pulsosAte } from './agendador'
import type { ConfigMetronomo, Pulso } from './tipos'

function config(parcial: Partial<ConfigMetronomo> = {}): ConfigMetronomo {
  return { ...CONFIG_PADRAO, ...parcial }
}

/** Os pulsos de `[inicio, ate)` com a mesma configuração do começo ao fim. */
function gerar(c: ConfigMetronomo, ate: number, inicio = 0): Pulso[] {
  return pulsosAte(c, estadoInicial(c, inicio), ate).pulsos
}

describe('agendador', () => {
  it('padrão do Musicca: 100 BPM, 4 tempos, acento no 1', () => {
    expect(CONFIG_PADRAO).toMatchObject({ bpm: 100, temposPorCompasso: 4, subdivisao: 1, acentoNoUm: true })
  })

  it('a 120 BPM os tempos caem a cada 0,5 s, exatamente', () => {
    const pulsos = gerar(config({ bpm: 120, contagemEntrada: 0 }), 3.01, 1)
    expect(pulsos.map((p) => p.tempo)).toEqual([1, 1.5, 2, 2.5, 3])
  })

  it('numera compasso e batida e acentua só o 1', () => {
    const pulsos = gerar(config({ bpm: 60, temposPorCompasso: 3, contagemEntrada: 0 }), 4)
    expect(pulsos.map((p) => [p.compasso, p.batida, p.acento])).toEqual([
      [0, 1, true],
      [0, 2, false],
      [0, 3, false],
      [1, 1, true],
    ])
  })

  it('sem acento no 1, nenhum pulso é acentuado', () => {
    expect(gerar(config({ bpm: 60, acentoNoUm: false, contagemEntrada: 0 }), 4).some((p) => p.acento)).toBe(false)
  })

  it('subdivisão em tercina põe três pulsos por tempo, o primeiro como tempo', () => {
    const pulsos = gerar(config({ bpm: 60, subdivisao: 3, contagemEntrada: 0 }), 1.99)
    expect(pulsos.map((p) => [p.batida, p.sub])).toEqual([
      [1, 0],
      [1, 1],
      [1, 2],
      [2, 0],
      [2, 1],
      [2, 2],
    ])
    expect(pulsos[1]?.tempo).toBeCloseTo(1 / 3, 12)
  })

  it('a contagem de entrada vem antes do compasso 0, com compasso negativo', () => {
    const pulsos = gerar(config({ bpm: 60, temposPorCompasso: 2, contagemEntrada: 1 }), 3.5)
    expect(pulsos.map((p) => [p.compasso, p.batida, p.contagem])).toEqual([
      [-1, 1, true],
      [-1, 2, true],
      [0, 1, false],
      [0, 2, false],
    ])
  })

  it('tocar 1 e silenciar 1: compassos ímpares silenciados, a contagem nunca', () => {
    const c = config({ bpm: 60, temposPorCompasso: 1, contagemEntrada: 1, silencio: { ativo: true, tocar: 1, silenciar: 1 } })
    expect(gerar(c, 5).map((p) => [p.compasso, p.silenciado])).toEqual([
      [-1, false],
      [0, false],
      [1, true],
      [2, false],
      [3, true],
    ])
  })

  it('tocar 2 e silenciar 3 repete a cada 5 compassos', () => {
    const c = config({ bpm: 60, temposPorCompasso: 1, contagemEntrada: 0, silencio: { ativo: true, tocar: 2, silenciar: 3 } })
    expect(gerar(c, 10).map((p) => p.silenciado)).toEqual([false, false, true, true, true, false, false, true, true, true])
  })

  it('continua de onde parou: duas janelas dão os mesmos pulsos que uma', () => {
    const c = config({ bpm: 137, subdivisao: 4, contagemEntrada: 1 })
    const primeira = pulsosAte(c, estadoInicial(c, 0.2), 1.3)
    const segunda = pulsosAte(c, primeira.estado, 4)
    expect([...primeira.pulsos, ...segunda.pulsos]).toEqual(gerar(c, 4, 0.2))
  })

  it('nova configuração vale a partir do pulso pedido, sem pular nem repetir', () => {
    const lento = config({ bpm: 60, contagemEntrada: 0 })
    const rapido = config({ bpm: 120, contagemEntrada: 0 })
    const antes = pulsosAte(lento, estadoInicial(lento, 0), 1.5)
    const depois = pulsosAte(rapido, antes.estado, 3)
    expect([...antes.pulsos, ...depois.pulsos].map((p) => p.tempo)).toEqual([0, 1, 2, 2.5])
  })
})
