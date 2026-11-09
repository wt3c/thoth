import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { Afinacao } from '@/dominio/tipos'
import BracoSvg from './BracoSvg.vue'

const BAIXO_4: Afinacao = { id: 'baixo-4', nome: 'E A D G', instrumento: 'baixo', cordas: [28, 33, 38, 43] }

describe('BracoSvg', () => {
  it('desenha uma nota por casa de cada corda, da solta à última', () => {
    const braco = mount(BracoSvg, { props: { afinacao: BAIXO_4, casas: 12 } })
    expect(braco.findAll('[data-nota]')).toHaveLength(4 * 13)
  })

  it('a corda grave fica embaixo, como o baixo visto por quem toca', () => {
    const braco = mount(BracoSvg, { props: { afinacao: BAIXO_4, casas: 12 } })
    const y = (corda: number) => Number(braco.get(`[data-corda="${corda}"][data-casa="0"]`).attributes('data-y'))
    expect(y(0)).toBeGreaterThan(y(3))
  })

  it('clicar numa nota emite a posição com a altura', async () => {
    const braco = mount(BracoSvg, { props: { afinacao: BAIXO_4, casas: 12 } })
    await braco.get('[data-corda="0"][data-casa="5"]').trigger('click')
    expect(braco.emitted('tocar')?.[0]?.[0]).toMatchObject({ corda: 0, casa: 5, altura: 33 })
  })

  it('cada nota tem nome acessível e é alvo de pelo menos 44 px', () => {
    const braco = mount(BracoSvg, { props: { afinacao: BAIXO_4, casas: 12 } })
    const nota = braco.get('[data-corda="0"][data-casa="5"]')
    expect(nota.attributes('role')).toBe('button')
    expect(nota.attributes('aria-label')).toBe('A, corda 4, casa 5')
    expect(Number(nota.get('.alvo').attributes('width'))).toBeGreaterThanOrEqual(44)
  })
})
