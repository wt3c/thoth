<script setup lang="ts" generic="T extends string | number">
/** Grupo de opções exclusivas: rádios nativos (teclado e leitor de tela de graça), alvos ≥ 44 px. */
defineProps<{ legenda: string; nome: string; opcoes: readonly { valor: T; rotulo: string }[] }>()
const modelo = defineModel<T>({ required: true })
</script>

<template>
  <fieldset class="segmentado">
    <legend>{{ legenda }}</legend>
    <div class="opcoes">
      <label
        v-for="o in opcoes"
        :key="String(o.valor)"
        :class="{ ativa: modelo === o.valor }"
      >
        <input
          v-model="modelo"
          type="radio"
          :name="nome"
          :value="o.valor"
        >
        {{ o.rotulo }}
      </label>
    </div>
  </fieldset>
</template>

<style scoped>
.segmentado {
  border: 0;
  margin: 0;
  padding: 0;
  min-width: 0;
}
legend {
  font-size: 0.8rem;
  color: var(--texto-suave);
  margin-bottom: 4px;
}
.opcoes {
  display: flex;
  flex-wrap: wrap;
  border: 1px solid var(--borda);
  border-radius: 10px;
  overflow: hidden;
  width: fit-content;
  max-width: 100%;
}
label {
  min-height: 44px;
  min-width: 44px;
  padding: 0 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  background: var(--superficie);
  border-right: 1px solid var(--borda);
  user-select: none;
}
label:last-child {
  border-right: 0;
}
label.ativa {
  background: var(--destaque);
  color: var(--destaque-texto);
  font-weight: 600;
}
label:has(input:focus-visible) {
  outline: 3px solid var(--foco);
  outline-offset: -3px;
}
input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}
</style>
