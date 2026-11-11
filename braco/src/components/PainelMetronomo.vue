<script setup lang="ts">
import { computed } from 'vue'
import { BPM_MAX, BPM_MIN, limitarBpm } from '@/som/config-metronomo'
import type { ConfigMetronomo, SomDoClique, Subdivisao } from '@/som/tipos'
import { useConfigStore } from '@/stores/config'
import { useMetronomoStore } from '@/stores/metronomo'
import GrupoDeOpcoes from './GrupoDeOpcoes.vue'
import IndicadorDeTempos from './IndicadorDeTempos.vue'

const config = useConfigStore()
const metro = useMetronomoStore()

/** Toda mudança passa pelo store, que valida e repassa ao motor; erro aqui é bug, não entrada do usuário. */
function mudar(parcial: Partial<ConfigMetronomo>) {
  metro.atualizar(parcial).catch((erro: unknown) => console.error('configuração do metrônomo recusada', erro))
}

const numero = (e: Event) => Number((e.target as HTMLInputElement | HTMLSelectElement).value)
const mudarBpm = (bpm: number) => {
  if (Number.isFinite(bpm)) mudar({ bpm: limitarBpm(bpm) })
}

const subdivisao = computed({
  get: () => metro.config.subdivisao,
  set: (subdivisao: Subdivisao) => mudar({ subdivisao }),
})

const SONS: readonly { valor: SomDoClique; rotulo: string }[] = [
  { valor: 'eletronico', rotulo: 'Eletrônico' },
  { valor: 'madeira', rotulo: 'Bloco de madeira' },
  { valor: 'bipe', rotulo: 'Bipe' },
]

const tap = () => metro.tap(performance.now()).catch((erro: unknown) => console.error("tap recusado", erro))

function silencio(parcial: Partial<ConfigMetronomo['silencio']>) {
  mudar({ silencio: { ...metro.config.silencio, ...parcial } })
}
</script>

<template>
  <section
    class="painel"
    aria-labelledby="titulo-metronomo"
  >
    <h2 id="titulo-metronomo">
      Metrônomo
    </h2>

    <div class="colunas">
      <div class="grupo">
        <div class="principal">
          <button
            type="button"
            class="tocar"
            :aria-pressed="metro.tocando"
            @click="metro.alternar()"
          >
            {{ metro.tocando ? '■ Parar' : '▶ Tocar' }}
          </button>
          <IndicadorDeTempos />
        </div>

        <div class="andamento">
          <button
            type="button"
            data-acao="menos"
            aria-label="Diminuir andamento"
            @click="mudarBpm(metro.config.bpm - 1)"
          >
            −
          </button>
          <label class="campo bpm">
            <span>BPM</span>
            <input
              type="number"
              name="bpm"
              :min="BPM_MIN"
              :max="BPM_MAX"
              :value="metro.config.bpm"
              @change="mudarBpm(numero($event))"
            >
          </label>
          <button
            type="button"
            data-acao="mais"
            aria-label="Aumentar andamento"
            @click="mudarBpm(metro.config.bpm + 1)"
          >
            +
          </button>
          <button
            type="button"
            data-acao="tap"
            @click="tap"
          >
            Tap
          </button>
        </div>
        <input
          type="range"
          name="bpm-slider"
          aria-label="Andamento"
          :min="BPM_MIN"
          :max="BPM_MAX"
          :value="metro.config.bpm"
          @input="mudarBpm(numero($event))"
        >
      </div>

      <div class="grupo">
        <div class="linha">
          <label class="campo">
            <span>Tempos</span>
            <select
              name="tempos"
              :value="metro.config.temposPorCompasso"
              @change="mudar({ temposPorCompasso: numero($event) })"
            >
              <option
                v-for="n in 12"
                :key="n"
                :value="n"
              >{{ n }}</option>
            </select>
          </label>
          <label class="campo">
            <span>Som</span>
            <select
              name="som"
              :value="metro.config.som"
              @change="mudar({ som: ($event.target as HTMLSelectElement).value as SomDoClique })"
            >
              <option
                v-for="s in SONS"
                :key="s.valor"
                :value="s.valor"
              >{{ s.rotulo }}</option>
            </select>
          </label>
          <label class="campo">
            <span>Contagem</span>
            <select
              name="contagem"
              :value="metro.config.contagemEntrada"
              @change="mudar({ contagemEntrada: numero($event) })"
            >
              <option :value="0">Sem contagem</option>
              <option :value="1">1 compasso</option>
              <option :value="2">2 compassos</option>
            </select>
          </label>
        </div>

        <GrupoDeOpcoes
          v-model="subdivisao"
          legenda="Subdivisão"
          nome="subdivisao"
          :opcoes="[{ valor: 1, rotulo: '♩' }, { valor: 2, rotulo: '♫' }, { valor: 3, rotulo: '3' }, { valor: 4, rotulo: '♬' }]"
        />
      </div>

      <div class="grupo">
        <label class="campo">
          <span>Volume</span>
          <input
            type="range"
            name="volume"
            min="0"
            max="1"
            step="0.05"
            :value="metro.config.volume"
            @input="mudar({ volume: numero($event) })"
          >
        </label>

        <label class="interruptor">
          <input
            type="checkbox"
            name="acento"
            :checked="metro.config.acentoNoUm"
            @change="mudar({ acentoNoUm: ($event.target as HTMLInputElement).checked })"
          >
          Acento no tempo 1
        </label>

        <label class="interruptor">
          <input
            type="checkbox"
            name="silencio"
            :checked="metro.config.silencio.ativo"
            @change="silencio({ ativo: ($event.target as HTMLInputElement).checked })"
          >
          Compassos em silêncio
        </label>
        <div
          v-if="metro.config.silencio.ativo"
          class="linha"
        >
          <label class="campo">
            <span>Tocar</span>
            <input
              type="number"
              name="silencio-tocar"
              min="1"
              max="99"
              :value="metro.config.silencio.tocar"
              @change="silencio({ tocar: numero($event) })"
            >
          </label>
          <label class="campo">
            <span>Silenciar</span>
            <input
              type="number"
              name="silencio-silenciar"
              min="1"
              max="99"
              :value="metro.config.silencio.silenciar"
              @change="silencio({ silenciar: numero($event) })"
            >
          </label>
        </div>
      </div>

      <div class="grupo">
        <label class="interruptor">
          <input
            v-model="config.quantizar"
            type="checkbox"
            name="quantizar"
          >
          Encaixar o clique no braço na grade do metrônomo
        </label>
      </div>
    </div>
  </section>
</template>

<style scoped>
/* Em tela larga os grupos ficam lado a lado; em tela estreita, empilhados como antes. */
.colunas {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 240px), 1fr));
  gap: 12px 24px;
  align-items: start;
}
.grupo {
  display: grid;
  gap: 12px;
  align-content: start;
}
.principal {
  display: flex;
  align-items: center;
  gap: 16px;
}
.tocar {
  min-width: 120px;
  font-size: 1.1rem;
}
.andamento {
  display: flex;
  align-items: end;
  gap: 8px;
}
.bpm input {
  width: 5ch;
  font-size: 1.4rem;
  text-align: center;
}
input[type='range'] {
  width: 100%;
  min-height: 44px;
}
.linha {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
</style>
