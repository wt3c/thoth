<script setup lang="ts">
/**
 * Legenda dos sinais de oitava do modo notas (emenda do ADR-061). O desenho repete o do braço:
 * anel em volta da nota tocada e etiqueta no canto das outras posições da mesma nota.
 */
import { useConfigStore } from '@/stores/config'

const config = useConfigStore()

const ITENS: readonly { sinal: string; texto: string }[] = [
  { sinal: 'referencia', texto: 'A nota que você tocou: o ponto de partida das oitavas' },
  { sinal: '+1', texto: 'Uma oitava acima: a mesma nota, mais aguda' },
  { sinal: '+2', texto: 'Duas oitavas acima' },
  { sinal: '−1', texto: 'Uma oitava abaixo: a mesma nota, mais grave' },
  { sinal: '=', texto: 'O mesmo som, em outra corda' },
]
</script>

<template>
  <section
    v-if="config.modo === 'notas'"
    class="legenda"
  >
    <ul aria-label="Legenda das oitavas">
      <li
        v-for="item in ITENS"
        :key="item.sinal"
        :data-sinal="item.sinal"
      >
        <svg
          viewBox="0 0 40 40"
          width="40"
          height="40"
          aria-hidden="true"
        >
          <circle
            class="amostra"
            cx="18"
            cy="22"
            r="12"
          />
          <circle
            v-if="item.sinal === 'referencia'"
            class="anel-referencia"
            cx="18"
            cy="22"
            r="16"
          />
          <g
            v-else
            class="oitava"
          >
            <circle
              cx="30"
              cy="10"
              r="9"
            />
            <text
              x="30"
              y="10"
            >{{ item.sinal }}</text>
          </g>
        </svg>
        <span>{{ item.texto }}</span>
      </li>
    </ul>
    <p>
      Oitava é a mesma nota repetida, mais aguda ou mais grave. Na mesma corda, ela fica 12 casas adiante.
    </p>
  </section>
</template>

<style scoped>
.legenda {
  margin: 8px 0 16px;
  font-size: 0.9rem;
}
ul {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 20px;
  margin: 0;
  padding: 0;
  list-style: none;
}
li {
  display: flex;
  align-items: center;
  gap: 6px;
}
p {
  margin: 4px 0 0;
  color: var(--texto-suave);
}
.amostra {
  fill: var(--superficie);
  stroke: var(--texto-suave);
  stroke-width: 2;
}
/* O mesmo desenho de `.anel-referencia` e `.oitava` em BracoSvg.vue. */
.anel-referencia {
  fill: none;
  stroke: var(--destaque);
  stroke-width: 3;
}
.oitava circle {
  fill: var(--destaque);
}
.oitava text {
  fill: var(--destaque-texto);
  font: 700 11px/1 system-ui, sans-serif;
  text-anchor: middle;
  dominant-baseline: central;
}
</style>
