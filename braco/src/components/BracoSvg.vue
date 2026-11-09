<script setup lang="ts">
/**
 * O braço em SVG (ADR-059): na horizontal, corda grave embaixo e pestana à esquerda; na vertical
 * (celular em pé, ADR-063), pestana em cima e corda grave à esquerda. A geometria vem de
 * `dominio/geometria`.
 * Cada nota é um alvo de toque com no mínimo 44 px. O foco é itinerante: só uma nota
 * fica no Tab, as setas andam pelo braço e Enter toca a nota. O espaço fica reservado ao metrônomo.
 */
import { computed, ref } from 'vue'
import { gerarBraco } from '@/dominio/braco'
import { geometriaDoBraco, type Orientacao } from '@/dominio/geometria'
import { nomeDaClasse } from '@/dominio/nomes'
import type { Afinacao, Altura, Posicao } from '@/dominio/tipos'
import { vistaDaNota, type EscolhasDaVista, type VistaDaNota } from '@/dominio/vista'

const props = withDefaults(
  defineProps<{
    afinacao: Afinacao
    casas: number
    escolhas: EscolhasDaVista
    soando?: Altura | null
    orientacao?: Orientacao
  }>(),
  { soando: null, orientacao: 'horizontal' },
)
const emit = defineEmits<{ tocar: [posicao: Posicao] }>()

const numCordas = computed(() => props.afinacao.cordas.length)
const g = computed(() => geometriaDoBraco(numCordas.value, props.casas, props.orientacao))
const centro = (p: { corda: number; casa: number }) => g.value.centro(p.corda, p.casa)

const posicoes = computed(() => gerarBraco(props.afinacao, props.casas))
const vistas = computed(() => new Map(posicoes.value.map((p) => [chave(p), vistaDaNota(p, props.escolhas)])))
const vistaDe = (p: Posicao): VistaDaNota => {
  const v = vistas.value.get(chave(p))
  if (!v) throw new Error(`posição sem vista: ${chave(p)}`)
  return v
}
const coresDoBraco = computed(() => {
  const b = props.escolhas.paleta.braco
  return { '--braco-madeira': b.madeira, '--braco-traste': b.traste, '--braco-corda': b.corda, '--braco-marcacao': b.marcacao }
})

const focada = ref({ corda: 0, casa: 0 })
const notas = ref<Record<string, SVGGElement>>({})
const chave = (p: { corda: number; casa: number }) => `${p.corda}-${p.casa}`

function rotulo(p: Posicao): string {
  return `${vistaDe(p).falado}, corda ${numCordas.value - p.corda}, casa ${p.casa}`
}

/** [corda, casa] por seta: anda na direção em que o braço aparece na tela. */
const PASSOS: Record<Orientacao, Record<string, [number, number]>> = {
  horizontal: { ArrowRight: [0, 1], ArrowLeft: [0, -1], ArrowUp: [1, 0], ArrowDown: [-1, 0] },
  vertical: { ArrowDown: [0, 1], ArrowUp: [0, -1], ArrowRight: [1, 0], ArrowLeft: [-1, 0] },
}

function aoTeclar(evento: KeyboardEvent, p: Posicao) {
  if (evento.key === 'Enter') {
    evento.preventDefault()
    emit('tocar', p)
    return
  }
  const passo = PASSOS[props.orientacao][evento.key]
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
      :viewBox="`0 0 ${g.largura} ${g.altura}`"
      :width="g.largura"
      :height="g.altura"
      role="group"
      :data-orientacao="orientacao"
      :style="coresDoBraco"
      :aria-label="`Braço, afinação ${afinacao.nome}, ${casas} casas`"
    >
      <rect
        class="madeira"
        :x="g.madeira.x"
        :y="g.madeira.y"
        :width="g.madeira.largura"
        :height="g.madeira.altura"
        rx="4"
      />
      <line
        v-for="(s, i) in g.trastes"
        :key="`traste-${i}`"
        :class="i === 0 ? 'pestana' : 'traste'"
        v-bind="s"
      />
      <line
        v-for="(s, corda) in g.cordas"
        :key="`corda-${corda}`"
        class="corda"
        v-bind="s"
        :stroke-width="1.5 + (numCordas - 1 - corda) * 0.6"
      />
      <circle
        v-for="(m, i) in g.marcacoes"
        :key="`marcacao-${i}`"
        class="marcacao"
        :data-casa="m.casa"
        :cx="m.x"
        :cy="m.y"
        r="7"
      />
      <text
        v-for="n in g.numeros"
        :key="`numero-${n.casa}`"
        class="numero"
        :x="n.x"
        :y="n.y"
        aria-hidden="true"
      >{{ n.casa }}</text>
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
        :data-x="centro(p).x"
        :data-y="centro(p).y"
        :data-destaque="vistaDe(p).destaque"
        :data-soando="p.altura === soando"
        :class="{ soando: p.altura === soando }"
        @click="emit('tocar', p); focada = { corda: p.corda, casa: p.casa }"
        @keydown="aoTeclar($event, p)"
      >
        <rect
          class="alvo"
          :x="centro(p).x - g.alvo.largura / 2"
          :y="centro(p).y - g.alvo.altura / 2"
          :width="g.alvo.largura"
          :height="g.alvo.altura"
        />
        <template v-if="vistaDe(p).visivel">
          <circle
            class="marcador"
            :class="{ destaque: vistaDe(p).destaque }"
            :cx="centro(p).x"
            :cy="centro(p).y"
            :fill="vistaDe(p).fundo"
            r="17"
          />
          <text
            class="nome"
            :x="centro(p).x"
            :y="centro(p).y"
            :fill="vistaDe(p).corTexto"
            aria-hidden="true"
          >{{ vistaDe(p).texto }}</text>
        </template>
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
.marcacao {
  fill: var(--braco-marcacao);
  opacity: 0.6;
}
.soando .marcador {
  stroke: var(--foco);
  stroke-width: 5;
}
.soando .alvo {
  fill: var(--foco);
  opacity: 0.25;
}
.nota {
  cursor: pointer;
  outline: none;
}
.alvo {
  fill: transparent;
}
.marcador {
  stroke: var(--braco-madeira);
  stroke-width: 2;
}
.marcador.destaque {
  stroke: var(--texto);
  stroke-width: 4;
}
.numero {
  fill: var(--texto-suave);
  font: 500 11px/1 system-ui, sans-serif;
  text-anchor: middle;
  dominant-baseline: central;
}
.nome {
  font: 600 13px/1 system-ui, sans-serif;
  text-anchor: middle;
  dominant-baseline: central;
  pointer-events: none;
}
.nota:focus-visible .alvo {
  stroke: var(--foco);
  stroke-width: 3;
}
.nota:focus-visible .marcador {
  stroke: var(--foco);
  stroke-width: 4;
}
</style>
