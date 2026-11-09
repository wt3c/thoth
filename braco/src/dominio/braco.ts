import type { Afinacao, Posicao } from './tipos'

/** Todas as posições do braço, da casa 0 (solta) até `casas`, em cada corda. */
export function gerarBraco(afinacao: Afinacao, casas: number): Posicao[] {
  return afinacao.cordas.flatMap((solta, corda) =>
    Array.from({ length: casas + 1 }, (_, casa) => {
      const altura = solta + casa
      return { corda, casa, altura, classe: altura % 12 }
    }),
  )
}
