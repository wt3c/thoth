import { describe, expect, it } from 'vitest'
import { corDoTexto, PALETAS, razaoContraste } from './cores'
import { PADROES } from './teoria'
import type { Padrao, Posicao } from './tipos'
import { exibirGrau, TODAS_AS_CLASSES, vistaDaNota, type EscolhasDaVista } from './vista'

const padrao = (id: string): Padrao => {
  const achado = PADROES.find((p) => p.id === id)
  if (!achado) throw new Error(id)
  return achado
}
const pos = (altura: number, corda = 0, casa = 0): Posicao => ({ corda, casa, altura, classe: altura % 12 })
const NOTAS: EscolhasDaVista = {
  modo: 'notas',
  filtro: TODAS_AS_CLASSES,
  selecionada: null,
  tonica: null,
  padrao: null,
  rotulo: 'nome',
  nome: { nomenclatura: 'cifra', acidente: 'sustenido' },
  paleta: PALETAS.claro,
}
const TEORIA: EscolhasDaVista = { ...NOTAS, modo: 'teoria', tonica: 5 }

describe('vistaDaNota — modo notas', () => {
  it('M3: mostra todas as notas, cada classe com a sua cor e texto legível', () => {
    const vistas = Array.from({ length: 12 }, (_, c) => vistaDaNota(pos(36 + c), NOTAS))
    expect(vistas.every((v) => v.visivel)).toBe(true)
    expect(new Set(vistas.map((v) => v.fundo)).size).toBe(12)
    for (const v of vistas) expect(razaoContraste(v.fundo, v.corTexto)).toBeGreaterThanOrEqual(4.5)
    expect(vistas.map((v) => v.texto).join(' ')).toBe('C C♯ D D♯ E F F♯ G G♯ A A♯ B')
  })

  it('o filtro esconde as classes de fora; a selecionada aparece mesmo filtrada (M4)', () => {
    const e = { ...NOTAS, filtro: [0, 4, 7], selecionada: 9 }
    expect(vistaDaNota(pos(40), e).visivel).toBe(true)
    expect(vistaDaNota(pos(41), e).visivel).toBe(false)
    expect(vistaDaNota(pos(45), e)).toMatchObject({ visivel: true, destaque: true })
    expect(vistaDaNota(pos(57), e).destaque).toBe(true)
    expect(vistaDaNota(pos(40), e).destaque).toBe(false)
  })

  it('S3: solfejo e bemol', () => {
    const e = { ...NOTAS, nome: { nomenclatura: 'solfejo', acidente: 'bemol' } } as const
    expect(vistaDaNota(pos(46), e).texto).toBe('Si♭')
    expect(vistaDaNota(pos(46), e).falado).toBe('Si♭')
  })

  it('sem tônica escolhida, o modo teoria se comporta como o de notas', () => {
    expect(vistaDaNota(pos(45), { ...TEORIA, tonica: null })).toEqual(vistaDaNota(pos(45), NOTAS))
  })
})

describe('vistaDaNota — modo teoria (M9)', () => {
  it('sem padrão, toda nota aparece pela função cromática em relação à tônica', () => {
    const e = { ...TEORIA, rotulo: 'grau' } as const
    expect(vistaDaNota(pos(41), e)).toMatchObject({ visivel: true, texto: '1', destaque: true, fundo: PALETAS.claro.tonica })
    expect(vistaDaNota(pos(44), e)).toMatchObject({ texto: '♭3', destaque: false, fundo: PALETAS.claro.porGrau['3'] })
    expect(vistaDaNota(pos(47), e).texto).toBe('♯4')
  })

  it('com padrão, só aparecem as notas dele, grafadas pela tônica: o 4º de fá maior é si bemol', () => {
    const e = { ...TEORIA, padrao: padrao('escala-maior') }
    expect(vistaDaNota(pos(46), e)).toMatchObject({ visivel: true, texto: 'B♭', falado: 'B♭, grau 4' })
    expect(vistaDaNota(pos(47), e).visivel).toBe(false)
    expect(vistaDaNota(pos(46), { ...e, rotulo: 'grau' }).texto).toBe('4')
  })

  it('a tônica nunca divide a cor com outro grau e todo texto tem 4,5:1', () => {
    for (const paleta of Object.values(PALETAS)) {
      const e = { ...TEORIA, paleta }
      const vistas = Array.from({ length: 12 }, (_, c) => vistaDaNota(pos(36 + c), e))
      const tonica = vistas.filter((v) => v.destaque)
      expect(tonica).toHaveLength(1)
      expect(vistas.filter((v) => v.fundo === paleta.tonica)).toHaveLength(1)
      for (const v of vistas) expect(v.corTexto).toBe(corDoTexto(v.fundo))
    }
  })

  it('o acidente escolhido grafa a tônica: lá sustenido × si bemol maior', () => {
    const e = { ...TEORIA, tonica: 10, padrao: padrao('escala-maior') }
    expect(vistaDaNota(pos(46), e).texto).toBe('A♯')
    expect(vistaDaNota(pos(46), { ...e, nome: { nomenclatura: 'cifra', acidente: 'bemol' } }).texto).toBe('B♭')
  })
})

describe('exibirGrau', () => {
  it('troca os acidentes ASCII pelos musicais', () => {
    expect(['1', 'b3', '#4', 'bb7', '##5'].map(exibirGrau)).toEqual(['1', '♭3', '♯4', '𝄫7', '𝄪5'])
  })
})
