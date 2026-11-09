import { defineStore } from 'pinia'
import { ref } from 'vue'
import { obterMotor, type Motor } from '@/composables/motor'
import type { Altura } from '@/dominio/tipos'
import { CONFIG_PADRAO } from '@/som/agendador'
import { validarConfig } from '@/som/config-metronomo'
import { TapTempo } from '@/som/tap-tempo'
import type { ConfigMetronomo, Pulso } from '@/som/tipos'

/** Fração da duração do pulso que a nota da sequência ocupa: o respiro separa os ataques. */
const LEGATO = 0.9

/** Estado serializável e visual do metrônomo; o metrônomo em si fica no motor, fora da reatividade. */
export const useMetronomoStore = defineStore('metronomo', () => {
  const config = ref<ConfigMetronomo>(CONFIG_PADRAO)
  const tocando = ref(false)
  const pulso = ref<Pulso | null>(null)
  const sequenciaAtiva = ref(false)
  const soando = ref<Altura | null>(null)
  const tapTempo = new TapTempo()
  let alturas: readonly Altura[] = []
  let inscrito: Motor | null = null

  async function motor(): Promise<Motor> {
    const m = await obterMotor()
    if (inscrito !== m) {
      inscrito = m
      m.metronomo.configurar(config.value)
      m.metronomo.aoPulso((p) => {
        pulso.value = p
        const indice = m.sequencia.indiceDoPulso(p)
        soando.value = indice === null ? null : (alturas[indice] ?? null)
      })
    }
    return m
  }

  async function atualizar(parcial: Partial<ConfigMetronomo>) {
    const nova = validarConfig({ ...config.value, ...parcial })
    config.value = nova
    if (inscrito) inscrito.metronomo.configurar(nova)
  }

  async function iniciar() {
    const m = await motor()
    m.metronomo.iniciar()
    tocando.value = true
  }

  async function parar() {
    const m = await motor()
    pararSequencia()
    m.metronomo.parar()
    tocando.value = false
    pulso.value = null
  }

  async function alternar() {
    await (tocando.value ? parar() : iniciar())
  }

  async function tap(agoraMs: number) {
    const bpm = tapTempo.tocar(agoraMs)
    if (bpm !== null) await atualizar({ bpm })
  }

  /** S6: as notas soam nos pulsos, agendadas junto com os cliques. */
  async function tocarSequencia(novas: readonly Altura[]) {
    const m = await motor()
    alturas = novas
    m.sequencia.iniciar(novas, (60 / config.value.bpm / config.value.subdivisao) * LEGATO)
    sequenciaAtiva.value = true
    if (!tocando.value) await iniciar()
  }

  function pararSequencia() {
    inscrito?.sequencia.parar()
    sequenciaAtiva.value = false
    soando.value = null
  }

  return { config, tocando, pulso, sequenciaAtiva, soando, atualizar, alternar, tap, tocarSequencia, pararSequencia }
})
