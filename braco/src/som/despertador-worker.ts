/**
 * O despertador do metrônomo num Web Worker (ADR-057). Em aba de segundo plano, o navegador
 * estrangula os timers da thread principal; os do Worker sofrem bem menos. O `setInterval`
 * aqui só ACORDA o agendador — nenhum instante de som sai dele.
 */
import type { Despertador } from './tipos'

export type MensagemDoDespertador = { readonly tipo: 'iniciar'; readonly intervaloMs: number } | { readonly tipo: 'parar' }

/** O pedaço de `Worker` que o despertador usa; nos testes, um falso. */
export interface PortaDoWorker {
  onmessage: ((evento: MessageEvent) => void) | null
  postMessage(mensagem: MensagemDoDespertador): void
}

export class DespertadorWorker implements Despertador {
  private worker: PortaDoWorker | null = null
  private aoTique: (() => void) | null = null

  constructor(private readonly fabrica: () => PortaDoWorker) {}

  iniciar(aoTique: () => void, intervaloMs: number): void {
    this.aoTique = aoTique
    if (!this.worker) {
      this.worker = this.fabrica()
      // Tique que já estava na fila quando `parar` foi chamado chega com `aoTique` nulo e morre aqui.
      this.worker.onmessage = () => this.aoTique?.()
    }
    this.worker.postMessage({ tipo: 'iniciar', intervaloMs })
  }

  parar(): void {
    this.aoTique = null
    this.worker?.postMessage({ tipo: 'parar' })
  }
}

interface EscopoDoWorker {
  onmessage: ((evento: MessageEvent<MensagemDoDespertador>) => void) | null
  postMessage(mensagem: unknown): void
}

/** O lado de dentro do Worker: separado do arquivo `.worker.ts` para ser testável. */
export function instalarTiquetaque(escopo: EscopoDoWorker): void {
  let id: ReturnType<typeof setInterval> | null = null
  const parar = () => {
    if (id !== null) clearInterval(id)
    id = null
  }
  escopo.onmessage = ({ data }) => {
    parar()
    if (data.tipo === 'iniciar') id = setInterval(() => escopo.postMessage('tique'), data.intervaloMs)
  }
}

/** O despertador da aplicação. */
export function criarDespertador(): Despertador {
  return new DespertadorWorker(() => new Worker(new URL('./tique.worker.ts', import.meta.url), { type: 'module' }))
}
