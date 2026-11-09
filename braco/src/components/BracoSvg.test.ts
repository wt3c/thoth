import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { PALETAS } from '@/dominio/cores'
import type { Afinacao } from '@/dominio/tipos'
import { TODAS_AS_CLASSES, type EscolhasDaVista } from '@/dominio/vista'
import BracoSvg from './BracoSvg.vue'

const BAIXO_4: Afinacao = { id: 'baixo-4', nome: 'E A D G', instrumento: 'baixo', cordas: [28, 33, 38, 43] }
const NOTAS: EscolhasDaVista = {
  modo: 'notas',
  filtro: TODAS_AS_CLASSES,
  selecionada: null,
  tonica: null,
  padrao: null,
  rotulo: 'nome',
  nome: { nomenclatura: 'cifra', acidente: 'sustenido' },
  paleta: PALETAS.claro,
}
const montar = (escolhas: Partial<EscolhasDaVista> = {}, casas = 12, soando: number | null = null) =>
  mount(BracoSvg, { props: { afinacao: BAIXO_4, casas, escolhas: { ...NOTAS, ...escolhas }, soando } })

describe('BracoSvg', () => {
  it('desenha uma nota por casa de cada corda, da solta à última', () => {
    expect(montar().findAll('[data-nota]')).toHaveLength(4 * 13)
    expect(montar({}, 24).findAll('[data-nota]')).toHaveLength(4 * 25)
  })

  it('a corda grave fica embaixo, como o baixo visto por quem toca', () => {
    const braco = montar()
    const y = (corda: number) => Number(braco.get(`[data-corda="${corda}"][data-casa="0"]`).attributes('data-y'))
    expect(y(0)).toBeGreaterThan(y(3))
  })

  it('clicar numa nota emite a posição com a altura', async () => {
    const braco = montar()
    await braco.get('[data-corda="0"][data-casa="5"]').trigger('click')
    expect(braco.emitted('tocar')?.[0]?.[0]).toMatchObject({ corda: 0, casa: 5, altura: 33 })
  })

  it('cada nota tem nome acessível e é alvo de pelo menos 44 px', () => {
    const nota = montar().get('[data-corda="0"][data-casa="5"]')
    expect(nota.attributes('role')).toBe('button')
    expect(nota.attributes('aria-label')).toBe('A, corda 4, casa 5')
    expect(Number(nota.get('.alvo').attributes('width'))).toBeGreaterThanOrEqual(44)
  })

  it('pinta o marcador com a cor da vista e o texto com a cor legível', () => {
    const nota = montar().get('[data-corda="0"][data-casa="5"]')
    expect(nota.get('.marcador').attributes('fill')).toBe(PALETAS.claro.porClasse[9])
    expect(nota.get('.nome').attributes('fill')).toBe('#ffffff')
  })

  it('nota filtrada some da vista mas continua tocável; a selecionada fica destacada', () => {
    // E solta e casa 12 na corda E, casa 7 na A, 2 na D, 9 na G.
    const braco = montar({ filtro: [9], selecionada: 4 })
    const filtrada = braco.get('[data-corda="0"][data-casa="1"]')
    expect(filtrada.find('.marcador').exists()).toBe(false)
    expect(filtrada.attributes('role')).toBe('button')
    expect(braco.findAll('[data-destaque="true"]').map((n) => n.attributes('data-nota'))).toEqual(Array(5).fill('E'))
  })

  it('na teoria, o nome acessível diz o grau', () => {
    const nota = montar({ modo: 'teoria', tonica: 4 }).get('[data-corda="0"][data-casa="3"]')
    expect(nota.attributes('aria-label')).toBe('G, grau ♭3, corda 4, casa 3')
  })

  it('as cores do braço vêm da paleta, como variáveis CSS', () => {
    const estilo = montar({ paleta: PALETAS.escuro }).get('svg').attributes('style')
    expect(estilo).toContain(`--braco-madeira: ${PALETAS.escuro.braco.madeira}`)
  })

  it('a altura que soa na sequência acende em todas as posições dela, e só nelas', () => {
    // 33 = A1: corda E casa 5 e corda A solta.
    const acesas = montar({}, 12, 33).findAll('[data-soando="true"]')
    expect(acesas.map((n) => `${n.attributes('data-corda')}-${n.attributes('data-casa')}`)).toEqual(['0-5', '1-0'])
  })

  it('marcações nas casas 3, 5, 7, 9 e 12, dupla na 12', () => {
    const casas = montar().findAll('.marcacao').map((m) => Number(m.attributes('data-casa')))
    expect(casas).toEqual([3, 5, 7, 9, 12, 12])
    expect(montar({}, 24).findAll('.marcacao').filter((m) => m.attributes('data-casa') === '24')).toHaveLength(2)
  })
})
