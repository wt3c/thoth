/**
 * Metrônomo por agendamento antecipado (ADR-057): a cada tique do despertador, agenda no
 * relógio de áudio os pulsos dos próximos `janela` segundos. O despertador só acorda;
 * o tempo de cada som vem sempre do `Relogio`.
 */
import { CONFIG_PADRAO, estadoInicial, proximoPulso, proximoTempo, type EstadoDoAgendador } from './agendador'
import { validarConfig } from './config-metronomo'
import type { ConfigMetronomo, Despertador, Metronomo, Pulso, Relogio, Sintetizador } from './tipos'

export interface DependenciasDoMetronomo {
  readonly relogio: Relogio
  readonly despertador: Despertador
  readonly sintetizador: Sintetizador
  /** Quanto à frente agendar, em segundos. */
  readonly janela?: number
  readonly intervaloMs?: number
  /** Folga entre o `iniciar` e o primeiro tempo, para o primeiro clique não chegar atrasado. */
  readonly atrasoInicial?: number
}

export class MetronomoAgendado implements Metronomo {
  private config: ConfigMetronomo = CONFIG_PADRAO
  private pendente: ConfigMetronomo | null = null
  private estado: EstadoDoAgendador | null = null
  /** Agendados que ainda não soaram: o indicador visual os anuncia quando o relógio os alcança. */
  private fila: Pulso[] = []
  private readonly ouvintes = new Set<(pulso: Pulso) => void>()
  private readonly agendadores = new Set<(pulso: Pulso) => void>()
  private readonly janela: number
  private readonly intervaloMs: number
  private readonly atrasoInicial: number

  constructor(private readonly deps: DependenciasDoMetronomo) {
    this.janela = deps.janela ?? 0.1
    this.intervaloMs = deps.intervaloMs ?? 25
    this.atrasoInicial = deps.atrasoInicial ?? 0.05
  }

  get tocando(): boolean {
    return this.estado !== null
  }

  iniciar(): void {
    if (this.estado) return
    if (this.pendente) {
      this.config = this.pendente
      this.pendente = null
    }
    this.estado = estadoInicial(this.config, this.deps.relogio.agora() + this.atrasoInicial)
    this.deps.despertador.iniciar(() => this.tique(), this.intervaloMs)
    this.tique()
  }

  parar(): void {
    if (!this.estado) return
    this.deps.despertador.parar()
    this.deps.sintetizador.silenciar()
    this.estado = null
    this.fila = []
  }

  configurar(config: ConfigMetronomo): void {
    validarConfig(config)
    if (this.estado) this.pendente = config
    else this.config = config
  }

  aoPulso(cb: (pulso: Pulso) => void): () => void {
    this.ouvintes.add(cb)
    return () => this.ouvintes.delete(cb)
  }

  aoAgendar(cb: (pulso: Pulso) => void): () => void {
    this.agendadores.add(cb)
    return () => this.agendadores.delete(cb)
  }

  proximoDaGrade(agora: number): number | null {
    if (!this.estado) return null
    const naFila = this.fila.find((p) => p.tempo >= agora)
    if (naFila) return naFila.tempo
    let e = this.estado
    while (proximoTempo(e) < agora) e = proximoPulso(this.config, e).estado
    return proximoTempo(e)
  }

  private tique(): void {
    const agora = this.deps.relogio.agora()
    this.anunciar(agora)
    this.agendar(agora + this.janela)
  }

  private anunciar(agora: number): void {
    while (this.fila.length > 0 && (this.fila[0]?.tempo ?? Infinity) <= agora) {
      const pulso = this.fila.shift()
      if (pulso) for (const cb of this.ouvintes) cb(pulso)
    }
  }

  private agendar(ate: number): void {
    let e = this.estado
    if (!e) return
    while (proximoTempo(e) < ate) {
      // A configuração nova entra só no começo de um tempo (ADR-057).
      if (this.pendente && e.sub === 0) {
        this.config = this.pendente
        this.pendente = null
      }
      const passo = proximoPulso(this.config, e)
      const { pulso } = passo
      if (!pulso.silenciado) {
        this.deps.sintetizador.clique(pulso.tempo, {
          acento: pulso.acento,
          sub: pulso.sub > 0,
          volume: this.config.volume,
          som: this.config.som,
        })
      }
      for (const cb of this.agendadores) cb(pulso)
      this.fila.push(pulso)
      e = passo.estado
    }
    this.estado = e
  }
}
