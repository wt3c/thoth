import { afterEach, describe, expect, it, vi } from 'vitest'
import { DespertadorWorker, instalarTiquetaque, type MensagemDoDespertador, type PortaDoWorker } from './despertador-worker'

class WorkerFalso implements PortaDoWorker {
  enviadas: MensagemDoDespertador[] = []
  onmessage: ((evento: MessageEvent) => void) | null = null
  postMessage(mensagem: MensagemDoDespertador) {
    this.enviadas.push(mensagem)
  }
  tique() {
    this.onmessage?.({ data: 'tique' } as MessageEvent)
  }
}

describe('DespertadorWorker', () => {
  it('só cria o Worker no primeiro iniciar e pede o intervalo', () => {
    const worker = new WorkerFalso()
    const fabrica = vi.fn(() => worker)
    const despertador = new DespertadorWorker(fabrica)
    expect(fabrica).not.toHaveBeenCalled()
    despertador.iniciar(() => {}, 25)
    expect(worker.enviadas).toEqual([{ tipo: 'iniciar', intervaloMs: 25 }])
  })

  it('cada tique do Worker acorda quem iniciou', () => {
    const worker = new WorkerFalso()
    const aoTique = vi.fn()
    new DespertadorWorker(() => worker).iniciar(aoTique, 25)
    worker.tique()
    worker.tique()
    expect(aoTique).toHaveBeenCalledTimes(2)
  })

  it('tique atrasado que chega depois do parar é ignorado', () => {
    const worker = new WorkerFalso()
    const aoTique = vi.fn()
    const despertador = new DespertadorWorker(() => worker)
    despertador.iniciar(aoTique, 25)
    despertador.parar()
    worker.tique()
    expect(aoTique).not.toHaveBeenCalled()
    expect(worker.enviadas.at(-1)).toEqual({ tipo: 'parar' })
  })
})

describe('instalarTiquetaque (o lado de dentro do Worker)', () => {
  afterEach(() => vi.useRealTimers())

  it('posta "tique" no intervalo pedido até receber parar', () => {
    vi.useFakeTimers()
    const postadas: unknown[] = []
    const escopo = { onmessage: null as ((e: MessageEvent<MensagemDoDespertador>) => void) | null, postMessage: (m: unknown) => postadas.push(m) }
    instalarTiquetaque(escopo)
    escopo.onmessage?.({ data: { tipo: 'iniciar', intervaloMs: 25 } } as MessageEvent<MensagemDoDespertador>)
    vi.advanceTimersByTime(100)
    expect(postadas).toHaveLength(4)
    escopo.onmessage?.({ data: { tipo: 'parar' } } as MessageEvent<MensagemDoDespertador>)
    vi.advanceTimersByTime(100)
    expect(postadas).toHaveLength(4)
  })

  it('iniciar de novo não acumula dois intervalos', () => {
    vi.useFakeTimers()
    const postadas: unknown[] = []
    const escopo = { onmessage: null as ((e: MessageEvent<MensagemDoDespertador>) => void) | null, postMessage: (m: unknown) => postadas.push(m) }
    instalarTiquetaque(escopo)
    escopo.onmessage?.({ data: { tipo: 'iniciar', intervaloMs: 25 } } as MessageEvent<MensagemDoDespertador>)
    escopo.onmessage?.({ data: { tipo: 'iniciar', intervaloMs: 25 } } as MessageEvent<MensagemDoDespertador>)
    vi.advanceTimersByTime(100)
    expect(postadas).toHaveLength(4)
  })
})
