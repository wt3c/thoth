import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'
import App from './App.vue'

vi.mock('@/composables/motor', () => ({ obterMotor: () => new Promise(() => {}) }))

describe('App: disposição dos painéis', () => {
  it('o metrônomo vem depois de Notas, Instrumento e Exibição, numa faixa da largura toda', () => {
    const app = mount(App, { global: { plugins: [createPinia()] } })
    const paineis = app.findAll('.paineis > section')
    expect(paineis.map((p) => p.get('h2').text())).toEqual(['Notas', 'Instrumento', 'Exibição', 'Metrônomo'])
    expect(paineis.at(-1)?.classes()).toContain('largo')
    app.unmount()
  })
})
