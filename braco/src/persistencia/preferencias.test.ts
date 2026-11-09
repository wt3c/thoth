import { describe, expect, it } from 'vitest'
import { carregar, escrever, PREFERENCIAS_PADRAO, type Preferencias } from './preferencias'

const comMetronomo = (parcial: Partial<Preferencias['metronomo']>): Preferencias['metronomo'] => ({
  ...PREFERENCIAS_PADRAO.metronomo,
  ...parcial,
})

describe('preferências (S8)', () => {
  it('o padrão se escreve só com a versão: a URL fica limpa', () => {
    expect(escrever(PREFERENCIAS_PADRAO)).toBe('v=1')
  })

  it('ida e volta preserva tudo, inclusive o ° do acorde diminuto e um filtro parcial', () => {
    const p: Preferencias = {
      ...PREFERENCIAS_PADRAO,
      instrumento: 'baixo',
      numCordas: 5,
      afinacaoId: 'baixo-5',
      casas: 21,
      modo: 'teoria',
      filtro: [0, 4, 7, 11],
      selecionada: 10,
      tonica: 9,
      padraoId: 'acorde-°7',
      rotulo: 'grau',
      nomenclatura: 'solfejo',
      acidente: 'bemol',
      tema: 'escuro',
      daltonico: true,
      quantizar: true,
      metronomo: comMetronomo({
        bpm: 132,
        temposPorCompasso: 7,
        subdivisao: 3,
        acentoNoUm: false,
        silencio: { ativo: true, tocar: 2, silenciar: 3 },
        volume: 0.35,
        som: 'madeira',
        contagemEntrada: 2,
      }),
    }
    const texto = escrever(p)
    expect(texto).toContain('padrao=acorde-%C2%B07')
    expect(carregar(texto, null)).toEqual({ preferencias: p, rejeitados: [] })
  })

  it('filtro vazio é uma escolha, não ausência', () => {
    const p = { ...PREFERENCIAS_PADRAO, filtro: [] }
    expect(carregar(escrever(p), null).preferencias.filtro).toEqual([])
  })

  it('URL vence o armazenado, que vence o padrão', () => {
    const armazenado = escrever({ ...PREFERENCIAS_PADRAO, casas: 20, modo: 'teoria' })
    const { preferencias } = carregar('?v=1&casas=15', armazenado)
    expect([preferencias.casas, preferencias.modo, preferencias.rotulo]).toEqual([15, 'teoria', 'nome'])
  })

  it('campo inválido é recusado e relatado; os outros valem', () => {
    const { preferencias, rejeitados } = carregar('?v=1&casas=99&modo=jazz&tonica=4&padrao=escala-xyz', null)
    expect(preferencias.tonica).toBe(4)
    expect([preferencias.casas, preferencias.modo, preferencias.padraoId]).toEqual([12, 'notas', null])
    expect(rejeitados).toEqual(['url: casas=99', 'url: modo=jazz', 'url: padrao=escala-xyz'])
  })

  it('armazenado de outra versão é descartado inteiro, com aviso', () => {
    const { preferencias, rejeitados } = carregar('', 'v=0&casas=20')
    expect(preferencias).toEqual(PREFERENCIAS_PADRAO)
    expect(rejeitados).toEqual(['armazenado: versão 0'])
  })

  it('URL de outra versão também é descartada; sem versão, vale a atual', () => {
    expect(carregar('?v=2&casas=20', null).rejeitados).toEqual(['url: versão 2'])
    expect(carregar('?casas=20', null).preferencias.casas).toBe(20)
  })

  it('afinação de outro instrumento volta à padrão do instrumento, com aviso', () => {
    const { preferencias, rejeitados } = carregar('?instrumento=guitarra&cordas=6', 'v=1&cordas=5&afinacao=baixo-5')
    expect([preferencias.instrumento, preferencias.numCordas, preferencias.afinacaoId]).toEqual(['guitarra', 6, 'guitarra-6'])
    expect(rejeitados).toEqual(['afinacao=baixo-5 não serve para guitarra de 6 cordas'])
  })

  it('número de cordas que o instrumento não tem volta ao primeiro possível', () => {
    const { preferencias, rejeitados } = carregar('?instrumento=guitarra&cordas=7', null)
    expect([preferencias.numCordas, preferencias.afinacaoId]).toEqual([6, 'guitarra-6'])
    expect(rejeitados).toContain('cordas=7 não serve para guitarra')
  })

  it('andamento fora da faixa do metrônomo é recusado', () => {
    const { preferencias, rejeitados } = carregar('?bpm=500&tempos=3', null)
    expect(preferencias.metronomo).toMatchObject({ bpm: 100, temposPorCompasso: 3 })
    expect(rejeitados).toEqual(['url: bpm=500'])
  })
})
