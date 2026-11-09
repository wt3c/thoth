import type { ConfigMetronomo } from './tipos'

export const BPM_MIN = 30
export const BPM_MAX = 244

function exigir(condicao: boolean, campo: string, valor: unknown, faixa: string): void {
  if (!condicao) throw new RangeError(`metrônomo: ${campo} = ${String(valor)} fora de ${faixa}`)
}

const inteiroEntre = (v: number, min: number, max: number) => Number.isInteger(v) && v >= min && v <= max

/** Recusa configuração fora das faixas, em vez de prender em silêncio: valor inválido é erro de quem chamou. */
export function validarConfig(c: ConfigMetronomo): ConfigMetronomo {
  exigir(Number.isFinite(c.bpm) && c.bpm >= BPM_MIN && c.bpm <= BPM_MAX, 'bpm', c.bpm, `${BPM_MIN}–${BPM_MAX}`)
  exigir(inteiroEntre(c.temposPorCompasso, 1, 12), 'temposPorCompasso', c.temposPorCompasso, '1–12')
  exigir([1, 2, 3, 4].includes(c.subdivisao), 'subdivisao', c.subdivisao, '1–4')
  exigir(inteiroEntre(c.silencio.tocar, 1, 99), 'silencio.tocar', c.silencio.tocar, '1–99')
  exigir(inteiroEntre(c.silencio.silenciar, 1, 99), 'silencio.silenciar', c.silencio.silenciar, '1–99')
  exigir(Number.isFinite(c.volume) && c.volume >= 0 && c.volume <= 1, 'volume', c.volume, '0–1')
  exigir(inteiroEntre(c.contagemEntrada, 0, 2), 'contagemEntrada', c.contagemEntrada, '0–2')
  return c
}

/** Para as setas, o slider e o tap: aqui prender é o comportamento pedido, não um disfarce. */
export function limitarBpm(bpm: number): number {
  return Math.min(BPM_MAX, Math.max(BPM_MIN, Math.round(bpm)))
}
