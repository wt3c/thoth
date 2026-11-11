/**
 * Esquema das preferências salvas (S8, ADR-062). Um único formato de texto — o de uma query
 * string — serve à URL e ao localStorage. Só se escreve o que difere do padrão; ao ler, a URL
 * vence o armazenado, que vence o padrão.
 *
 * Valor ruim vindo de fora (link antigo, edição à mão) não derruba a página: o campo é
 * recusado, o resto vale, e cada recusa volta em `rejeitados` para quem chamou registrar.
 */
import { afinacaoPadrao, afinacaoPorId } from '@/dominio/afinacoes'
import { PADROES } from '@/dominio/teoria'
import type { Acidente, ClasseAltura, Instrumento, Nomenclatura } from '@/dominio/tipos'
import { TODAS_AS_CLASSES, type Modo, type Rotulo } from '@/dominio/vista'
import { CONFIG_PADRAO } from '@/som/agendador'
import { BPM_MAX, BPM_MIN } from '@/som/config-metronomo'
import type { ConfigMetronomo, SomDoClique, Subdivisao } from '@/som/tipos'

export const VERSAO = 1

export type Tema = 'sistema' | 'claro' | 'escuro' | 'matte-black'

export const CORDAS: Readonly<Record<Instrumento, readonly number[]>> = { baixo: [4, 5, 6, 7], guitarra: [6] }
export const CASAS_MIN = 12
export const CASAS_MAX = 24
/** O braço abre com 21 casas, a pedido do usuário (emenda do ADR-062). */
export const CASAS_PADRAO = 21

export interface Preferencias {
  readonly instrumento: Instrumento
  readonly numCordas: number
  readonly afinacaoId: string
  readonly casas: number
  readonly modo: Modo
  readonly filtro: readonly ClasseAltura[]
  readonly selecionada: ClasseAltura | null
  readonly tonica: ClasseAltura | null
  readonly padraoId: string | null
  readonly rotulo: Rotulo
  readonly nomenclatura: Nomenclatura
  readonly acidente: Acidente
  readonly tema: Tema
  readonly daltonico: boolean
  readonly quantizar: boolean
  readonly metronomo: ConfigMetronomo
}

export const PREFERENCIAS_PADRAO: Preferencias = {
  instrumento: 'baixo',
  numCordas: 4,
  afinacaoId: 'baixo-4',
  casas: CASAS_PADRAO,
  modo: 'notas',
  filtro: [],
  selecionada: null,
  tonica: null,
  padraoId: null,
  rotulo: 'nome',
  nomenclatura: 'cifra',
  acidente: 'sustenido',
  tema: 'sistema',
  daltonico: false,
  quantizar: false,
  metronomo: CONFIG_PADRAO,
}

type Mutavel<T> = { -readonly [K in keyof T]: T[K] }

/** `undefined` = texto inválido para o campo. */
type Leitor<T> = (texto: string) => T | undefined

interface Campo {
  readonly chave: string
  escrever(p: Preferencias): string
  /** Devolve `false` se o texto não serve. */
  aplicar(texto: string, p: Mutavel<Preferencias>): boolean
}

function campo<T>(
  chave: string,
  ler: Leitor<T>,
  paraTexto: (v: T) => string,
  obter: (p: Preferencias) => T,
  por: (p: Mutavel<Preferencias>, v: T) => void,
): Campo {
  return {
    chave,
    escrever: (p) => paraTexto(obter(p)),
    aplicar(texto, p) {
      const v = ler(texto)
      if (v === undefined) return false
      por(p, v)
      return true
    },
  }
}

const inteiro =
  (min: number, max: number): Leitor<number> =>
  (t) => {
    if (!/^\d+$/.test(t)) return undefined
    const n = Number(t)
    return n >= min && n <= max ? n : undefined
  }
const umDe =
  <T extends string>(...valores: readonly T[]): Leitor<T> =>
  (t) =>
    (valores as readonly string[]).includes(t) ? (t as T) : undefined
