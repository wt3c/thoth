<script setup lang="ts">
import { computed } from 'vue'
import type { Instrumento } from '@/dominio/tipos'
import { CASAS_MAX, CASAS_MIN, CORDAS, useConfigStore } from '@/stores/config'
import GrupoDeOpcoes from './GrupoDeOpcoes.vue'

const config = useConfigStore()

const instrumento = computed({ get: () => config.instrumento, set: (v: Instrumento) => config.escolherInstrumento(v) })
const cordas = computed({ get: () => config.numCordas, set: (n: number) => config.escolherNumCordas(n) })
const opcoesDeCordas = computed(() => CORDAS[config.instrumento].map((n) => ({ valor: n, rotulo: String(n) })))
</script>

<template>
  <section
    class="painel"
    aria-labelledby="titulo-instrumento"
  >
    <h2 id="titulo-instrumento">
      Instrumento
    </h2>
    <GrupoDeOpcoes
      v-model="instrumento"
      legenda="Instrumento"
      nome="instrumento"
      :opcoes="[{ valor: 'baixo', rotulo: 'Baixo' }, { valor: 'guitarra', rotulo: 'Guitarra' }]"
    />
    <GrupoDeOpcoes
      v-if="opcoesDeCordas.length > 1"
      v-model="cordas"
      legenda="Cordas"
      nome="cordas"
      :opcoes="opcoesDeCordas"
    />
    <label class="campo">
      <span>Afinação</span>
      <select v-model="config.afinacaoId">
        <option
          v-for="a in config.afinacoesDisponiveis"
          :key="a.id"
          :value="a.id"
        >{{ a.nome }}</option>
      </select>
    </label>
    <label class="campo">
      <span>Casas: {{ config.casas }}</span>
      <input
        type="range"
        :min="CASAS_MIN"
        :max="CASAS_MAX"
        :value="config.casas"
        @input="config.escolherCasas(Number(($event.target as HTMLInputElement).value))"
      >
    </label>
  </section>
</template>
