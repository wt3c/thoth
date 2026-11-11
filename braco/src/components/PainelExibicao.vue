<script setup lang="ts">
import { useConfigStore } from '@/stores/config'
import GrupoDeOpcoes from './GrupoDeOpcoes.vue'

const config = useConfigStore()
</script>

<template>
  <section
    class="painel"
    aria-labelledby="titulo-exibicao"
  >
    <h2 id="titulo-exibicao">
      Exibição
    </h2>
    <GrupoDeOpcoes
      v-model="config.nomenclatura"
      legenda="Nomes"
      nome="nomenclatura"
      :opcoes="[{ valor: 'cifra', rotulo: 'C D E' }, { valor: 'solfejo', rotulo: 'Dó Ré Mi' }]"
    />
    <GrupoDeOpcoes
      v-model="config.acidente"
      legenda="Acidentes"
      nome="acidente"
      :opcoes="[{ valor: 'sustenido', rotulo: '♯' }, { valor: 'bemol', rotulo: '♭' }]"
    />
    <GrupoDeOpcoes
      v-model="config.tema"
      legenda="Tema"
      nome="tema"
      :opcoes="[{ valor: 'sistema', rotulo: 'Sistema' }, { valor: 'claro', rotulo: 'Claro' }, { valor: 'escuro', rotulo: 'Escuro' }, { valor: 'matte-black', rotulo: 'Matte Black' }]"
    />
    <label class="interruptor">
      <input
        v-model="config.daltonico"
        type="checkbox"
      >
      Cores para daltonismo
    </label>
  </section>
</template>
