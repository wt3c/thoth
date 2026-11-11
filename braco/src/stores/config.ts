import { usePreferredDark } from '@vueuse/core'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { afinacaoPadrao, afinacaoPorId, afinacoesDe } from '@/dominio/afinacoes'
import { PALETAS } from '@/dominio/cores'
import { PADROES } from '@/dominio/teoria'
import type { Acidente, ClasseAltura, Instrumento, Nomenclatura, Posicao } from '@/dominio/tipos'
import { TODAS_AS_CLASSES, type EscolhasDaVista, type Modo, type Rotulo } from '@/dominio/vista'
import { CASAS_MAX, CASAS_MIN, CORDAS, PREFERENCIAS_PADRAO, type Preferencias, type Tema } from '@/persistencia/preferencias'

export { CASAS_MAX, CASAS_MIN, CORDAS, type Tema }

export type PreferenciasDaVista = Omit<Preferencias, 'metronomo'>

const P = PREFERENCIAS_PADRAO

/** Escolhas serializáveis do usuário; o padrão e a persistência (S8) vêm de `persistencia/preferencias`. */
export const useConfigStore = defineStore('config', () => {
  const instrumento = ref<Instrumento>(P.instrumento)
  const numCordas = ref(P.numCordas)
  const afinacaoId = ref(P.afinacaoId)
  const casas = ref(P.casas)
  const modo = ref<Modo>(P.modo)
  const filtro = ref<ClasseAltura[]>([...P.filtro])
  const selecionada = ref<ClasseAltura | null>(P.selecionada)
  /** O lugar tocado no modo notas, ponto de partida das oitavas; não é persistido. */
  const tocada = ref<{ corda: number; casa: number } | null>(null)
  const tonica = ref<ClasseAltura | null>(P.tonica)
  const padraoId = ref<string | null>(P.padraoId)
  const rotulo = ref<Rotulo>(P.rotulo)
  const nomenclatura = ref<Nomenclatura>(P.nomenclatura)
  const acidente = ref<Acidente>(P.acidente)
  const tema = ref<Tema>(P.tema)
  const daltonico = ref(P.daltonico)
  const quantizar = ref(P.quantizar)

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

  /** Derivada: vale só enquanto o lugar tocado ainda existe e ainda é a nota selecionada. */
  const referencia = computed<Posicao | null>(() => {
    const t = tocada.value
    const classe = selecionada.value
    if (t === null || classe === null) return null
    const solta = afinacao.value.cordas[t.corda]
    if (solta === undefined || t.casa > casas.value) return null
    const altura = solta + t.casa
    return altura % 12 === classe ? { ...t, altura, classe } : null
  })

  const escolhas = computed<EscolhasDaVista>(() => ({
    modo: modo.value,
    filtro: filtro.value,
    selecionada: selecionada.value,
    referencia: referencia.value,
    tonica: tonica.value,
    padrao: padrao.value,
    rotulo: rotulo.value,
    nome: { nomenclatura: nomenclatura.value, acidente: acidente.value },
    paleta: PALETAS[daltonico.value ? 'daltonico' : temaEfetivo.value],
  }))

  const preferencias = computed<PreferenciasDaVista>(() => ({
    instrumento: instrumento.value,
    numCordas: numCordas.value,
    afinacaoId: afinacaoId.value,
    casas: casas.value,
    modo: modo.value,
    filtro: filtro.value,
    selecionada: selecionada.value,
    tonica: tonica.value,
    padraoId: padraoId.value,
    rotulo: rotulo.value,
    nomenclatura: nomenclatura.value,
    acidente: acidente.value,
    tema: tema.value,
    daltonico: daltonico.value,
    quantizar: quantizar.value,
  }))

  /** Recebe preferências já validadas e coerentes (`carregar`). */
  function aplicar(p: PreferenciasDaVista) {
    instrumento.value = p.instrumento
    numCordas.value = p.numCordas
    afinacaoId.value = p.afinacaoId
    casas.value = p.casas
    modo.value = p.modo
    filtro.value = [...p.filtro]
    selecionada.value = p.selecionada
    tocada.value = null
    // Preferência salva antes de a nota do modo notas virar tônica: a nota faz esse papel.
    tonica.value = p.tonica ?? p.selecionada
    padraoId.value = p.padraoId
    rotulo.value = p.rotulo
    nomenclatura.value = p.nomenclatura
    acidente.value = p.acidente
    tema.value = p.tema
    daltonico.value = p.daltonico
    quantizar.value = p.quantizar
  }

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
    else if (selecionada.value === p.classe && tocada.value?.corda === p.corda && tocada.value.casa === p.casa) {
      selecionada.value = null
      tocada.value = null
    } else {
      selecionada.value = p.classe
      tocada.value = { corda: p.corda, casa: p.casa }
      // A escolha feita no modo notas vale na teoria: vira a tônica.
      tonica.value = p.classe
    }
  }

  /** Sem tônica a teoria cai no filtro do modo notas (`vista`), então limpar a teoria limpa ele também. */
  function limparTeoria() {
    tonica.value = null
    mostrarClasses([])
  }

  function mostrarClasses(classes: readonly ClasseAltura[]) {
    filtro.value = TODAS_AS_CLASSES.filter((c) => classes.includes(c))
    // A selecionada aparece mesmo fora do filtro; esconder a classe dela tem de soltá-la.
    if (selecionada.value !== null && !classes.includes(selecionada.value)) {
      selecionada.value = null
      tocada.value = null
    }
  }

  function alternarClasse(c: ClasseAltura) {
    if (filtro.value.includes(c)) mostrarClasses(filtro.value.filter((x) => x !== c))
    else {
      mostrarClasses([...filtro.value, c])
      // O braço abre limpo: escolher a nota é ligá-la aqui, e essa escolha vale na teoria.
      tonica.value = c
    }
  }

  return {
    instrumento, numCordas, afinacaoId, casas, modo, filtro, selecionada, tonica, padraoId, rotulo,
    nomenclatura, acidente, tema, daltonico, quantizar, temaEfetivo, afinacao, afinacoesDisponiveis, escolhas, preferencias,
    escolherNumCordas, escolherInstrumento, escolherCasas, aoTocar, mostrarClasses, alternarClasse, limparTeoria, aplicar,
  }
})
