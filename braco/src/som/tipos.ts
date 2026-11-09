/**
 * Contratos do som (ADR-057). TypeScript puro, fora da reatividade do Vue:
 * nada daqui entra em `ref`/`reactive` — os stores guardam só a configuração serializável.
 *
 * Todo tempo é em **segundos do relógio do `AudioContext`** (`currentTime`).
 */

import type { Altura } from '@/dominio/tipos'

/** Fonte única de tempo para metrônomo e notas. Em produção, `AudioContext.currentTime`. */
export interface Relogio {
  agora(): number
}

/** Quantas notas por tempo: 1 = semínima, 2 = colcheia, 3 = tercina, 4 = semicolcheia. */
export type Subdivisao = 1 | 2 | 3 | 4

export type SomDoClique = 'eletronico' | 'madeira' | 'bipe'

export interface ConfigMetronomo {
  /** 30–244, como o Musicca. */
  readonly bpm: number
  /** Tempos por compasso, 1–12. */
  readonly temposPorCompasso: number
  readonly subdivisao: Subdivisao
  /** Som distinto no tempo 1. Desligar equivale ao `isTempoHidden` do Musicca. */
  readonly acentoNoUm: boolean
  /** "Tocar N compassos e silenciar M"; o indicador visual continua andando no silêncio. */
  readonly silencio: { readonly ativo: boolean; readonly tocar: number; readonly silenciar: number }
  /** 0–1. */
  readonly volume: number
  readonly som: SomDoClique
  /** Compassos de contagem antes do primeiro tempo, 0–2. Não contam para o silêncio. */
  readonly contagemEntrada: number
}

/** Um pulso já posicionado no relógio de áudio. */
export interface Pulso {
  readonly tempo: number
  /** Compasso, a partir de 0; negativo durante a contagem de entrada. */
  readonly compasso: number
  /** Tempo dentro do compasso, a partir de 1. */
  readonly batida: number
  /** Subdivisão dentro do tempo, a partir de 0 (0 = o próprio tempo). */
  readonly sub: number
  readonly acento: boolean
  readonly silenciado: boolean
  readonly contagem: boolean
}

export interface OpcoesDoClique {
  readonly acento: boolean
  /** Pulso de subdivisão (mais fraco que o tempo). */
  readonly sub: boolean
  readonly volume: number
  readonly som: SomDoClique
}

/** Produz o som. Implementação real sobre Web Audio; nos testes, um gravador. */
export interface Sintetizador {
  clique(tempo: number, opcoes: OpcoesDoClique): void
  nota(altura: Altura, tempo: number, duracao: number): void
  /** Cancela tudo o que foi agendado e ainda não soou. */
  silenciar(): void
}

/** Acorda o agendador periodicamente. Em produção, um Web Worker; só dá o tique, nunca o tempo. */
export interface Despertador {
  iniciar(aoTique: () => void, intervaloMs: number): void
  parar(): void
}

export interface Metronomo {
  readonly tocando: boolean
  iniciar(): void
  parar(): void
  /** Vale a partir do próximo tempo. */
  configurar(config: ConfigMetronomo): void
  /** Chamado quando cada pulso **soa** (para o indicador visual), não quando é agendado. */
  aoPulso(cb: (pulso: Pulso) => void): () => void
  /** Chamado quando cada pulso é **agendado**, ~100 ms antes de soar: para agendar notas no mesmo instante (S6). */
  aoAgendar(cb: (pulso: Pulso) => void): () => void
  /** Próximo instante da grade (tempo × subdivisão) depois de `agora`; `null` se parado. */
  proximoDaGrade(agora: number): number | null
}
