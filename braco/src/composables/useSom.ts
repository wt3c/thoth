import { audio } from '@/som/contexto'
import { SintetizadorWebAudio } from '@/som/sintetizador-web-audio'
import type { Altura } from '@/dominio/tipos'

/** Fora de `ref`/`reactive` de propósito (ADR-057): o Vue não deve envolver nós de áudio em proxy. */
let sintetizador: SintetizadorWebAudio | null = null

export function useSom() {
  /** Chamado dentro do gesto: o primeiro clique também desbloqueia o áudio. */
  async function tocarNota(altura: Altura, duracao = 1.2): Promise<void> {
    const ctx = await audio.desbloquear()
    sintetizador ??= new SintetizadorWebAudio(ctx)
    sintetizador.nota(altura, ctx.currentTime, duracao)
  }
  return { tocarNota }
}
