import { describe, expect, it, vi } from 'vitest'
import { criarAcessoAoContexto } from './contexto'

function contextoFalso(estado: AudioContextState = 'suspended') {
  return { state: estado, resume: vi.fn(async () => undefined) }
}

describe('acesso preguiçoso ao AudioContext', () => {
  it('não cria o contexto antes do primeiro gesto', () => {
    const fabrica = vi.fn(() => contextoFalso())
    criarAcessoAoContexto(fabrica)
    expect(fabrica).not.toHaveBeenCalled()
  })

  it('o gesto cria um único contexto e o retoma se estiver suspenso', async () => {
    const falso = contextoFalso()
    const fabrica = vi.fn(() => falso)
    const acesso = criarAcessoAoContexto(fabrica)

    const primeiro = await acesso.desbloquear()
    const segundo = await acesso.desbloquear()

    expect(fabrica).toHaveBeenCalledTimes(1)
    expect(primeiro).toBe(segundo)
    expect(falso.resume).toHaveBeenCalled()
  })

  it('contexto já rodando não é retomado de novo', async () => {
    const falso = contextoFalso('running')
    await criarAcessoAoContexto(() => falso).desbloquear()
    expect(falso.resume).not.toHaveBeenCalled()
  })
})
