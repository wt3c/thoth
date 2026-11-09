/**
 * Contratos do domínio (ADR-056 a 061). TypeScript puro: sem DOM, sem áudio, sem Vue.
 *
 * Alteração aqui é mudança de contrato: commit na `feat/braco` e rebase das trilhas.
 */

/** Classe de altura: 0 = C (dó), 1 = C♯/D♭ … 11 = B (si). */
export type ClasseAltura = number

/** Altura absoluta em pitch MIDI: 60 = C4, 69 = A4 (440 Hz). */
export type Altura = number

export type Instrumento = 'baixo' | 'guitarra'

export interface Afinacao {
  readonly id: string
  readonly nome: string
  readonly instrumento: Instrumento
  /** Da corda mais grave para a mais aguda. */
  readonly cordas: readonly Altura[]
}

/** Uma casa do braço. `corda` 0 é a mais grave; `casa` 0 é a corda solta. */
export interface Posicao {
  readonly corda: number
  readonly casa: number
  readonly altura: Altura
  readonly classe: ClasseAltura
}

/** Grau grafado do padrão: `'1'`, `'b3'`, `'#4'`, `'bb7'`. Ré♯ e mi♭ são graus diferentes (ADR-061). */
export type Grau = string

export type TipoPadrao = 'escala' | 'acorde' | 'intervalo'

export interface Padrao {
  readonly id: string
  readonly nome: string
  readonly tipo: TipoPadrao
  /** O primeiro é sempre `'1'`, a tônica. */
  readonly graus: readonly Grau[]
}

export interface NotaDoPadrao {
  readonly classe: ClasseAltura
  readonly grau: Grau
  /** Nome grafado em cifra, coerente com a tônica e o grau: em F maior, o 4º grau é `Bb`, não `A#`. */
  readonly nome: string
}

export type Nomenclatura = 'cifra' | 'solfejo'
export type Acidente = 'sustenido' | 'bemol'

export interface OpcoesDeNome {
  readonly nomenclatura: Nomenclatura
  readonly acidente: Acidente
}

/** Cor em `#rrggbb`. */
export type Cor = string

export type IdTema = 'claro' | 'escuro' | 'daltonico'

export interface CoresDoBraco {
  readonly madeira: Cor
  readonly traste: Cor
  readonly corda: Cor
  readonly marcacao: Cor
}

export interface Paleta {
  readonly id: IdTema
  readonly braco: CoresDoBraco
  /** Uma cor por classe de altura (índice = classe). Fora do modo teoria. */
  readonly porClasse: readonly Cor[]
  /** Cor exclusiva da tônica no modo teoria. */
  readonly tonica: Cor
  /** Cor por número do grau, sem o acidente: chave `'2'` … `'7'` (e `'9'`, `'11'`, `'13'`). */
  readonly porGrau: Readonly<Record<string, Cor>>
}
