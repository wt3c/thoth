import { usePreferredDark } from '@vueuse/core'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { afinacaoPadrao, afinacaoPorId, afinacoesDe } from '@/dominio/afinacoes'
import { PALETAS } from '@/dominio/cores'
import { PADROES } from '@/dominio/teoria'
import type { Acidente, ClasseAltura, Instrumento, Nomenclatura, Posicao } from '@/dominio/tipos'
import { TODAS_AS_CLASSES, type EscolhasDaVista, type Modo, type Rotulo } from '@/dominio/vista'

export type Tema = 'sistema' | 'claro' | 'escuro'

export const CORDAS: Readonly<Record<Instrumento, readonly number[]>> = { baixo: [4, 5, 6, 7], guitarra: [6] }
export const CASAS_MIN = 12
export const CASAS_MAX = 24

/** Escolhas serializáveis do usuário. Persistência em URL e localStorage: etapa 5 (S8). */
export const useConfigStore = defineStore('config', () => {
  const instrumento = ref<Instrumento>('baixo')
  const numCordas = ref(4)
  const afinacaoId = ref('baixo-4')
  const casas = ref(CASAS_MIN)
  const modo = ref<Modo>('notas')
  const filtro = ref<ClasseAltura[]>([...TODAS_AS_CLASSES])
  const selecionada = ref<ClasseAltura | null>(null)
  const tonica = ref<ClasseAltura | null>(null)
  const padraoId = ref<string | null>(null)
  const rotulo = ref<Rotulo>('nome')
  const nomenclatura = ref<Nomenclatura>('cifra')
  const acidente = ref<Acidente>('sustenido')
  const tema = ref<Tema>('sistema')
  const daltonico = ref(false)
  const quantizar = ref(false)

  const prefereEscuro = usePreferredDark()
  const temaEfetivo = computed(() => (tema.value === 'sistema' ? (prefereEscuro.value ? 'escuro' : 'claro') : tema.value))

  const afinacao = computed(() => afinacaoPorId(afinacaoId.value))
  const afinacoesDisponiveis = computed(() => afinacoesDe(instrumento.value, numCordas.value))
  const padrao = computed(() => {
    if (padraoId.value === null) return null
    const achado = PADROES.find((p) => p.id === padraoId.value)
    if (!achado) throw new Error(`Padrão desconhecido: ${padraoId.value}`)
    return achado
  })

  const escolhas = computed<EscolhasDaVista>(() => ({
    modo: modo.value,
    filtro: filtro.value,
    selecionada: selecionada.value,
    tonica: tonica.value,
    padrao: padrao.value,
    rotulo: rotulo.value,
    nome: { nomenclatura: nomenclatura.value, acidente: acidente.value },
    paleta: PALETAS[daltonico.value ? 'daltonico' : temaEfetivo.value],
  }))

  function escolherNumCordas(n: number) {
    if (!CORDAS[instrumento.value].includes(n)) throw new RangeError(`${instrumento.value} não tem ${n} cordas`)
    numCordas.value = n
    afinacaoId.value = afinacaoPadrao(instrumento.value, n).id
  }

  function escolherInstrumento(novo: Instrumento) {
    instrumento.value = novo
    escolherNumCordas(CORDAS[novo][0] ?? 0)
  }

  function escolherCasas(n: number) {
    if (!Number.isInteger(n) || n < CASAS_MIN || n > CASAS_MAX) throw new RangeError(`casas fora de ${CASAS_MIN}–${CASAS_MAX}: ${n}`)
    casas.value = n
  }

  function aoTocar(p: Posicao) {
    if (modo.value === 'teoria') tonica.value = p.classe
    else selecionada.value = selecionada.value === p.classe ? null : p.classe
  }

  function mostrarClasses(classes: readonly ClasseAltura[]) {
    filtro.value = TODAS_AS_CLASSES.filter((c) => classes.includes(c))
  }

  function alternarClasse(c: ClasseAltura) {
    mostrarClasses(filtro.value.includes(c) ? filtro.value.filter((x) => x !== c) : [...filtro.value, c])
  }

  return {
    instrumento, numCordas, afinacaoId, casas, modo, filtro, selecionada, tonica, padraoId, rotulo,
    nomenclatura, acidente, tema, daltonico, quantizar, temaEfetivo, afinacao, afinacoesDisponiveis, escolhas,
    escolherNumCordas, escolherInstrumento, escolherCasas, aoTocar, mostrarClasses, alternarClasse,
  }
})
