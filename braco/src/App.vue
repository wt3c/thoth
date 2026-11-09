<script setup lang="ts">
import BracoSvg from '@/components/BracoSvg.vue'
import { useSom } from '@/composables/useSom'
import { useConfigStore } from '@/stores/config'
import type { Posicao } from '@/dominio/tipos'

const config = useConfigStore()
const { tocarNota } = useSom()

function tocar(posicao: Posicao) {
  tocarNota(posicao.altura).catch((erro: unknown) => console.error('falha ao tocar a nota', posicao, erro))
}
</script>

<template>
  <main class="app">
    <h1>Mapa do braço</h1>
    <BracoSvg
      :afinacao="config.afinacao"
      :casas="config.casas"
      @tocar="tocar"
    />
  </main>
</template>

<style scoped>
.app {
  padding: 16px;
  max-width: 100%;
}
h1 {
  font-size: 1.25rem;
  margin: 0 0 12px;
}
</style>
