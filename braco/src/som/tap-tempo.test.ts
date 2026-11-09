import { describe, expect, it } from 'vitest'
import { TapTempo } from './tap-tempo'

describe('TapTempo', () => {
  it('um toque só não dá andamento', () => {
    expect(new TapTempo().tocar(0)).toBeNull()
  })

  it('média dos intervalos: toques a cada 500 ms dão 120 BPM', () => {
    const tap = new TapTempo()
    const resultados = [0, 500, 1000, 1500].map((ms) => tap.tocar(ms))
    expect(resultados).toEqual([null, 120, 120, 120])
  })

  it('irregular: 400 e 600 ms dão a média, 120 BPM', () => {
    const tap = new TapTempo()
    tap.tocar(0)
    tap.tocar(400)
    expect(tap.tocar(1000)).toBe(120)
  })

  it('mais de 3 s sem toque recomeça a contagem', () => {
    const tap = new TapTempo()
    tap.tocar(0)
    tap.tocar(500)
    expect(tap.tocar(3600)).toBeNull()
    expect(tap.tocar(4600)).toBe(60)
  })

  it('fica entre 30 e 244 BPM', () => {
    const tap = new TapTempo()
    tap.tocar(0)
    expect(tap.tocar(100)).toBe(244)
  })
})
