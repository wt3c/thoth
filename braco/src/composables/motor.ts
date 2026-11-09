/**
 * O motor de som da página: um contexto, um sintetizador, um metrônomo e uma sequência,
 * criados no primeiro gesto do usuário (política de autoplay) e nunca dentro de `ref`/`reactive`
 * (ADR-057): o Vue envolveria os nós de áudio em proxy.
 */
import { audio } from '@/som/contexto'
import { criarDespertador } from '@/som/despertador-worker'
import { MetronomoAgendado } from '@/som/metronomo'
import { SequenciaNoMetronomo } from '@/som/reproducao'
import { SintetizadorWebAudio } from '@/som/sintetizador-web-audio'
import type { Metronomo, Relogio, Sintetizador } from '@/som/tipos'

export interface Motor {
  readonly relogio: Relogio
  readonly sintetizador: Sintetizador
  readonly metronomo: Metronomo
  readonly sequencia: SequenciaNoMetronomo
}

let motor: Motor | null = null

/** Chamar dentro do gesto: o primeiro clique também desbloqueia o áudio. */
export async function obterMotor(): Promise<Motor> {
  const ctx = await audio.desbloquear()
  if (motor) return motor
  const relogio: Relogio = { agora: () => ctx.currentTime }
  const sintetizador = new SintetizadorWebAudio(ctx)
  const metronomo = new MetronomoAgendado({ relogio, despertador: criarDespertador(), sintetizador })
  motor = { relogio, sintetizador, metronomo, sequencia: new SequenciaNoMetronomo(metronomo, sintetizador) }
  return motor
}
