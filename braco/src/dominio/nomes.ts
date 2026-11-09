import type { ClasseAltura, Nomenclatura, OpcoesDeNome } from './tipos'

const SUSTENIDOS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'] as const
const BEMOIS = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B'] as const
const SOLFEJO: Readonly<Record<string, string>> = { C: 'Dó', D: 'Ré', E: 'Mi', F: 'Fá', G: 'Sol', A: 'Lá', B: 'Si' }

/** Cifra ASCII por padrão; solfejo usa acidentes musicais para exibição. */
export function nomeDaClasse(classe: ClasseAltura, opcoes?: OpcoesDeNome): string {
  const nomes = opcoes?.acidente === 'bemol' ? BEMOIS : SUSTENIDOS
  const nome = nomes[((classe % 12) + 12) % 12] ?? ''
  return opcoes?.nomenclatura === 'solfejo' ? exibirNome(nome, 'solfejo') : nome
}

/** Preserva a letra e os acidentes, inclusive enarmonias e acidentes duplos. */
export function exibirNome(nomeCifraAscii: string, nomenclatura: Nomenclatura): string {
  const partes = /^([A-G])(#{1,2}|b{1,2})?$/.exec(nomeCifraAscii)
  if (!partes) throw new Error(`Nome de nota inválido: ${nomeCifraAscii}`)
  const letra = partes[1]!
  const acidente = partes[2] ?? ''
  const simbolos: Readonly<Record<string, string>> = { '': '', '#': '♯', '##': '𝄪', b: '♭', bb: '𝄫' }
  return (nomenclatura === 'solfejo' ? SOLFEJO[letra]! : letra) + simbolos[acidente]!
}
