import { describe, expect, it } from 'vitest'
import { PALETAS, razaoContraste, corDoTexto, corDoGrau } from './cores'

// Valores de referência independentes, incluindo a região linear da curva sRGB.
describe('contraste WCAG', () => {
  it('confere extremos, simetria e luminância sRGB', () => {
    expect(razaoContraste('#000000', '#ffffff')).toBe(21)
    expect(razaoContraste('#abcdef', '#abcdef')).toBe(1)
    expect(razaoContraste('#ffffff', '#777777')).toBeCloseTo(4.478, 3)
    expect(razaoContraste('#080808', '#ffffff')).toBeCloseTo(21 / (1 + (8 / 255) / 12.92 / 0.05), 10)
    expect(razaoContraste('#123456', '#abcdef')).toBe(razaoContraste('#abcdef', '#123456'))
  })
  it('escolhe preto ou branco pelo maior contraste', () => {
    expect(corDoTexto('#ffffff')).toBe('#000000')
    expect(corDoTexto('#000000')).toBe('#ffffff')
    expect(corDoTexto('#777777')).toBe('#000000')
  })
  it('rejeita cores fora do contrato #rrggbb com contexto', () => {
    expect(() => razaoContraste('red', '#ffffff')).toThrow(/red/)
    expect(() => corDoTexto('#fff')).toThrow(/#fff/)
  })
})

describe('paletas acessíveis', () => {
  it('Matte Black usa as cores do tema do Omarchy: tônica no laranja de destaque, braço preto fosco', () => {
    const p = PALETAS['matte-black']
    expect(p.tonica).toBe('#e68e0d')
    expect(p.braco.madeira).toBe('#1e1e1e')
  })

  it.each(['claro', 'escuro', 'daltonico', 'matte-black'] as const)('%s respeita os pisos em todas as funções', (tema) => {
    const p = PALETAS[tema]
    expect(p.id).toBe(tema)
    expect(p.porClasse).toHaveLength(12)
    expect(new Set(p.porClasse.map((c) => c.toLowerCase())).size).toBe(12)
    const graus = ['2', '3', '4', '5', '6', '7', '9', '11', '13']
    expect(Object.keys(p.porGrau).sort()).toEqual(graus.sort())
    expect(Object.values(p.porGrau)).not.toContain(p.tonica)
    const cores = [...p.porClasse, p.tonica, ...Object.values(p.porGrau)]
    const superficies = [p.braco.madeira, p.braco.traste, p.braco.corda]
    const minimoMarcador = Math.min(...cores.flatMap((c) => superficies.map((s) => razaoContraste(c, s))))
    const minimoTexto = Math.min(...cores.map((c) => razaoContraste(c, corDoTexto(c))))
    console.log(`${tema}: marcador ${minimoMarcador.toFixed(4)} (piso 3); texto ${minimoTexto.toFixed(4)} (piso 4,5)`)
    expect(minimoMarcador).toBeGreaterThanOrEqual(3)
    expect(minimoTexto).toBeGreaterThanOrEqual(4.5)
    expect(corDoGrau(p, '1')).toBe(p.tonica)
    for (const g of graus) {
      expect(corDoGrau(p, g)).toBe(p.porGrau[g])
      expect(corDoGrau(p, `bb${g}`)).toBe(p.porGrau[g])
      expect(corDoGrau(p, `#${g}`)).toBe(p.porGrau[g])
    }
    expect(() => corDoGrau(p, '15')).toThrow(/15/)
    expect(() => corDoGrau(p, 'x3')).toThrow(/x3/)
  })
})
