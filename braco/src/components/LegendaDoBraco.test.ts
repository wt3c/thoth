import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { useConfigStore } from '@/stores/config'
import LegendaDoBraco from './LegendaDoBraco.vue'

let pinia: ReturnType<typeof createPinia>
beforeEach(() => {
  pinia = createPinia()
  setActivePinia(pinia)
})
const montar = () => mount(LegendaDoBraco, { global: { plugins: [pinia] } })

describe('LegendaDoBraco', () => {
  it('explica o anel e cada etiqueta de oitava, com o mesmo desenho do braço', () => {
    const legenda = montar()
    const itens = legenda.findAll('[data-sinal]')
    expect(itens.map((i) => i.attributes('data-sinal'))).toEqual(['referencia', '+1', '+2', '−1', '='])
    expect(itens[0]!.find('.anel-referencia').exists()).toBe(true)
    expect(itens.slice(1).map((i) => i.get('.oitava text').text())).toEqual(['+1', '+2', '−1', '='])
    expect(itens[1]!.text()).toContain('mais aguda')
    expect(itens[3]!.text()).toContain('mais grave')
    expect(itens[4]!.text()).toContain('outra corda')
    expect(legenda.text()).toContain('12 casas')
  })

  it('o desenho é decorativo; a lista tem nome acessível', () => {
    const legenda = montar()
    expect(legenda.findAll('svg').every((s) => s.attributes('aria-hidden') === 'true')).toBe(true)
    expect(legenda.get('[role="list"], ul').attributes('aria-label')).toBe('Legenda das oitavas')
  })

  it('só aparece no modo notas, onde as oitavas existem', async () => {
    const legenda = montar()
    useConfigStore().modo = 'teoria'
    await legenda.vm.$nextTick()
    expect(legenda.find('[data-sinal]').exists()).toBe(false)
  })
})
