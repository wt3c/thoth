import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { PALETAS } from '@/dominio/cores'
import { useConfigStore } from './config'

const posicao = (altura: number) => ({ corda: 0, casa: 0, altura, classe: altura % 12 })

describe('useConfigStore', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('começa no baixo de 4 cordas em E A D G, 12 casas, modo notas com tudo visível', () => {
    const config = useConfigStore()
    expect(config.afinacao.cordas).toEqual([28, 33, 38, 43])
    expect(config.casas).toBe(12)
    expect(config.escolhas).toMatchObject({ modo: 'notas', selecionada: null, tonica: null, padrao: null })
    expect(config.escolhas.filtro).toHaveLength(12)
  })

  it('id desconhecido é erro, não volta silenciosamente ao padrão', () => {
    const config = useConfigStore()
    config.afinacaoId = 'inexistente'
    expect(() => config.afinacao).toThrow(/inexistente/)
  })

  it('M1/M2: trocar instrumento ou número de cordas leva à afinação padrão correspondente', () => {
    const config = useConfigStore()
    config.escolherNumCordas(7)
    expect(config.afinacao.id).toBe('baixo-7')
    config.escolherInstrumento('guitarra')
    expect([config.numCordas, config.afinacao.id]).toEqual([6, 'guitarra-6'])
    config.escolherInstrumento('baixo')
    expect(config.afinacao.id).toBe('baixo-4')
    expect(config.afinacoesDisponiveis.map((a) => a.id)).toContain('baixo-drop-d')
  })

  it('número de cordas e de casas fora da faixa é recusado', () => {
    const config = useConfigStore()
    expect(() => config.escolherNumCordas(8)).toThrow(RangeError)
    expect(() => config.escolherCasas(11)).toThrow(RangeError)
    config.escolherCasas(24)
    expect(config.casas).toBe(24)
  })

  it('no modo notas, tocar seleciona a classe (M4); tocar de novo desmarca', () => {
    const config = useConfigStore()
    config.aoTocar(posicao(45))
    expect(config.selecionada).toBe(9)
    config.aoTocar(posicao(57))
    expect(config.selecionada).toBeNull()
  })

  it('no modo teoria, a nota tocada vira a tônica (M9)', () => {
    const config = useConfigStore()
    config.modo = 'teoria'
    config.aoTocar(posicao(41))
    config.aoTocar(posicao(41))
    expect(config.tonica).toBe(5)
    config.padraoId = 'escala-maior'
    expect(config.escolhas.padrao?.graus).toHaveLength(7)
  })

  it('o filtro alterna uma classe e mantém a ordem cromática', () => {
    const config = useConfigStore()
    config.mostrarClasses([])
    config.alternarClasse(7)
    config.alternarClasse(0)
    expect(config.filtro).toEqual([0, 7])
    config.alternarClasse(7)
    expect(config.filtro).toEqual([0])
  })

  it('a paleta segue o tema; o modo daltônico vence o tema', () => {
    const config = useConfigStore()
    config.tema = 'escuro'
    expect(config.escolhas.paleta).toBe(PALETAS.escuro)
    config.daltonico = true
    expect(config.escolhas.paleta).toBe(PALETAS.daltonico)
    config.daltonico = false
    config.tema = 'claro'
    expect(config.temaEfetivo).toBe('claro')
  })
})
