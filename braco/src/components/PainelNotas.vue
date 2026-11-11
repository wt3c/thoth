<script setup lang="ts">
import { computed } from 'vue'
import { exibirNome, nomeDaClasse } from '@/dominio/nomes'
import { alturasDaSequencia, posicoesVisiveis } from '@/dominio/sequencia'
import { PADROES } from '@/dominio/teoria'
import type { ClasseAltura, TipoPadrao } from '@/dominio/tipos'
import { TODAS_AS_CLASSES } from '@/dominio/vista'
import { useConfigStore } from '@/stores/config'
import { useMetronomoStore } from '@/stores/metronomo'
import GrupoDeOpcoes from './GrupoDeOpcoes.vue'

const config = useConfigStore()
const metro = useMetronomoStore()

const nome = (c: ClasseAltura) =>
  exibirNome(nomeDaClasse(c, { nomenclatura: 'cifra', acidente: config.acidente }), config.nomenclatura)

const GRUPOS: readonly { tipo: TipoPadrao; rotulo: string }[] = [
  { tipo: 'escala', rotulo: 'Escalas e modos' },
  { tipo: 'acorde', rotulo: 'Acordes' },
  { tipo: 'intervalo', rotulo: 'Intervalos' },
]

const padraoId = computed({
  get: () => config.padraoId ?? '',
  set: (v: string) => (config.padraoId = v === '' ? null : v),
})

const acesas = computed(() => posicoesVisiveis(config.afinacao, config.casas, config.escolhas))

/** Modo notas: cada posição acesa soa e acende sozinha num pulso, pela mesma sequência do S6. */
function tocarAcesas() {
  metro.tocarSequencia(acesas.value).catch((erro: unknown) => console.error('falha ao tocar as notas', erro))
}

/** "Parar notas" desliga tudo: o metrônomo para e leva a sequência junto. */
function pararNotas() {
  metro.parar().catch((erro: unknown) => console.error('falha ao parar as notas', erro))
}

/** Sem tônica não há sequência: o botão de parar ficaria desligado com ela ainda soando. */
function limparTeoria() {
  if (metro.sequenciaAtiva) metro.pararSequencia()
  config.limparTeoria()
}

function tocarSequencia() {
  if (config.tonica === null) return
  const alturas = alturasDaSequencia(config.afinacao, config.casas, config.tonica, config.escolhas.padrao)
  metro.tocarSequencia(alturas).catch((erro: unknown) => console.error('falha ao tocar a sequência', erro))
}
</script>

<template>
  <section
    class="painel"
    aria-labelledby="titulo-notas"
  >
    <h2 id="titulo-notas">
      Notas
    </h2>
    <GrupoDeOpcoes
      v-model="config.modo"
      legenda="Modo"
      nome="modo"
      :opcoes="[{ valor: 'notas', rotulo: 'Notas' }, { valor: 'teoria', rotulo: 'Teoria' }]"
    />

    <template v-if="config.modo === 'notas'">
      <div
        class="filtro"
        role="group"
        aria-label="Notas visíveis"
      >
        <button
          v-for="c in TODAS_AS_CLASSES"
          :key="c"
          type="button"
          class="classe"
          :data-classe="c"
          :aria-pressed="config.filtro.includes(c)"
          :style="{ '--cor': config.escolhas.paleta.porClasse[c] }"
          @click="config.alternarClasse(c)"
        >
          {{ nome(c) }}
        </button>
      </div>
      <div class="acoes">
        <button
          type="button"
          data-acao="todas"
          @click="config.mostrarClasses(TODAS_AS_CLASSES)"
        >
          Todas
        </button>
        <button
          type="button"
          data-acao="limpar"
          @click="config.mostrarClasses([])"
        >
          Limpar
        </button>
      </div>
      <p class="dica">
        <template v-if="config.selecionada !== null">
          {{ nome(config.selecionada) }} destacada em todas as posições. Toque de novo para soltar.
        </template>
        <template v-else>
          Toque uma nota para ouvi-la e vê-la em todo o braço.
        </template>
      </p>
      <div class="acoes">
        <button
          type="button"
          data-acao="tocar-notas"
          :disabled="!metro.sequenciaAtiva && acesas.length === 0"
          @click="metro.sequenciaAtiva ? pararNotas() : tocarAcesas()"
        >
          {{ metro.sequenciaAtiva ? 'Parar notas' : 'Tocar notas do braço no metrônomo' }}
        </button>
      </div>
    </template>

    <template v-else>
      <p
        class="dica"
        aria-live="polite"
      >
        <template v-if="config.tonica === null">
          Toque uma nota no braço para ela virar a tônica.
        </template>
        <template v-else>
          Tônica: <strong>{{ nome(config.tonica) }}</strong>
        </template>
      </p>
      <label class="campo">
        <span>Padrão</span>
        <select v-model="padraoId">
          <option value="">Todas as notas (função de cada uma)</option>
          <optgroup
            v-for="g in GRUPOS"
            :key="g.tipo"
            :label="g.rotulo"
          >
            <option
              v-for="p in PADROES.filter((x) => x.tipo === g.tipo)"
              :key="p.id"
              :value="p.id"
            >{{ p.nome }}</option>
          </optgroup>
        </select>
      </label>
      <div class="rotulo-e-limpar">
        <GrupoDeOpcoes
          v-model="config.rotulo"
          legenda="Rótulo"
          nome="rotulo"
          :opcoes="[{ valor: 'nome', rotulo: 'Nome' }, { valor: 'grau', rotulo: 'Grau' }]"
        />
        <button
          type="button"
          data-acao="limpar-teoria"
          @click="limparTeoria"
        >
          Limpar
        </button>
      </div>
      <div class="acoes">
        <button
          type="button"
          :disabled="config.tonica === null"
          @click="metro.sequenciaAtiva ? metro.pararSequencia() : tocarSequencia()"
        >
          {{ metro.sequenciaAtiva ? 'Parar sequência' : 'Tocar sequência no metrônomo' }}
        </button>
      </div>
    </template>
  </section>
</template>

<style scoped>
.rotulo-e-limpar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 8px;
}
.rotulo-e-limpar button {
  min-height: 44px;
}
.filtro {
  display: grid;
  grid-template-columns: repeat(6, minmax(44px, 1fr));
  gap: 6px;
}
.classe {
  min-height: 44px;
  border-radius: 10px;
  border: 2px solid var(--cor);
  background: var(--superficie);
  color: var(--texto);
  font-weight: 600;
}
.classe[aria-pressed='true'] {
  background: var(--cor);
  color: var(--fundo-nota-texto, #fff);
}
.classe[aria-pressed='false'] {
  opacity: 0.55;
  text-decoration: line-through;
}
</style>
