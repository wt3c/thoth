<script setup lang="ts">
/**
 * Metrônomo rápido (ADR-063): tocar, andamento e indicador sempre ao alcance no celular,
 * fixo no pé da tela enquanto o braço rola. Usa o mesmo store do painel completo.
 */
import { limitarBpm } from '@/som/config-metronomo'
import { useMetronomoStore } from '@/stores/metronomo'
import IndicadorDeTempos from './IndicadorDeTempos.vue'

const metro = useMetronomoStore()

function mudarBpm(passo: number) {
  metro
    .atualizar({ bpm: limitarBpm(metro.config.bpm + passo) })
    .catch((erro: unknown) => console.error('andamento recusado', erro))
}
</script>

<template>
  <div
    class="barra"
    role="region"
    aria-label="Metrônomo rápido"
  >
    <button
      type="button"
      class="tocar"
      :aria-pressed="metro.tocando"
      @click="metro.alternar()"
    >
      {{ metro.tocando ? '■' : '▶' }}<span class="rotulo">{{ metro.tocando ? 'Parar' : 'Tocar' }}</span>
    </button>
    <button
      type="button"
      data-acao="menos"
      aria-label="Diminuir andamento"
      @click="mudarBpm(-1)"
    >
      −
    </button>
    <span
      class="bpm"
      aria-live="polite"
    >{{ metro.config.bpm }}</span>
    <button
      type="button"
      data-acao="mais"
      aria-label="Aumentar andamento"
      @click="mudarBpm(1)"
    >
      +
    </button>
    <IndicadorDeTempos />
  </div>
</template>

<style scoped>
.barra {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px calc(8px + env(safe-area-inset-bottom));
  background: var(--superficie);
  border-top: 1px solid var(--borda);
  box-shadow: 0 -2px 8px rgb(0 0 0 / 12%);
}
.tocar {
  display: inline-flex;
  gap: 6px;
  align-items: center;
}
.bpm {
  min-width: 3ch;
  text-align: center;
  font-size: 1.2rem;
  font-variant-numeric: tabular-nums;
}
.barra :deep(.indicador) {
  flex: 1;
  justify-content: flex-end;
  gap: 4px;
}
.barra :deep(.tempo) {
  width: 12px;
  height: 12px;
}
.bpm::after {
  content: ' BPM';
  font-size: 0.75rem;
  color: var(--texto-suave);
}
</style>
