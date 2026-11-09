<script setup lang="ts">
import { watchEffect } from 'vue'
import BracoSvg from '@/components/BracoSvg.vue'
import PainelExibicao from '@/components/PainelExibicao.vue'
import PainelInstrumento from '@/components/PainelInstrumento.vue'
import PainelMetronomo from '@/components/PainelMetronomo.vue'
import PainelNotas from '@/components/PainelNotas.vue'
import { useSom } from '@/composables/useSom'
import type { Posicao } from '@/dominio/tipos'
import { useConfigStore } from '@/stores/config'
import { useMetronomoStore } from '@/stores/metronomo'

const config = useConfigStore()
const metro = useMetronomoStore()
const { tocarNota } = useSom()

// "sistema" fica a cargo do prefers-color-scheme do CSS; os outros fixam o tema.
watchEffect(() => {
  const raiz = document.documentElement
  if (config.tema === 'sistema') delete raiz.dataset.tema
  else raiz.dataset.tema = config.tema
})

function tocar(posicao: Posicao) {
  config.aoTocar(posicao)
  tocarNota(posicao.altura, config.quantizar).catch((erro: unknown) => console.error('falha ao tocar a nota', posicao, erro))
}
</script>

<template>
  <div class="app">
    <header>
      <h1>Mapa do braço</h1>
      <p>{{ config.afinacao.nome }} · {{ config.casas }} casas</p>
    </header>
    <main>
      <div class="braco">
        <BracoSvg
          :afinacao="config.afinacao"
          :casas="config.casas"
          :escolhas="config.escolhas"
          :soando="metro.soando"
          @tocar="tocar"
        />
      </div>
      <div class="paineis">
        <PainelNotas />
        <PainelMetronomo />
        <PainelInstrumento />
        <PainelExibicao />
      </div>
    </main>
  </div>
</template>

<style scoped>
.app {
  padding: 16px;
  max-width: 1400px;
  margin: 0 auto;
}
header {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 16px;
  margin-bottom: 12px;
}
h1 {
  font-size: 1.4rem;
  margin: 0;
}
header p {
  margin: 0;
  color: var(--texto-suave);
}
.braco {
  overflow-x: auto;
  margin-bottom: 16px;
}
.paineis {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr));
  gap: 16px;
  align-items: start;
}
</style>
