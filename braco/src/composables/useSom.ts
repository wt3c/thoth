import { obterMotor } from '@/composables/motor'
import type { Altura } from '@/dominio/tipos'
import { momentoDaNota } from '@/som/reproducao'

export function useSom() {
  /**
   * M8: parado, a nota soa na hora; rodando, também — a menos que `quantizar` esteja ligado,
   * e aí ela espera o próximo instante da grade do metrônomo.
   */
  async function tocarNota(altura: Altura, quantizar = false, duracao = 1.2): Promise<void> {
    const { relogio, metronomo, sintetizador } = await obterMotor()
    sintetizador.nota(altura, momentoDaNota(relogio.agora(), metronomo, quantizar), duracao)
  }
  return { tocarNota }
}
