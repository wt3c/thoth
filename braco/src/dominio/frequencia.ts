import type { Altura } from './tipos'

/** Temperamento igual de 12 notas, com o lá 4 (MIDI 69) como referência. */
export function frequencia(altura: Altura, la4 = 440): number {
  return la4 * 2 ** ((altura - 69) / 12)
}
