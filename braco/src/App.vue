<script setup lang="ts">
import { useMediaQuery } from '@vueuse/core'
import { computed, watchEffect } from 'vue'
import BarraMetronomo from '@/components/BarraMetronomo.vue'
import BracoSvg from '@/components/BracoSvg.vue'
import GuiaDeUso from '@/components/GuiaDeUso.vue'
import LegendaDoBraco from '@/components/LegendaDoBraco.vue'
import PainelExibicao from '@/components/PainelExibicao.vue'
import PainelInstrumento from '@/components/PainelInstrumento.vue'
import PainelMetronomo from '@/components/PainelMetronomo.vue'
import PainelNotas from '@/components/PainelNotas.vue'
import { useSom } from '@/composables/useSom'
import type { Posicao } from '@/dominio/tipos'
import { ligarPersistencia } from '@/persistencia/usePersistencia'
import { useConfigStore } from '@/stores/config'
import { useMetronomoStore } from '@/stores/metronomo'

const config = useConfigStore()
const metro = useMetronomoStore()
const { tocarNota } = useSom()
ligarPersistencia()

// ADR-063: celular em pé vê o braço na vertical, que cabe na largura e rola para baixo.
const emPe = useMediaQuery('(orientation: portrait) and (max-width: 640px)')
const orientacao = computed(() => (emPe.value ? 'vertical' : 'horizontal'))

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
      <a href="#como-usar">
        <svg
          viewBox="0 0 16 16"
          width="16"
          height="16"
          aria-hidden="true"
        >
          <circle
            cx="8"
            cy="8"
            r="7"
            fill="none"
            stroke="currentColor"
            stroke-width="1.5"
          />
          <path
            d="M6 6.2a2 2 0 1 1 2.8 1.8c-.5.3-.8.7-.8 1.3v.4"
            fill="none"
            stroke="currentColor"
            stroke-width="1.5"
            stroke-linecap="round"
          />
          <circle
            cx="8"
            cy="12"
            r="1"
            fill="currentColor"
          />
        </svg>
        Como usar
      </a>
    </header>
    <main>
      <div class="braco">
        <BracoSvg
          :afinacao="config.afinacao"
          :casas="config.casas"
          :escolhas="config.escolhas"
          :soando="metro.soando"
          :orientacao="orientacao"
          @tocar="tocar"
        />
      </div>
      <LegendaDoBraco />
      <div class="paineis">
        <PainelNotas />
        <PainelMetronomo />
        <PainelInstrumento />
        <PainelExibicao />
      </div>
      <GuiaDeUso />
    </main>
    <BarraMetronomo class="rapida" />
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
header a {
  margin-left: auto;
  color: var(--destaque);
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.braco {
  overflow-x: auto;
  margin-bottom: 16px;
}
.rapida {
  display: none;
}
/* Tela estreita ou baixa: o painel do metrônomo fica longe do braço, então a barra rápida
   acompanha a rolagem no pé da tela. */
@media (max-width: 640px), (max-height: 500px) {
  .app {
    padding-bottom: 96px;
  }
  .rapida {
    display: flex;
    position: fixed;
    inset: auto 0 0;
    z-index: 10;
  }
  header {
    margin-bottom: 8px;
  }
}
.paineis {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr));
  gap: 16px;
  align-items: start;
}
</style>
