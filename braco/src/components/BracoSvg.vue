<script setup lang="ts">
/**
 * O braço em SVG (ADR-059): a corda grave embaixo, a pestana à esquerda.
 * Cada nota é um alvo de toque com no mínimo 44 px. O foco é itinerante: só uma nota
 * fica no Tab, as setas andam pelo braço e Enter toca a nota. O espaço fica reservado ao metrônomo.
 */
import { computed, ref } from 'vue'
import { gerarBraco } from '@/dominio/braco'
import { nomeDaClasse } from '@/dominio/nomes'
import type { Afinacao, Posicao } from '@/dominio/tipos'

const props = defineProps<{ afinacao: Afinacao; casas: number }>()
const emit = defineEmits<{ tocar: [posicao: Posicao] }>()

const ALVO = 48
const ESPACO_CORDA = 52
const MARGEM = 28
const LARGURA_SOLTA = 56
/** Largura da casa 1; as seguintes encolhem como num braço real, até o piso do alvo de toque. */
const PRIMEIRA_CASA = 112

const larguras = computed(() =>
  Array.from({ length: props.casas }, (_, i) => Math.max(ALVO + 6, PRIMEIRA_CASA * 2 ** (-i / 12))),
)
/** x de cada traste; o índice 0 é a pestana. */
const trastes = computed(() => {
  const xs = [MARGEM + LARGURA_SOLTA]
  for (const largura of larguras.value) xs.push((xs.at(-1) ?? 0) + largura)
  return xs
})
const numCordas = computed(() => props.afinacao.cordas.length)
const largura = computed(() => (trastes.value.at(-1) ?? 0) + MARGEM)
const altura = computed(() => numCordas.value * ESPACO_CORDA + MARGEM)

const yDaCorda = (corda: number) => MARGEM / 2 + (numCordas.value - 1 - corda) * ESPACO_CORDA + ESPACO_CORDA / 2
function xDaCasa(casa: number): number {
  if (casa === 0) return MARGEM + LARGURA_SOLTA / 2
  return ((trastes.value[casa - 1] ?? 0) + (trastes.value[casa] ?? 0)) / 2
}

const posicoes = computed(() => gerarBraco(props.afinacao, props.casas))

const focada = ref({ corda: 0, casa: 0 })
const notas = ref<Record<string, SVGGElement>>({})
const chave = (p: { corda: number; casa: number }) => `${p.corda}-${p.casa}`

function rotulo(p: Posicao): string {
  return `${nomeDaClasse(p.classe)}, corda ${numCordas.value - p.corda}, casa ${p.casa}`
}

const PASSOS: Record<string, [number, number]> = {
  ArrowRight: [0, 1],
  ArrowLeft: [0, -1],
  ArrowUp: [1, 0],
  ArrowDown: [-1, 0],
}

function aoTeclar(evento: KeyboardEvent, p: Posicao) {
  if (evento.key === 'Enter') {
    evento.preventDefault()
    emit('tocar', p)
    return
  }
  const passo = PASSOS[evento.key]
  if (!passo) return
  evento.preventDefault()
  const corda = Math.min(numCordas.value - 1, Math.max(0, p.corda + passo[0]))
  const casa = Math.min(props.casas, Math.max(0, p.casa + passo[1]))
  focada.value = { corda, casa }
  notas.value[chave(focada.value)]?.focus()
}
</script>

<template>
  <div class="rolagem">
    <svg
      class="braco"
      :viewBox="`0 0 ${largura} ${altura}`"
      :width="largura"
      :height="altura"
      role="group"
      :aria-label="`Braço, afinação ${afinacao.nome}, ${casas} casas`"
    >
      <rect
        class="madeira"
        :x="MARGEM + LARGURA_SOLTA"
        :y="MARGEM / 2"
        :width="(trastes.at(-1) ?? 0) - MARGEM - LARGURA_SOLTA"
        :height="numCordas * ESPACO_CORDA"
        rx="4"
      />
      <line
        v-for="(x, i) in trastes"
        :key="`traste-${i}`"
        :class="i === 0 ? 'pestana' : 'traste'"
        :x1="x"
        :x2="x"
        :y1="MARGEM / 2"
        :y2="MARGEM / 2 + numCordas * ESPACO_CORDA"
      />
      <line
        v-for="(_, corda) in afinacao.cordas"
        :key="`corda-${corda}`"
        class="corda"
        :x1="MARGEM"
        :x2="trastes.at(-1)"
        :y1="yDaCorda(corda)"
        :y2="yDaCorda(corda)"
        :stroke-width="1.5 + (numCordas - 1 - corda) * 0.2 + corda * 0.6"
      />
      <g
        v-for="p in posicoes"
        :key="chave(p)"
        :ref="(el) => { if (el) notas[chave(p)] = el as SVGGElement }"
        class="nota"
        role="button"
        :tabindex="focada.corda === p.corda && focada.casa === p.casa ? 0 : -1"
        :aria-label="rotulo(p)"
        :data-nota="nomeDaClasse(p.classe)"
        :data-corda="p.corda"
        :data-casa="p.casa"
        :data-y="yDaCorda(p.corda)"
        @click="emit('tocar', p); focada = { corda: p.corda, casa: p.casa }"
        @keydown="aoTeclar($event, p)"
      >
        <rect
          class="alvo"
          :x="xDaCasa(p.casa) - ALVO / 2"
          :y="yDaCorda(p.corda) - 22"
          :width="ALVO"
          height="44"
        />
        <circle
          class="marcador"
          :cx="xDaCasa(p.casa)"
          :cy="yDaCorda(p.corda)"
          r="16"
        />
        <text
          class="nome"
          :x="xDaCasa(p.casa)"
          :y="yDaCorda(p.corda)"
          aria-hidden="true"
        >{{ nomeDaClasse(p.classe) }}</text>
      </g>
    </svg>
  </div>
</template>

<style scoped>
.rolagem {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
.braco {
  display: block;
}
.madeira {
  fill: var(--braco-madeira);
}
.traste {
  stroke: var(--braco-traste);
  stroke-width: 3;
}
.pestana {
  stroke: var(--braco-traste);
  stroke-width: 7;
}
.corda {
  stroke: var(--braco-corda);
}
.nota {
  cursor: pointer;
  outline: none;
}
.alvo {
  fill: transparent;
}
.marcador {
  fill: var(--nota-fundo);
  stroke: var(--braco-madeira);
  stroke-width: 2;
}
.nome {
  fill: var(--nota-texto);
  font: 600 13px/1 system-ui, sans-serif;
  text-anchor: middle;
  dominant-baseline: central;
  pointer-events: none;
}
.nota:focus-visible .marcador {
  stroke: var(--foco);
  stroke-width: 4;
}
</style>
