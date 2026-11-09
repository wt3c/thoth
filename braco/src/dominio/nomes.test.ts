import { describe, expect, it } from 'vitest'
import { nomeDaClasse } from './nomes'

describe('nomeDaClasse', () => {
  it('cifra com sustenido por padrão', () => {
    expect([0, 1, 4, 9, 11].map((c) => nomeDaClasse(c))).toEqual(['C', 'C#', 'E', 'A', 'B'])
  })
})
