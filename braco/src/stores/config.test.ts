import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { useConfigStore } from './config'

describe('useConfigStore', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('começa no baixo de 4 cordas em E A D G', () => {
    const config = useConfigStore()
    expect(config.afinacao.id).toBe('baixo-4')
    expect(config.afinacao.cordas).toEqual([28, 33, 38, 43])
  })

  it('trocar o id da afinação troca as cordas', () => {
    const config = useConfigStore()
    config.afinacaoId = 'baixo-5'
    expect(config.afinacao.cordas).toHaveLength(5)
  })

  it('id desconhecido é erro, não volta silenciosamente ao padrão', () => {
    const config = useConfigStore()
    config.afinacaoId = 'inexistente'
    expect(() => config.afinacao).toThrow(/inexistente/)
  })
})
