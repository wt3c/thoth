import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { useConfigStore } from '@/stores/config'
import { useMetronomoStore } from '@/stores/metronomo'
import { CHAVE, ligarPersistencia } from './usePersistencia'

vi.mock('@/composables/motor', () => ({ obterMotor: () => new Promise(() => {}) }))

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  history.replaceState(null, '', '/braco/')
})

describe('ligarPersistencia (S8)', () => {
  it('abre com a URL por cima do que estava salvo', async () => {
    localStorage.setItem(CHAVE, 'v=1&casas=20&bpm=90')
    history.replaceState(null, '', '/braco/?modo=teoria&tonica=9')
    const config = useConfigStore()
    const metro = useMetronomoStore()
    ligarPersistencia()
    await nextTick()
    expect([config.casas, config.modo, config.tonica, metro.config.bpm]).toEqual([20, 'teoria', 9, 90])
  })

  it('cada mudança vai para o localStorage e para a URL, sem nova entrada no histórico', async () => {
    const config = useConfigStore()
    const metro = useMetronomoStore()
    ligarPersistencia()
    const entradas = history.length
    config.escolherCasas(17)
    await metro.atualizar({ bpm: 140 })
    await nextTick()
    expect(localStorage.getItem(CHAVE)).toBe('v=1&casas=17&bpm=140')
    expect(location.search).toBe('?v=1&casas=17&bpm=140')
    expect(location.pathname).toBe('/braco/')
    expect(history.length).toBe(entradas)
  })

  it('o que foi recusado é avisado no console, sem impedir a abertura', async () => {
    const aviso = vi.spyOn(console, 'warn').mockImplementation(() => {})
    history.replaceState(null, '', '/braco/?casas=99')
    ligarPersistencia()
    await nextTick()
    expect(aviso).toHaveBeenCalledWith('preferências recusadas', ['url: casas=99'])
    expect(useConfigStore().casas).toBe(21)
    aviso.mockRestore()
  })
})
