import { nomeDaClasse } from './nomes'
import type { Acidente, ClasseAltura, Grau, NotaDoPadrao, Padrao, TipoPadrao } from './tipos'

function catalogar(tipo: TipoPadrao, entradas: readonly (readonly [string, string, string])[]): Padrao[] {
  return entradas.map(([id, nome, graus]) => ({ id: `${tipo}-${id}`, nome, tipo, graus: graus.split(' ') }))
}

/** Menor melódica ascendente; na descida clássica usa-se a menor natural. */
export const PADROES: readonly Padrao[] = [
  ...catalogar('escala', [
    ['maior', 'Maior', '1 2 3 4 5 6 7'],
    ['menor-natural', 'Menor natural', '1 2 b3 4 5 b6 b7'],
    ['menor-harmonica', 'Menor harmônica', '1 2 b3 4 5 b6 7'],
    ['menor-melodica', 'Menor melódica (ascendente)', '1 2 b3 4 5 6 7'],
    ['pentatonica-maior', 'Pentatônica maior', '1 2 3 5 6'],
    ['pentatonica-menor', 'Pentatônica menor', '1 b3 4 5 b7'],
    ['blues', 'Blues', '1 b3 4 #4 5 b7'],
    ['jonio', 'Jônio', '1 2 3 4 5 6 7'],
    ['dorico', 'Dórico', '1 2 b3 4 5 6 b7'],
    ['frigio', 'Frígio', '1 b2 b3 4 5 b6 b7'],
    ['lidio', 'Lídio', '1 2 3 #4 5 6 7'],
    ['mixolidio', 'Mixolídio', '1 2 3 4 5 6 b7'],
    ['eolio', 'Eólio', '1 2 b3 4 5 b6 b7'],
    ['locrio', 'Lócrio', '1 b2 b3 4 b5 b6 b7'],
  ]),
  ...catalogar('acorde', [
    ['maior', 'Maior', '1 3 5'], ['menor', 'Menor', '1 b3 5'],
    ['diminuto', 'Diminuto', '1 b3 b5'], ['aumentado', 'Aumentado', '1 3 #5'],
    ['sus2', 'Sus2', '1 2 5'], ['sus4', 'Sus4', '1 4 5'],
    ['7M', '7M', '1 3 5 7'], ['7', '7', '1 3 5 b7'], ['m7', 'm7', '1 b3 5 b7'],
    ['m7b5', 'm7b5 (meio diminuto)', '1 b3 b5 b7'], ['°7', '°7 (diminuto)', '1 b3 b5 bb7'],
    ['m7M', 'm7M', '1 b3 5 7'], ['add9', 'Add9', '1 3 5 9'],
    ['6', '6', '1 3 5 6'], ['m6', 'm6', '1 b3 5 6'],
  ]),
  ...catalogar('intervalo', [
    ['unissono', 'Uníssono', '1 1'], ['segunda-menor', 'Segunda menor', '1 b2'],
    ['segunda-maior', 'Segunda maior', '1 2'], ['terca-menor', 'Terça menor', '1 b3'],
    ['terca-maior', 'Terça maior', '1 3'], ['quarta-justa', 'Quarta justa', '1 4'],
    ['tritono', 'Trítono (quarta aumentada)', '1 #4'], ['quinta-justa', 'Quinta justa', '1 5'],
    ['sexta-menor', 'Sexta menor', '1 b6'], ['sexta-maior', 'Sexta maior', '1 6'],
    ['setima-menor', 'Sétima menor', '1 b7'], ['setima-maior', 'Sétima maior', '1 7'],
    ['oitava', 'Oitava', '1 8'],
  ]),
]

const LETRAS = ['C', 'D', 'E', 'F', 'G', 'A', 'B'] as const
const NATURAIS = [0, 2, 4, 5, 7, 9, 11] as const
const CROMATICOS: readonly Grau[] = ['1', 'b2', '2', 'b3', '3', '4', '#4', '5', 'b6', '6', 'b7', '7']
const modulo = (valor: number, base: number) => ((valor % base) + base) % base

function decomporGrau(grau: Grau): { indice: number; semitons: number } {
  const partes = /^(#{1,2}|b{1,2})?([1-9]\d*)$/.exec(grau)
  if (!partes) throw new Error(`Grau inválido: ${grau}`)
  const numero = Number(partes[2])
  if (!Number.isSafeInteger(numero)) throw new Error(`Grau inválido: ${grau}`)
  const indice = (numero - 1) % 7
  const acidente = partes[1] ?? ''
  const alteracao = acidente.length * (acidente.startsWith('b') ? -1 : 1)
  return { indice, semitons: NATURAIS[indice]! + alteracao }
}

/** A letra vem do grau diatônico; o acidente ajusta a altura, sem respelling enarmônico. */
export function notasDoPadrao(
  tonica: ClasseAltura, padrao: Padrao, acidenteDaTonica: Acidente = 'sustenido',
): NotaDoPadrao[] {
  const nomeTonica = nomeDaClasse(tonica, { nomenclatura: 'cifra', acidente: acidenteDaTonica })
  const indiceTonica = LETRAS.findIndex((letra) => letra === nomeTonica[0])
  if (indiceTonica < 0) throw new Error(`Tônica inválida: ${tonica}`)
  return padrao.graus.map((grau) => {
    const { indice, semitons } = decomporGrau(grau)
    const indiceLetra = (indiceTonica + indice) % 7
    const classe = modulo(tonica + semitons, 12)
    const diferenca = modulo(classe - NATURAIS[indiceLetra]! + 6, 12) - 6
    const acidentes = diferenca < 0 ? 'b'.repeat(-diferenca) : '#'.repeat(diferenca)
    return { classe, grau, nome: LETRAS[indiceLetra]! + acidentes }
  })
}

export function grauCromatico(tonica: ClasseAltura, classe: ClasseAltura): Grau {
  return CROMATICOS[modulo(classe - tonica, 12)]!
}

export function grauNoPadrao(tonica: ClasseAltura, classe: ClasseAltura, padrao: Padrao): Grau | null {
  return notasDoPadrao(tonica, padrao).find((nota) => nota.classe === modulo(classe, 12))?.grau ?? null
}
