import { describe, expect, it } from 'vitest'
import { CONFIG_PADRAO } from './agendador'
import { MetronomoAgendado } from './metronomo'
import type { ConfigMetronomo, Despertador, OpcoesDoClique, Pulso, Sintetizador } from './tipos'

class RelogioFalso {
  t = 10
  agora() {
    return this.t
  }
}

class DespertadorFalso implements Despertador {
  aoTique: (() => void) | null = null
  inicios = 0
  iniciar(aoTique: () => void) {
    this.inicios += 1
    this.aoTique = aoTique
  }
  parar() {
    this.aoTique = null
  }
  tique() {
    this.aoTique?.()
  }
}

class Gravador implements Sintetizador {
  cliques: { tempo: number; opcoes: OpcoesDoClique }[] = []
  silencios = 0
  clique(tempo: number, opcoes: OpcoesDoClique) {
    this.cliques.push({ tempo, opcoes })
  }
  nota() {}
  silenciar() {
    this.silencios += 1
  }
}

function montar(parcial: Partial<ConfigMetronomo> = {}) {
  const relogio = new RelogioFalso()
  const despertador = new DespertadorFalso()
  const sint = new Gravador()
  const metro = new MetronomoAgendado({ relogio, despertador, sintetizador: sint })
  metro.configurar({ ...CONFIG_PADRAO, bpm: 120, contagemEntrada: 0, ...parcial })
  /** Avança o relógio em passos de 25 ms, tiquetaqueando como o Worker. */
  const andar = (segundos: number) => {
    for (let i = 0; i < Math.round(segundos / 0.025); i++) {
      relogio.t += 0.025
      despertador.tique()
    }
  }
  return { relogio, despertador, sint, metro, andar }
}

const tempos = (sint: Gravador) => sint.cliques.map((c) => Number(c.tempo.toFixed(6)))

describe('MetronomoAgendado', () => {
  it('o primeiro tempo soa 50 ms depois do iniciar, acentuado', () => {
    const { sint, metro } = montar()
    metro.iniciar()
    expect(sint.cliques[0]?.tempo).toBeCloseTo(10.05, 12)
    expect(sint.cliques[0]?.opcoes).toMatchObject({ acento: true, sub: false, volume: CONFIG_PADRAO.volume })
  })

  it('agenda só até 100 ms à frente e nunca agenda o mesmo pulso duas vezes', () => {
    const { sint, metro, andar } = montar()
    metro.iniciar()
    expect(sint.cliques).toHaveLength(1)
    andar(1.6)
    expect(tempos(sint)).toEqual([10.05, 10.55, 11.05, 11.55])
  })

  it('o pulso visual sai quando o relógio alcança o pulso, não quando é agendado', () => {
    const { metro, andar } = montar()
    const vistos: Pulso[] = []
    metro.aoPulso((p) => vistos.push(p))
    metro.iniciar()
    expect(vistos).toHaveLength(0)
    andar(0.075)
    expect(vistos.map((p) => p.batida)).toEqual([1])
    andar(0.5)
    expect(vistos.map((p) => p.batida)).toEqual([1, 2])
  })

  it('compasso silenciado anda no visual mas não soa', () => {
    const { sint, metro, andar } = montar({ temposPorCompasso: 1, silencio: { ativo: true, tocar: 1, silenciar: 1 } })
    const vistos: Pulso[] = []
    metro.aoPulso((p) => vistos.push(p))
    metro.iniciar()
    andar(2.1)
    // 120 BPM, 1 tempo por compasso: um compasso a cada 0,5 s.
    expect(vistos.map((p) => p.silenciado)).toEqual([false, true, false, true, false])
    expect(tempos(sint)).toEqual([10.05, 11.05, 12.05])
  })

  it('parar cala o que já foi agendado e iniciar de novo volta ao tempo 1', () => {
    const { sint, metro, andar, despertador } = montar()
    const vistos: Pulso[] = []
    metro.aoPulso((p) => vistos.push(p))
    metro.iniciar()
    andar(0.6)
    metro.parar()
    expect(metro.tocando).toBe(false)
    expect(sint.silencios).toBe(1)
    expect(despertador.aoTique).toBeNull()
    andar(1)
    expect(vistos.map((p) => p.batida)).toEqual([1, 2])
    metro.iniciar()
    andar(0.075)
    expect(vistos.at(-1)?.batida).toBe(1)
  })

  it('iniciar com o metrônomo já tocando é inócuo', () => {
    const { metro, despertador, sint } = montar()
    metro.iniciar()
    metro.iniciar()
    expect(despertador.inicios).toBe(1)
    expect(sint.cliques).toHaveLength(1)
  })

  it('novo andamento vale no tempo seguinte; as subdivisões do tempo corrente ficam', () => {
    const { sint, metro, andar } = montar({ bpm: 60, subdivisao: 2 })
    metro.iniciar()
    andar(0.2)
    metro.configurar({ ...CONFIG_PADRAO, bpm: 120, subdivisao: 2, contagemEntrada: 0 })
    andar(1.4)
    expect(tempos(sint)).toEqual([10.05, 10.55, 11.05, 11.3, 11.55])
  })

  it('configuração inválida é recusada e não muda o que está tocando', () => {
    const { metro } = montar()
    expect(() => metro.configurar({ ...CONFIG_PADRAO, bpm: 500 })).toThrow(RangeError)
  })

  it('a grade: parado não há; rodando é o próximo pulso, contando as subdivisões', () => {
    const { metro, andar } = montar({ subdivisao: 2 })
    expect(metro.proximoDaGrade(10)).toBeNull()
    metro.iniciar()
    andar(0.1)
    expect(metro.proximoDaGrade(10.1)).toBeCloseTo(10.3, 12)
    expect(metro.proximoDaGrade(10.31)).toBeCloseTo(10.55, 12)
  })

  it('cancelar a inscrição para de avisar', () => {
    const { metro, andar } = montar()
    const vistos: Pulso[] = []
    const cancelar = metro.aoPulso((p) => vistos.push(p))
    metro.iniciar()
    cancelar()
    andar(1)
    expect(vistos).toHaveLength(0)
  })

  it('aoAgendar recebe cada pulso uma vez, no agendamento, inclusive os silenciados', () => {
    const { metro, andar } = montar({ temposPorCompasso: 1, silencio: { ativo: true, tocar: 1, silenciar: 1 } })
    const agendados: number[] = []
    metro.aoAgendar((p) => agendados.push(Number(p.tempo.toFixed(6))))
    metro.iniciar()
    expect(agendados).toEqual([10.05])
    andar(0.6)
    expect(agendados).toEqual([10.05, 10.55])
  })
})
