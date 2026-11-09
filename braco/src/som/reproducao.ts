/**
 * Notas tocadas junto do metrônomo (ADR-057).
 *
 * M8: clicar numa nota com o metrônomo parado soa na hora; rodando, soa na hora também,
 * a menos que o usuário ligue "quantizar" — aí espera o próximo instante da grade.
 *
 * S6: a sequência é agendada no relógio de áudio junto com os cliques (`aoAgendar`, ~100 ms
 * antes de soar), não no aviso visual, que chega até um tique atrasado.
 */
import type { Altura } from '@/dominio/tipos'
import type { Metronomo, Pulso, Sintetizador } from './tipos'

export function momentoDaNota(agora: number, metronomo: Pick<Metronomo, 'proximoDaGrade'>, quantizar: boolean): number {
  if (!quantizar) return agora
  return metronomo.proximoDaGrade(agora) ?? agora
}

export class SequenciaNoMetronomo {
  private alturas: readonly Altura[] = []
  private duracao = 0
  private proxima = 0
  private cancelar: (() => void) | null = null
  /** Qual nota cada pulso tocou, para o visual acender a posição certa quando o pulso soar. */
  private indices = new WeakMap<Pulso, number>()

  constructor(
    private readonly metronomo: Pick<Metronomo, 'aoAgendar'>,
    private readonly sintetizador: Pick<Sintetizador, 'nota'>,
  ) {}

  get ativa(): boolean {
    return this.cancelar !== null
  }

  iniciar(alturas: readonly Altura[], duracao: number): void {
    if (alturas.length === 0) throw new RangeError('sequência vazia: escolha ao menos uma nota')
    this.parar()
    this.alturas = alturas
    this.duracao = duracao
    this.proxima = 0
    this.indices = new WeakMap()
    this.cancelar = this.metronomo.aoAgendar((pulso) => this.agendar(pulso))
  }

  parar(): void {
    this.cancelar?.()
    this.cancelar = null
  }

  indiceDoPulso(pulso: Pulso): number | null {
    return this.indices.get(pulso) ?? null
  }

  private agendar(pulso: Pulso): void {
    // A contagem de entrada é só para preparar; o silêncio é exercício, então a nota segue.
    if (pulso.contagem) return
    const indice = this.proxima
    const altura = this.alturas[indice]
    if (altura === undefined) return
    this.sintetizador.nota(altura, pulso.tempo, this.duracao)
    this.indices.set(pulso, indice)
    this.proxima = (indice + 1) % this.alturas.length
  }
}
