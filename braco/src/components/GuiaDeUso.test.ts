import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import GuiaDeUso from './GuiaDeUso.vue'
import PainelExibicao from './PainelExibicao.vue'
import PainelInstrumento from './PainelInstrumento.vue'
import PainelMetronomo from './PainelMetronomo.vue'
import PainelNotas from './PainelNotas.vue'

vi.mock('@/composables/motor', () => ({ obterMotor: () => new Promise(() => {}) }))

let pinia: ReturnType<typeof createPinia>
beforeEach(() => {
  pinia = createPinia()
  setActivePinia(pinia)
})
const montar = (componente: Parameters<typeof mount>[0]) => mount(componente, { global: { plugins: [pinia] } })

describe('GuiaDeUso', () => {
  it('é uma seção com âncora, um bloco que abre e fecha por assunto', () => {
    const guia = montar(GuiaDeUso)
    expect(guia.get('section').attributes('id')).toBe('como-usar')
    expect(guia.get('h2').text()).toBe('Como usar')
    const blocos = guia.findAll('details')
    expect(blocos.map((b) => b.attributes('data-secao'))).toEqual([
      'comecar', 'notas', 'oitavas', 'teoria', 'metronomo', 'instrumento', 'exibicao', 'salvo', 'teclado',
    ])
    expect(blocos.every((b) => b.find('summary').text().length > 0)).toBe(true)
    expect(blocos.every((b) => b.attributes('open') === undefined)).toBe(true)
  })

  it('cada painel da página tem o seu bloco, com o mesmo título', () => {
    const resumos = montar(GuiaDeUso).findAll('summary').map((s) => s.text())
    for (const painel of [PainelNotas, PainelMetronomo, PainelInstrumento, PainelExibicao]) {
      const titulo = montar(painel).get('h2').text()
      expect(resumos).toContain(titulo)
    }
  })

  it('o guia cita os botões pelo nome que aparece na tela', () => {
    const texto = montar(GuiaDeUso).text()
    for (const rotulo of ['Todas', 'Limpar', 'Tocar notas do braço no metrônomo', 'Parar notas', 'Tap']) {
      expect(texto).toContain(rotulo)
    }
  })
})
