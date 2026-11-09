import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useConfigStore } from '@/stores/config'
import { useMetronomoStore } from '@/stores/metronomo'
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

describe('PainelInstrumento', () => {
  it('troca instrumento, cordas, afinação e casas', async () => {
    const painel = montar(PainelInstrumento)
    const config = useConfigStore()
    await painel.get('input[type=radio][value="5"]').setValue()
    expect(config.afinacao.id).toBe('baixo-5')
    await painel.get('input[type=radio][value="guitarra"]').setValue()
    expect(config.afinacao.id).toBe('guitarra-6')
    expect(painel.find('input[type=radio][value="5"]').exists()).toBe(false)
    await painel.get('select').setValue('guitarra-dadgad')
    expect(config.afinacao.nome).toBe('DADGAD')
    await painel.get('input[type=range]').setValue('20')
    expect(config.casas).toBe(20)
  })
})

describe('PainelNotas', () => {
  it('o filtro tem um botão por classe, com estado acessível', async () => {
    const painel = montar(PainelNotas)
    const config = useConfigStore()
    const botoes = painel.findAll('[data-classe]')
    expect(botoes).toHaveLength(12)
    await botoes[1]!.trigger('click')
    expect(config.filtro).toEqual([1])
    expect(botoes[1]!.attributes('aria-pressed')).toBe('true')
    await painel.get('[data-acao="todas"]').trigger('click')
    expect(config.filtro).toHaveLength(12)
    const limpar = painel.get('[data-acao="limpar"]')
    expect(limpar.text()).toBe('Limpar')
    await limpar.trigger('click')
    expect(config.filtro).toEqual([])
  })

  it('no modo teoria, escolhe padrão e rótulo; sem tônica, pede um clique no braço', async () => {
    const painel = montar(PainelNotas)
    const config = useConfigStore()
    await painel.get('input[type=radio][value="teoria"]').setValue()
    expect(painel.text()).toContain('Toque uma nota no braço')
    config.tonica = 5
    await painel.vm.$nextTick()
    await painel.get('select').setValue('escala-maior')
    expect(config.padraoId).toBe('escala-maior')
    await painel.get('input[type=radio][value="grau"]').setValue()
    expect(config.rotulo).toBe('grau')
    expect(painel.text()).toContain('F')
  })
})

describe('PainelExibicao', () => {
  it('nomenclatura, acidente, tema e daltônico', async () => {
    const painel = montar(PainelExibicao)
    const config = useConfigStore()
    await painel.get('input[type=radio][value="solfejo"]').setValue()
    await painel.get('input[type=radio][value="bemol"]').setValue()
    await painel.get('input[type=radio][value="escuro"]').setValue()
    await painel.get('input[type=checkbox]').setValue(true)
    expect([config.nomenclatura, config.acidente, config.tema, config.daltonico]).toEqual(['solfejo', 'bemol', 'escuro', true])
  })
})

describe('PainelMetronomo', () => {
  it('andamento por campo e pelos botões ±, limitado à faixa', async () => {
    const painel = montar(PainelMetronomo)
    const metro = useMetronomoStore()
    await painel.get('input[type=number]').setValue('132')
    await vi.waitFor(() => expect(metro.config.bpm).toBe(132))
    await painel.get('[data-acao="mais"]').trigger('click')
    await vi.waitFor(() => expect(metro.config.bpm).toBe(133))
    await painel.get('input[type=number]').setValue('999')
    await vi.waitFor(() => expect(metro.config.bpm).toBe(244))
  })

  it('compasso, subdivisão, som, contagem e silêncio vão para a configuração', async () => {
    const painel = montar(PainelMetronomo)
    const metro = useMetronomoStore()
    await painel.get('select[name="tempos"]').setValue('3')
    await painel.get('input[type=radio][value="3"][name="subdivisao"]').setValue()
    await painel.get('select[name="som"]').setValue('madeira')
    await painel.get('select[name="contagem"]').setValue('1')
    await painel.get('input[name="silencio"]').setValue(true)
    await vi.waitFor(() =>
      expect(metro.config).toMatchObject({ temposPorCompasso: 3, subdivisao: 3, som: 'madeira', contagemEntrada: 1, silencio: { ativo: true } }),
    )
  })

  it('o indicador tem um ponto por tempo e acende o tempo que soou', async () => {
    const painel = montar(PainelMetronomo)
    const metro = useMetronomoStore()
    metro.pulso = { tempo: 0, compasso: 0, batida: 3, sub: 0, acento: false, silenciado: false, contagem: false }
    await painel.vm.$nextTick()
    const pontos = painel.findAll('.tempo')
    expect(pontos).toHaveLength(4)
    expect(pontos.map((p) => p.classes('aceso'))).toEqual([false, false, true, false])
  })

  it('quantizar começa desligado (M8)', () => {
    const painel = montar(PainelMetronomo)
    expect((painel.get('input[name="quantizar"]').element as HTMLInputElement).checked).toBe(false)
  })
})
