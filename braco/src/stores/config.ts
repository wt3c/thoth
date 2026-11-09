import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import AFINACOES from '@/dominio/afinacoes.json'
import type { Afinacao } from '@/dominio/tipos'

const PRESETS = AFINACOES as readonly Afinacao[]

/** Configuração serializável do braço. Persistência em URL e localStorage chega na etapa 5 (S8). */
export const useConfigStore = defineStore('config', () => {
  const afinacaoId = ref('baixo-4')
  const casas = ref(12)

  const afinacao = computed(() => {
    const achada = PRESETS.find((a) => a.id === afinacaoId.value)
    if (!achada) throw new Error(`afinação desconhecida: ${afinacaoId.value}`)
    return achada
  })

  return { afinacaoId, casas, afinacao }
})
