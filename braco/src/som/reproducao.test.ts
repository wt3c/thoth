import { describe, expect, it } from 'vitest'
import type { Altura } from '@/dominio/tipos'
import { momentoDaNota, SequenciaNoMetronomo } from './reproducao'
import type { Pulso } from './tipos'

const grade = (proximo: number | null) => ({ proximoDaGrade: () => proximo })

describe('momentoDaNota (M8)', () => {
  it('metrônomo parado: a nota soa na hora, quantizando ou não', () => {
    expect(momentoDaNota(5, grade(null), false)).toBe(5)
    expect(momentoDaNota(5, grade(null), true)).toBe(5)
  })

  it('rodando sem quantizar (padrão): soa na hora', () => {
    expect(momentoDaNota(5, grade(5.2), false)).toBe(5)
  })

  it('rodando e quantizando: espera o próximo instante da grade', () => {
    expect(momentoDaNota(5, grade(5.2), true)).toBe(5.2)
  })
})

class MetronomoFalso {
  private cb: ((p: Pulso) => void) | null = null
  aoAgendar(cb: (p: Pulso) => void) {
    this.cb = cb
    return () => {
      this.cb = null
    }
  }
  /** Entrega e devolve o mesmo objeto, como o metrônomo real faz entre `aoAgendar` e `aoPulso`. */
  agendar(p: Partial<Pulso>): Pulso {
    const pulso = { tempo: 0, compasso: 0, batida: 1, sub: 0, acento: false, silenciado: false, contagem: false, ...p }
    this.cb?.(pulso)
    return pulso
  }
}

class Notas {
  tocadas: { altura: Altura; tempo: number; duracao: number }[] = []
  nota(altura: Altura, tempo: number, duracao: number) {
    this.tocadas.push({ altura, tempo, duracao })
  }
}

describe('SequenciaNoMetronomo (S6)', () => {
  function montar() {
    const metro = new MetronomoFalso()
    const sint = new Notas()
    const seq = new SequenciaNoMetronomo(metro, sint)
    return { metro, sint, seq }
  }

  it('cada pulso agendado toca a nota seguinte no instante do pulso, em ciclo', () => {
    const { metro, sint, seq } = montar()
    seq.iniciar([40, 43, 45], 0.2)
    for (const tempo of [1, 1.5, 2, 2.5]) metro.agendar({ tempo })
    expect(sint.tocadas).toEqual([
      { altura: 40, tempo: 1, duracao: 0.2 },
      { altura: 43, tempo: 1.5, duracao: 0.2 },
      { altura: 45, tempo: 2, duracao: 0.2 },
      { altura: 40, tempo: 2.5, duracao: 0.2 },
    ])
  })

  it('a contagem de entrada não consome nota; o compasso silenciado sim', () => {
    const { metro, sint, seq } = montar()
    seq.iniciar([40, 43], 0.2)
    metro.agendar({ tempo: 1, contagem: true, compasso: -1 })
    metro.agendar({ tempo: 2, silenciado: true })
    metro.agendar({ tempo: 3 })
    expect(sint.tocadas.map((n) => [n.altura, n.tempo])).toEqual([
      [40, 2],
      [43, 3],
    ])
  })

  it('o visual sabe qual nota cada pulso tocou', () => {
    const { metro, seq } = montar()
    seq.iniciar([40, 43], 0.2)
    const pulsos = [1, 2, 3].map((tempo) => metro.agendar({ tempo }))
    expect(pulsos.map((p) => seq.indiceDoPulso(p))).toEqual([0, 1, 0])
    expect(seq.indiceDoPulso({ ...pulsos[0]!, tempo: 9 })).toBeNull()
  })

  it('parar desliga a sequência; sequência vazia é recusada', () => {
    const { metro, sint, seq } = montar()
    expect(() => seq.iniciar([], 0.2)).toThrow(RangeError)
    seq.iniciar([40], 0.2)
    seq.parar()
    metro.agendar({ tempo: 1 })
    expect(sint.tocadas).toHaveLength(0)
    expect(seq.ativa).toBe(false)
  })

  it('iniciar de novo recomeça do começo da sequência nova', () => {
    const { metro, sint, seq } = montar()
    seq.iniciar([40, 43], 0.2)
    metro.agendar({ tempo: 1 })
    seq.iniciar([50, 52], 0.2)
    metro.agendar({ tempo: 2 })
    expect(sint.tocadas.map((n) => n.altura)).toEqual([40, 50])
  })
})
