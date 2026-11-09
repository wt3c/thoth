/**
 * Liga os stores à URL e ao localStorage (S8, ADR-062). Na abertura: URL > armazenado > padrão.
 * Depois, cada mudança reescreve os dois; a URL muda por `replaceState`, sem encher o histórico.
 */
import { watch } from 'vue'
import { useConfigStore } from '@/stores/config'
import { useMetronomoStore } from '@/stores/metronomo'
import { carregar, escrever } from './preferencias'

export const CHAVE = 'thoth-braco:preferencias'

/** O armazenamento pode faltar (aba privada, cota, bloqueio): a página segue, só sem lembrar. */
function lerArmazenado(): string | null {
  try {
    return localStorage.getItem(CHAVE)
  } catch (erro) {
    console.warn('localStorage indisponível para leitura', erro)
    return null
  }
}

function gravarArmazenado(texto: string) {
  try {
    localStorage.setItem(CHAVE, texto)
  } catch (erro) {
    console.warn('localStorage indisponível para escrita', erro)
  }
}

export function ligarPersistencia() {
  const config = useConfigStore()
  const metro = useMetronomoStore()

  const { preferencias, rejeitados } = carregar(location.search, lerArmazenado())
  if (rejeitados.length > 0) console.warn('preferências recusadas', rejeitados)
  const { metronomo, ...vista } = preferencias
  config.aplicar(vista)
  metro.config = metronomo

  watch(
    () => escrever({ ...config.preferencias, metronomo: metro.config }),
    (texto) => {
      gravarArmazenado(texto)
      history.replaceState(history.state, '', `${location.pathname}?${texto}${location.hash}`)
    },
    { immediate: true },
  )
}