const booleano: Leitor<boolean> = (t) => (t === '1' ? true : t === '0' ? false : undefined)
const bit = (b: boolean) => (b ? '1' : '0')
const classeOuNada: Leitor<ClasseAltura | null> = (t) => (t === '' ? null : inteiro(0, 11)(t))
const classeOuVazio = (c: ClasseAltura | null) => (c === null ? '' : String(c))

/** Filtro como dígitos hexadecimais em ordem cromática: "047b" = C, E, G, B. */
const lerFiltro: Leitor<ClasseAltura[]> = (t) => {
  if (!/^[0-9ab]*$/.test(t)) return undefined
  const classes = [...t].map((d) => parseInt(d, 16))
  if (new Set(classes).size !== classes.length) return undefined
  return TODAS_AS_CLASSES.filter((c) => classes.includes(c))
}
const escreverFiltro = (f: readonly ClasseAltura[]) => f.map((c) => c.toString(16)).join('')

const lerAfinacao: Leitor<string> = (t) => {
  try {
    return afinacaoPorId(t).id
  } catch {
    return undefined
  }
}
const lerPadrao: Leitor<string | null> = (t) => (t === '' ? null : PADROES.some((p) => p.id === t) ? t : undefined)

const lerVolume: Leitor<number> = (t) => {
  const v = Number(t)
  return t !== '' && Number.isFinite(v) && v >= 0 && v <= 1 ? v : undefined
}

/** Silêncio como "ativo:tocar:silenciar", para não perder as contagens quando desligado. */
const lerSilencio: Leitor<ConfigMetronomo['silencio']> = (t) => {
  const partes = t.split(':')
  if (partes.length !== 3) return undefined
  const [a, b, c] = partes as [string, string, string]
  const ativo = booleano(a)
  const tocar = inteiro(1, 99)(b)
  const silenciar = inteiro(1, 99)(c)
  if (ativo === undefined || tocar === undefined || silenciar === undefined) return undefined
  return { ativo, tocar, silenciar }
}

const metronomo = <K extends keyof ConfigMetronomo>(p: Mutavel<Preferencias>, k: K, v: ConfigMetronomo[K]) => {
  p.metronomo = { ...p.metronomo, [k]: v }
}

const CAMPOS: readonly Campo[] = [
  campo('instrumento', umDe<Instrumento>('baixo', 'guitarra'), String, (p) => p.instrumento, (p, v) => (p.instrumento = v)),
  campo('cordas', inteiro(1, 12), String, (p) => p.numCordas, (p, v) => (p.numCordas = v)),
  campo('afinacao', lerAfinacao, String, (p) => p.afinacaoId, (p, v) => (p.afinacaoId = v)),
  campo('casas', inteiro(CASAS_MIN, CASAS_MAX), String, (p) => p.casas, (p, v) => (p.casas = v)),
  campo('modo', umDe<Modo>('notas', 'teoria'), String, (p) => p.modo, (p, v) => (p.modo = v)),
  campo('filtro', lerFiltro, escreverFiltro, (p) => p.filtro, (p, v) => (p.filtro = v)),
  campo('nota', classeOuNada, classeOuVazio, (p) => p.selecionada, (p, v) => (p.selecionada = v)),
  campo('tonica', classeOuNada, classeOuVazio, (p) => p.tonica, (p, v) => (p.tonica = v)),
  campo('padrao', lerPadrao, (v) => v ?? '', (p) => p.padraoId, (p, v) => (p.padraoId = v)),
  campo('rotulo', umDe<Rotulo>('nome', 'grau'), String, (p) => p.rotulo, (p, v) => (p.rotulo = v)),
  campo('nomes', umDe<Nomenclatura>('cifra', 'solfejo'), String, (p) => p.nomenclatura, (p, v) => (p.nomenclatura = v)),
  campo('acidente', umDe<Acidente>('sustenido', 'bemol'), String, (p) => p.acidente, (p, v) => (p.acidente = v)),
  campo('tema', umDe<Tema>('sistema', 'claro', 'escuro', 'matte-black'), String, (p) => p.tema, (p, v) => (p.tema = v)),
  campo('daltonico', booleano, bit, (p) => p.daltonico, (p, v) => (p.daltonico = v)),
  campo('quantizar', booleano, bit, (p) => p.quantizar, (p, v) => (p.quantizar = v)),
  campo('bpm', inteiro(BPM_MIN, BPM_MAX), String, (p) => p.metronomo.bpm, (p, v) => metronomo(p, 'bpm', v)),
  campo('tempos', inteiro(1, 12), String, (p) => p.metronomo.temposPorCompasso, (p, v) => metronomo(p, 'temposPorCompasso', v)),
  campo('sub', inteiro(1, 4), String, (p) => p.metronomo.subdivisao, (p, v) => metronomo(p, 'subdivisao', v as Subdivisao)),
  campo('acento', booleano, bit, (p) => p.metronomo.acentoNoUm, (p, v) => metronomo(p, 'acentoNoUm', v)),
  campo(
    'silencio',
    lerSilencio,
    (s) => `${bit(s.ativo)}:${s.tocar}:${s.silenciar}`,
    (p) => p.metronomo.silencio,
    (p, v) => metronomo(p, 'silencio', v),
  ),
  campo('volume', lerVolume, String, (p) => p.metronomo.volume, (p, v) => metronomo(p, 'volume', v)),
  campo('som', umDe<SomDoClique>('eletronico', 'madeira', 'bipe'), String, (p) => p.metronomo.som, (p, v) => metronomo(p, 'som', v)),
  campo('contagem', inteiro(0, 2), String, (p) => p.metronomo.contagemEntrada, (p, v) => metronomo(p, 'contagemEntrada', v)),
]

