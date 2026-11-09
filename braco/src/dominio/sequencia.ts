import { gerarBraco } from './braco'
import { notasDoPadrao } from './teoria'
import type { Afinacao, Altura, ClasseAltura, Padrao } from './tipos'
import { vistaDaNota, type EscolhasDaVista } from './vista'

const CROMATICA = Array.from({ length: 12 }, (_, i) => i)

/**
 * As alturas que a sequência toca (S6): da tônica mais grave do braço, cada grau acima do
 * anterior. Escala e acorde que cabem numa oitava terminam na tônica de cima; intervalo, não.
 */
export function alturasDaSequencia(afinacao: Afinacao, casas: number, tonica: ClasseAltura, padrao: Padrao | null): Altura[] {
  const base = Math.min(...gerarBraco(afinacao, casas).filter((p) => p.classe === tonica).map((p) => p.altura))
  if (!Number.isFinite(base)) throw new Error(`a tônica ${tonica} não está no braço`)
  const classes = padrao === null ? CROMATICA.map((i) => (tonica + i) % 12) : notasDoPadrao(tonica, padrao).map((n) => n.classe)
  const deslocamentos: number[] = []
  for (const classe of classes) {
    let d = (((classe - tonica) % 12) + 12) % 12
    const anterior = deslocamentos.at(-1)
    while (anterior !== undefined && d <= anterior) d += 12
    deslocamentos.push(d)
  }
  const ultimo = deslocamentos.at(-1) ?? 0
  if (padrao?.tipo !== 'intervalo' && ultimo < 12) deslocamentos.push(12)
  return deslocamentos.map((d) => base + d)
}

/**
 * As alturas acesas no braço, para tocar no metrônomo: a mesma regra de visibilidade do
 * desenho (`vistaDaNota`), cada altura uma vez, da mais grave à mais aguda.
 */
export function alturasVisiveis(afinacao: Afinacao, casas: number, escolhas: EscolhasDaVista): Altura[] {
  const acesas = gerarBraco(afinacao, casas).filter((p) => vistaDaNota(p, escolhas).visivel)
  return [...new Set(acesas.map((p) => p.altura))].sort((a, b) => a - b)
}
