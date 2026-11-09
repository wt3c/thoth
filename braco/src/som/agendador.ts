/**
 * Agendador puro do metrônomo (ADR-057): dado o estado e um horizonte no relógio de áudio,
 * devolve os pulsos até lá e o estado para continuar. Sem relógio, sem timer, sem Web Audio —
 * quem decide a janela (agora + 100 ms) e quando trocar a configuração é o `Metronomo`.
 */
import type { ConfigMetronomo, Pulso } from './tipos'

export const CONFIG_PADRAO: ConfigMetronomo = {
  bpm: 100,
  temposPorCompasso: 4,
  subdivisao: 1,
  acentoNoUm: true,
  silencio: { ativo: false, tocar: 1, silenciar: 1 },
  volume: 0.8,
  som: 'eletronico',
  contagemEntrada: 0,
}

export interface EstadoDoAgendador {
  /**
   * O tempo do pulso `n` é `origem + n × duracao`: multiplicar em vez de somar evita que o
   * erro de ponto flutuante se acumule ao longo de minutos. Mudar o andamento refaz a origem.
   */
  readonly origem: number
  readonly n: number
  readonly duracao: number
  readonly compasso: number
  readonly batida: number
  readonly sub: number
}

const duracaoDoPulso = (c: ConfigMetronomo) => 60 / c.bpm / c.subdivisao

export function estadoInicial(config: ConfigMetronomo, inicio: number): EstadoDoAgendador {
  return { origem: inicio, n: 0, duracao: duracaoDoPulso(config), compasso: 0 - config.contagemEntrada, batida: 1, sub: 0 }
}

/** Instante do próximo pulso ainda não gerado. */
export const proximoTempo = (estado: EstadoDoAgendador) => estado.origem + estado.n * estado.duracao

function silenciado(c: ConfigMetronomo, compasso: number): boolean {
  if (!c.silencio.ativo || compasso < 0) return false
  return compasso % (c.silencio.tocar + c.silencio.silenciar) >= c.silencio.tocar
}

function avancar(c: ConfigMetronomo, e: EstadoDoAgendador): EstadoDoAgendador {
  let { compasso, batida, sub } = e
  sub += 1
  if (sub >= c.subdivisao) {
    sub = 0
    batida += 1
    if (batida > c.temposPorCompasso) {
      batida = 1
      compasso += 1
    }
  }
  return { ...e, n: e.n + 1, compasso, batida, sub }
}

/** O pulso seguinte sob `config`. Trocar de andamento entre dois pulsos não pula nem repete nenhum. */
export function proximoPulso(config: ConfigMetronomo, estado: EstadoDoAgendador): { pulso: Pulso; estado: EstadoDoAgendador } {
  const duracao = duracaoDoPulso(config)
  const e = estado.duracao === duracao ? estado : { ...estado, origem: proximoTempo(estado), n: 0, duracao }
  return {
    pulso: {
      tempo: proximoTempo(e),
      compasso: e.compasso,
      batida: e.batida,
      sub: e.sub,
      acento: config.acentoNoUm && e.batida === 1 && e.sub === 0,
      silenciado: silenciado(config, e.compasso),
      contagem: e.compasso < 0,
    },
    estado: avancar(config, e),
  }
}

/** Todos os pulsos com instante `< ate`, a partir de `estado`, sob `config`. */
export function pulsosAte(
  config: ConfigMetronomo,
  estado: EstadoDoAgendador,
  ate: number,
): { pulsos: Pulso[]; estado: EstadoDoAgendador } {
  const pulsos: Pulso[] = []
  let e = estado
  while (proximoTempo(e) < ate) {
    const passo = proximoPulso(config, e)
    pulsos.push(passo.pulso)
    e = passo.estado
  }
  return { pulsos, estado: e }
}
