<script setup lang="ts">
/** Um ponto por tempo do compasso; acende o tempo que soou. Usado no painel e na barra rápida. */
import { computed } from 'vue'
import { useMetronomoStore } from '@/stores/metronomo'

const metro = useMetronomoStore()

const tempos = computed(() => Array.from({ length: metro.config.temposPorCompasso }, (_, i) => i + 1))
const acesa = computed(() => metro.pulso?.batida ?? null)
const estado = computed(() => {
  const p = metro.pulso
  if (!p) return ''
  if (p.contagem) return 'Contagem'
  if (p.silenciado) return 'Compasso em silêncio'
  return `Compasso ${p.compasso + 1}`
})
</script>

<template>
  <div
    class="indicador"
    role="status"
    :aria-label="estado || 'Metrônomo parado'"
  >
    <span
      v-for="t in tempos"
      :key="t"
      class="tempo"
      :class="{ aceso: acesa === t, acento: t === 1 && metro.config.acentoNoUm, mudo: metro.pulso?.silenciado, contagem: metro.pulso?.contagem }"
    />
  </div>
</template>

<style scoped>
.indicador {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.tempo {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid var(--borda);
  transition: background 60ms linear;
}
.tempo.acento {
  border-color: var(--destaque);
}
.tempo.aceso {
  background: var(--destaque);
  border-color: var(--destaque);
}
.tempo.aceso.mudo {
  background: transparent;
  border-style: dashed;
}
.tempo.aceso.contagem {
  background: var(--texto-suave);
}
</style>
