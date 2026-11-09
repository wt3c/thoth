import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { BPM_MAX } from '@/som/config-metronomo'
import { useMetronomoStore } from '@/stores/metronomo'
import BarraMetronomo from './BarraMetronomo.vue'

vi.mock('@/composables/motor', () => ({ obterMotor: () => new Promise(() => {}) }))

let pinia: ReturnType<typeof createPinia>
beforeEach(() => {
  pinia = createPinia()
  setActivePinia(pinia)
})
const montar = () => mount(BarraMetronomo, { global: { plugins: [pinia] } })

describe('BarraMetronomo', () => {
  it('é uma região nomeada com tocar, andamento e indicador', () => {
    const barra = montar()
    expect(barra.get('[role="region"]').attributes('aria-label')).toBe('Metrônomo rápido')
    expect(barra.get('.tocar').attributes('aria-pressed')).toBe('false')
    expect(barra.get('.bpm').text()).toBe('100')
    expect(barra.findAll('.tempo')).toHaveLength(4)
  })

  it('tocar chama o mesmo alternar do painel', async () => {
    const barra = montar()
    const metro = useMetronomoStore()
    const chamadas: string[] = []
    metro.$onAction(({ name }) => chamadas.push(name))
    await barra.get('.tocar').trigger('click')
    expect(chamadas).toContain('alternar')
  })

  it('± mudam o andamento no store, sem passar do limite', async () => {
    const barra = montar()
    const metro = useMetronomoStore()
    await barra.get('[data-acao="mais"]').trigger('click')
    await vi.waitFor(() => expect(metro.config.bpm).toBe(101))
    await barra.get('[data-acao="menos"]').trigger('click')
    await barra.get('[data-acao="menos"]').trigger('click')
    await vi.waitFor(() => expect(metro.config.bpm).toBe(99))
    await metro.atualizar({ bpm: BPM_MAX })
    await barra.get('[data-acao="mais"]').trigger('click')
    await vi.waitFor(() => expect(metro.config.bpm).toBe(BPM_MAX))
  })

  it('acende o tempo que soou', async () => {
    const barra = montar()
    const metro = useMetronomoStore()
    metro.pulso = { tempo: 0, compasso: 0, batida: 2, sub: 0, acento: false, silenciado: false, contagem: false }
    await barra.vm.$nextTick()
    expect(barra.findAll('.tempo').map((t) => t.classes('aceso'))).toEqual([false, true, false, false])
  })
})
