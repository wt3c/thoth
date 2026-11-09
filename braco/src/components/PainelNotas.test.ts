import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useConfigStore } from '@/stores/config'
import { useMetronomoStore } from '@/stores/metronomo'
import PainelNotas from './PainelNotas.vue'

vi.mock('@/composables/motor', () => ({ obterMotor: () => new Promise(() => {}) }))

let pinia: ReturnType<typeof createPinia>
beforeEach(() => {
  pinia = createPinia()
  setActivePinia(pinia)
})
const montar = () => mount(PainelNotas, { global: { plugins: [pinia] } })
const botao = (painel: ReturnType<typeof montar>) => painel.get('[data-acao="tocar-notas"]')

describe('PainelNotas: tocar as notas acesas no metrônomo', () => {
  it('sem nota acesa, o botão fica desligado', async () => {
    const painel = montar()
    await painel.get('[data-acao="nenhuma"]').trigger('click')
    expect(botao(painel).attributes('disabled')).toBeDefined()
  })

  it('toca cada posição acesa, da grave à aguda, na sequência do metrônomo', async () => {
    const painel = montar()
    const config = useConfigStore()
    const metro = useMetronomoStore()
    const tocadas: unknown[] = []
    metro.$onAction(({ name, args }) => {
      if (name === 'tocarSequencia') tocadas.push(args[0])
    })
    config.casas = 5
    config.mostrarClasses([4, 9])
    await painel.vm.$nextTick()
    await botao(painel).trigger('click')
    const lugares = (tocadas[0] as { corda: number; casa: number }[]).map((p) => `${p.corda}-${p.casa}`)
    expect([tocadas.length, lugares]).toEqual([1, ['0-0', '0-5', '1-0', '2-2', '3-2']])
  })

  it('com a sequência ativa, o mesmo botão para as notas e o metrônomo', async () => {
    const painel = montar()
    const metro = useMetronomoStore()
    metro.sequenciaAtiva = true
    await painel.vm.$nextTick()
    expect(botao(painel).text()).toContain('Parar')
    const chamadas: string[] = []
    metro.$onAction(({ name }) => chamadas.push(name))
    await botao(painel).trigger('click')
    expect(chamadas).toContain('parar')
  })
})
