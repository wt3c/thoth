import { limitarBpm } from './config-metronomo'

/** Depois disso sem toque, o próximo começa uma contagem nova (Musicca: 3 s). */
const ESQUECER_MS = 3000

/** "Marcar tempo": o andamento é a média de todos os intervalos desde o primeiro toque. */
export class TapTempo {
  private toques: number[] = []

  /** `agoraMs` vem de `performance.now()` — aqui é medição do gesto, não fonte de tempo de som. */
  tocar(agoraMs: number): number | null {
    const ultimo = this.toques.at(-1)
    if (ultimo !== undefined && agoraMs - ultimo > ESQUECER_MS) this.toques = []
    this.toques.push(agoraMs)
    const primeiro = this.toques[0]
    if (this.toques.length < 2 || primeiro === undefined) return null
    const mediaMs = (agoraMs - primeiro) / (this.toques.length - 1)
    return limitarBpm(60000 / mediaMs)
  }
}
