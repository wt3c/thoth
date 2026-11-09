/**
 * O `AudioContext` nasce e é retomado só dentro de um gesto do usuário (ADR-057):
 * fora dele o navegador o cria suspenso e o primeiro som se perde.
 * Fica fora da reatividade do Vue; os componentes chamam `desbloquear()` no clique.
 */

interface ContextoRetomavel {
  readonly state: AudioContextState
  resume(): Promise<void>
}

export interface AcessoAoContexto<C extends ContextoRetomavel> {
  desbloquear(): Promise<C>
}

export function criarAcessoAoContexto<C extends ContextoRetomavel>(fabrica: () => C): AcessoAoContexto<C> {
  let contexto: C | null = null
  return {
    async desbloquear() {
      contexto ??= fabrica()
      if (contexto.state !== 'running') await contexto.resume()
      return contexto
    },
  }
}

/** O acesso da aplicação, ao `AudioContext` do navegador. */
export const audio = criarAcessoAoContexto(() => new AudioContext({ latencyHint: 'interactive' }))
