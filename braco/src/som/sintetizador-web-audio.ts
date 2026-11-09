import { frequencia } from '@/dominio/frequencia'
import type { Altura } from '@/dominio/tipos'
import type { OpcoesDoClique, Sintetizador, SomDoClique } from './tipos'

/** Forma de onda, frequências (tempo forte, tempo, subdivisão) e duração de cada som do clique. */
const CLIQUES: Record<SomDoClique, { tipo: OscillatorType; hz: readonly [number, number, number]; dur: number }> = {
  eletronico: { tipo: 'square', hz: [1760, 1320, 990], dur: 0.03 },
  madeira: { tipo: 'triangle', hz: [1200, 900, 700], dur: 0.05 },
  bipe: { tipo: 'sine', hz: [1000, 800, 600], dur: 0.06 },
}

const ATAQUE_S = 0.003

/**
 * Oscilador com envelope, agendado no relógio do contexto (ADR-057). Recebe o contexto
 * pronto: quem cria e retoma o `AudioContext` no gesto do usuário é `contexto.ts`.
 * Nunca entra em estado reativo do Vue.
 */
export class SintetizadorWebAudio implements Sintetizador {
  private readonly agendados = new Set<AudioScheduledSourceNode>()
  private readonly saida: GainNode

  constructor(private readonly ctx: BaseAudioContext) {
    this.saida = ctx.createGain()
    this.saida.gain.value = 0.8
    this.saida.connect(ctx.destination)
  }

  nota(altura: Altura, tempo: number, duracao: number): void {
    const hz = frequencia(altura)
    const osc = this.ctx.createOscillator()
    osc.type = 'triangle'
    osc.frequency.value = hz
    const filtro = this.ctx.createBiquadFilter()
    filtro.type = 'lowpass'
    filtro.frequency.value = Math.min(4000, hz * 8)
    osc.connect(filtro).connect(this.envelope(tempo, duracao, 0.6))
    this.tocar(osc, tempo, duracao)
  }

  clique(tempo: number, opcoes: OpcoesDoClique): void {
    const som = CLIQUES[opcoes.som]
    const osc = this.ctx.createOscillator()
    osc.type = som.tipo
    osc.frequency.value = opcoes.acento ? som.hz[0] : opcoes.sub ? som.hz[2] : som.hz[1]
    const pico = opcoes.volume * (opcoes.acento ? 1 : opcoes.sub ? 0.4 : 0.7)
    osc.connect(this.envelope(tempo, som.dur, pico))
    this.tocar(osc, tempo, som.dur)
  }

  silenciar(): void {
    for (const fonte of this.agendados) {
      fonte.onended = null
      fonte.stop(0)
      fonte.disconnect()
    }
    this.agendados.clear()
  }

  /** Ataque de 3 ms e queda exponencial: sem estalo no início nem no fim. */
  private envelope(tempo: number, duracao: number, pico: number): GainNode {
    const ganho = this.ctx.createGain()
    ganho.gain.setValueAtTime(0, tempo)
    if (pico > 0) {
      ganho.gain.linearRampToValueAtTime(pico, tempo + ATAQUE_S)
      ganho.gain.exponentialRampToValueAtTime(0.0001, tempo + duracao)
    }
    ganho.connect(this.saida)
    return ganho
  }

  private tocar(fonte: AudioScheduledSourceNode, tempo: number, duracao: number): void {
    this.agendados.add(fonte)
    fonte.onended = () => this.agendados.delete(fonte)
    fonte.start(tempo)
    fonte.stop(tempo + duracao + 0.01)
  }
}
