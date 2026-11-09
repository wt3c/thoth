import dados from './afinacoes.json'
import type { Afinacao, Instrumento } from './tipos'

const AFINACOES: readonly Afinacao[] = dados.map((afinacao) => {
  if (afinacao.instrumento !== 'baixo' && afinacao.instrumento !== 'guitarra') {
    throw new Error(`Instrumento inválido na afinação ${afinacao.id}: ${afinacao.instrumento}`)
  }
  return { ...afinacao, instrumento: afinacao.instrumento }
})

export function afinacoesDe(instrumento: Instrumento, numCordas: number): readonly Afinacao[] {
  return AFINACOES.filter((a) => a.instrumento === instrumento && a.cordas.length === numCordas)
}

export function afinacaoPorId(id: string): Afinacao {
  const afinacao = AFINACOES.find((a) => a.id === id)
  if (!afinacao) throw new Error(`Afinação desconhecida: ${id}`)
  return afinacao
}

export function afinacaoPadrao(instrumento: Instrumento, numCordas: number): Afinacao {
  const afinacao = afinacoesDe(instrumento, numCordas).find((a) => a.id === `${instrumento}-${numCordas}`)
  if (!afinacao) throw new Error(`Sem afinação padrão para ${instrumento} de ${numCordas} cordas`)
  return afinacao
}