/** Texto de query string sem o `?`, com a versão e só os campos diferentes do padrão. */
export function escrever(p: Preferencias): string {
  const params = new URLSearchParams({ v: String(VERSAO) })
  for (const c of CAMPOS) {
    const texto = c.escrever(p)
    if (texto !== c.escrever(PREFERENCIAS_PADRAO)) params.set(c.chave, texto)
  }
  return params.toString()
}

function aplicar(origem: 'url' | 'armazenado', texto: string, p: Mutavel<Preferencias>, rejeitados: string[]) {
  const params = new URLSearchParams(texto)
  const versao = params.get('v')
  // Na URL a versão pode faltar (link digitado à mão); no armazenado, que só nós escrevemos, não.
  if ((versao ?? (origem === 'url' ? String(VERSAO) : null)) !== String(VERSAO)) {
    rejeitados.push(`${origem}: versão ${versao ?? 'ausente'}`)
    return
  }
  for (const c of CAMPOS) {
    const valor = params.get(c.chave)
    if (valor !== null && !c.aplicar(valor, p)) rejeitados.push(`${origem}: ${c.chave}=${valor}`)
  }
}

/** Instrumento, cordas e afinação vêm de campos separados; aqui eles são postos de acordo. */
function tornarCoerente(p: Mutavel<Preferencias>, rejeitados: string[]) {
  const possiveis = CORDAS[p.instrumento]
  if (!possiveis.includes(p.numCordas)) {
    rejeitados.push(`cordas=${p.numCordas} não serve para ${p.instrumento}`)
    p.numCordas = possiveis[0] ?? PREFERENCIAS_PADRAO.numCordas
    p.afinacaoId = afinacaoPadrao(p.instrumento, p.numCordas).id
  }
  const afinacao = afinacaoPorId(p.afinacaoId)
  if (afinacao.instrumento !== p.instrumento || afinacao.cordas.length !== p.numCordas) {
    rejeitados.push(`afinacao=${p.afinacaoId} não serve para ${p.instrumento} de ${p.numCordas} cordas`)
    p.afinacaoId = afinacaoPadrao(p.instrumento, p.numCordas).id
  }
}

export function carregar(url: string, armazenado: string | null): { preferencias: Preferencias; rejeitados: string[] } {
  const p: Mutavel<Preferencias> = { ...PREFERENCIAS_PADRAO }
  const rejeitados: string[] = []
  if (armazenado !== null) aplicar('armazenado', armazenado, p, rejeitados)
  if (url.replace(/^\?/, '') !== '') aplicar('url', url, p, rejeitados)
  tornarCoerente(p, rejeitados)
  return { preferencias: p, rejeitados }
}
