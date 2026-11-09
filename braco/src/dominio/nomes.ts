import type { ClasseAltura } from './tipos'

const SUSTENIDOS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'] as const

/** Nome da classe em cifra com sustenido. A Trilha A acrescenta solfejo, bemol e grafia por grau (S3). */
export function nomeDaClasse(classe: ClasseAltura): string {
  return SUSTENIDOS[((classe % 12) + 12) % 12] ?? ''
}
