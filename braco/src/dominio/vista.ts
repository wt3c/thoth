/**
 * O que cada casa do braço mostra (ADR-061): visível, cor, texto, destaque e o nome falado.
 * Puro: o `BracoSvg` só desenha o que sai daqui.
 *
 * Modo notas: cor por classe, filtro de classes (M3) e a nota selecionada destacada em todas
 * as posições (M4). Modo teoria: a tônica tem cor própria e as demais saem pela função —
 * cromática sem padrão, grafada pelo padrão com ele (M9, S4, S5).
 */
import { corDoGrau, corDoTexto } from './cores'
import { exibirNome, nomeDaClasse } from './nomes'
import { grauCromatico, notasDoPadrao } from './teoria'
import type { ClasseAltura, Cor, Grau, OpcoesDeNome, Padrao, Paleta, Posicao } from './tipos'

export type Modo = 'notas' | 'teoria'
export type Rotulo = 'nome' | 'grau'

export const TODAS_AS_CLASSES: readonly ClasseAltura[] = Array.from({ length: 12 }, (_, c) => c)

export interface EscolhasDaVista {
  readonly modo: Modo
  /** Classes visíveis no modo notas. */
  readonly filtro: readonly ClasseAltura[]
  readonly selecionada: ClasseAltura | null
  /** Só no modo teoria; sem tônica, a teoria se comporta como o modo notas. */
  readonly tonica: ClasseAltura | null
  /** `null` = todas as notas pela função cromática. */
  readonly padrao: Padrao | null
  /** Só no modo teoria: o grau no lugar do nome. */
  readonly rotulo: Rotulo
  readonly nome: OpcoesDeNome
  readonly paleta: Paleta
}

export interface VistaDaNota {
  readonly visivel: boolean
  readonly texto: string
  readonly fundo: Cor
  readonly corTexto: Cor
  readonly destaque: boolean
  /** Para o nome acessível: nota e, na teoria, o grau. */
  readonly falado: string
}

const ACIDENTES: Readonly<Record<string, string>> = { '': '', b: '♭', bb: '𝄫', '#': '♯', '##': '𝄪' }

export function exibirGrau(grau: Grau): string {
  const partes = /^(#{1,2}|b{1,2})?(\d+)$/.exec(grau)
  if (!partes) throw new Error(`Grau inválido: ${grau}`)
  return (ACIDENTES[partes[1] ?? ''] ?? '') + partes[2]
}

function vista(visivel: boolean, nome: string, fundo: Cor, destaque: boolean, grau: Grau | null, rotulo: Rotulo): VistaDaNota {
  const grauExibido = grau === null ? null : exibirGrau(grau)
  return {
    visivel,
    texto: rotulo === 'grau' && grauExibido !== null ? grauExibido : nome,
    fundo,
    corTexto: corDoTexto(fundo),
    destaque,
    falado: grauExibido === null ? nome : `${nome}, grau ${grauExibido}`,
  }
}

export function vistaDaNota(p: Posicao, e: EscolhasDaVista): VistaDaNota {
  const nome = exibirNome(nomeDaClasse(p.classe, { nomenclatura: 'cifra', acidente: e.nome.acidente }), e.nome.nomenclatura)
  const fundoDaClasse = e.paleta.porClasse[p.classe] ?? e.paleta.tonica

  if (e.modo === 'notas' || e.tonica === null) {
    const selecionada = e.selecionada === p.classe
    return vista(selecionada || e.filtro.includes(p.classe), nome, fundoDaClasse, selecionada, null, 'nome')
  }

  const tonica = e.tonica
  const destaque = p.classe === tonica
  if (e.padrao === null) {
    const grau = grauCromatico(tonica, p.classe)
    return vista(true, nome, corDoGrau(e.paleta, grau), destaque, grau, e.rotulo)
  }
  const nota = notasDoPadrao(tonica, e.padrao, e.nome.acidente).find((n) => n.classe === p.classe)
  if (!nota) return vista(false, nome, fundoDaClasse, false, null, 'nome')
  return vista(true, exibirNome(nota.nome, e.nome.nomenclatura), corDoGrau(e.paleta, nota.grau), destaque, nota.grau, e.rotulo)
}
