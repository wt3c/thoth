// @vitest-environment node
import { OfflineAudioContext } from 'node-web-audio-api'
import { describe, expect, it } from 'vitest'
import { CONFIG_PADRAO } from './agendador'
import { MetronomoAgendado } from './metronomo'
import { SintetizadorWebAudio } from './sintetizador-web-audio'

const TAXA = 48000

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

describe('metrônomo agendado contra Web Audio real (offline)', () => {
  it('a 120 BPM, com o compasso 1 silenciado, soam os tempos esperados a ±1 ms', async () => {
    const ctx = new OfflineAudioContext(1, TAXA * 2.5, TAXA)
    // O agendador não roda durante a renderização offline: uma janela de 2,5 s agenda tudo no iniciar.
    const metro = new MetronomoAgendado({
      relogio: { agora: () => ctx.currentTime },
      despertador: { iniciar() {}, parar() {} },
      sintetizador: new SintetizadorWebAudio(ctx as unknown as BaseAudioContext),
      janela: 2.5,
    })
    metro.configurar({
      ...CONFIG_PADRAO,
      bpm: 120,
      temposPorCompasso: 2,
      contagemEntrada: 0,
      silencio: { ativo: true, tocar: 1, silenciar: 1 },
    })
    metro.iniciar()

    const medidos = ataques((await ctx.startRendering()).getChannelData(0))
    console.log('ataques do metrônomo (s):', medidos.map((t) => t.toFixed(5)))

    // Compasso de 1 s: o 0 soa (0,05 e 0,55), o 1 cala (1,05 e 1,55), o 2 volta (2,05).
    const esperados = [0.05, 0.55, 2.05]
    expect(medidos).toHaveLength(esperados.length)
    medidos.forEach((t, i) => expect(Math.abs(t - (esperados[i] ?? 0))).toBeLessThanOrEqual(0.001))
  })
})
