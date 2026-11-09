// @vitest-environment node
import { OfflineAudioContext } from 'node-web-audio-api'
import { describe, expect, it } from 'vitest'
import { SintetizadorWebAudio } from './sintetizador-web-audio'

const TAXA = 48000

/** Instantes (s) em que o sinal sai de pelo menos `respiro` segundos de silêncio. */
function ataques(dados: Float32Array, respiro = 0.05): number[] {
  const encontrados: number[] = []
  let ultimoAudivel = -Infinity
  for (let i = 0; i < dados.length; i++) {
    const t = i / TAXA
    if (Math.abs(dados[i] ?? 0) <= 1e-3) continue
    if (t - ultimoAudivel > respiro) encontrados.push(t)
    ultimoAudivel = t
  }
  return encontrados
}

describe('SintetizadorWebAudio contra Web Audio real (offline)', () => {
  it('a nota e o clique soam no instante agendado, com ±1 ms', async () => {
    const ctx = new OfflineAudioContext(1, TAXA * 2, TAXA)
    const sint = new SintetizadorWebAudio(ctx as unknown as BaseAudioContext)

    sint.nota(40, 0.25, 0.2)
    sint.clique(1.0, { acento: true, sub: false, volume: 1, som: 'eletronico' })
    const medidos = ataques((await ctx.startRendering()).getChannelData(0))

    console.log('ataques medidos (s):', medidos.map((t) => t.toFixed(5)))
    expect(medidos).toHaveLength(2)
    expect(Math.abs((medidos[0] ?? 0) - 0.25)).toBeLessThanOrEqual(0.001)
    expect(Math.abs((medidos[1] ?? 0) - 1.0)).toBeLessThanOrEqual(0.001)
  })

  it('silenciar cancela o que ainda não soou', async () => {
    const ctx = new OfflineAudioContext(1, TAXA, TAXA)
    const sint = new SintetizadorWebAudio(ctx as unknown as BaseAudioContext)

    sint.nota(40, 0.5, 0.2)
    sint.silenciar()

    expect(ataques((await ctx.startRendering()).getChannelData(0))).toEqual([])
  })
})
