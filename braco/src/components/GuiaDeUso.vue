<script setup lang="ts">
/**
 * Guia "Como usar" no fim da página (ADR-064): um bloco que abre e fecha por assunto, com os
 * títulos dos painéis. O texto cita os controles pelo nome que aparece na tela.
 */
</script>

<template>
  <section
    id="como-usar"
    class="guia"
    aria-labelledby="titulo-como-usar"
  >
    <h2 id="titulo-como-usar">
      Como usar
    </h2>

    <details data-secao="comecar">
      <summary>Primeiros passos</summary>
      <p>
        O desenho é o braço do instrumento: as linhas compridas são as cordas e os traços que as cruzam separam as
        casas. A corda mais grossa, de som mais grave, fica embaixo. No celular em pé, o braço fica na vertical, com
        a corda grave à esquerda.
      </p>
      <p>
        O braço abre limpo. Toque numa casa para ouvir a nota dela: a mesma nota se acende em todos os lugares do
        braço onde ela aparece.
      </p>
    </details>

    <details data-secao="notas">
      <summary>Notas</summary>
      <p>No modo <strong>Notas</strong>:</p>
      <ul>
        <li>Tocar uma casa toca o som e acende aquela nota em todo o braço. Tocar de novo no mesmo lugar solta.</li>
        <li>
          Os 12 botões ligam e desligam cada nota no braço. A nota desligada aparece riscada. <strong>Todas</strong>
          acende as 12 e <strong>Limpar</strong> apaga todas.
        </li>
        <li>
          <strong>Tocar notas do braço no metrônomo</strong> toca as notas acesas, uma por tempo, da mais grave à mais
          aguda; a que está soando fica em destaque. <strong>Parar notas</strong> para as notas e o metrônomo.
        </li>
      </ul>
    </details>

    <details data-secao="oitavas">
      <summary>Oitavas</summary>
      <p>
        Oitava é a mesma nota repetida, mais aguda ou mais grave. Na mesma corda, ela fica 12 casas adiante; em
        outra corda, em outro lugar.
      </p>
      <p>
        No modo Notas, a casa que você tocou ganha um anel: ela é o ponto de partida. As outras casas com a mesma
        nota ganham uma etiqueta: <strong>+1</strong> é uma oitava acima, <strong>+2</strong> duas,
        <strong>−1</strong> uma abaixo e <strong>=</strong> é o mesmo som em outra corda. A legenda abaixo do braço
        repete isso. Tocar outra casa com a mesma nota muda o ponto de partida.
      </p>
    </details>

    <details data-secao="teoria">
      <summary>Modo Teoria</summary>
      <p>
        A <strong>tônica</strong> é a nota de onde a escala ou o acorde parte. No modo <strong>Teoria</strong>,
        a nota que você toca vira a tônica; para trocar, toque outra. A nota escolhida no modo Notas já chega
        como tônica. <strong>Limpar</strong> apaga a tônica e deixa o braço vazio.
      </p>
      <ul>
        <li>
          <strong>Padrão</strong> escolhe uma escala, um acorde ou um intervalo. Só as notas dele aparecem no braço.
          Com <strong>Todas as notas (função de cada uma)</strong>, todas aparecem, cada uma com a cor da sua
          distância até a tônica.
        </li>
        <li>
          <strong>Rótulo</strong> mostra o nome da nota (<strong>Nome</strong>) ou o seu
          <strong>Grau</strong>: o número dela a partir da tônica, em que 1 é a própria tônica.
        </li>
        <li>
          <strong>Tocar sequência no metrônomo</strong> toca as notas do padrão uma por tempo, subindo a partir da
          tônica mais grave do braço. <strong>Parar sequência</strong> interrompe.
        </li>
      </ul>
    </details>

    <details data-secao="metronomo">
      <summary>Metrônomo</summary>
      <ul>
        <li><strong>▶ Tocar</strong> e <strong>■ Parar</strong>. Os círculos mostram em que tempo do compasso você está.</li>
        <li>
          O andamento vai de 30 a 244 batidas por minuto (BPM): use <strong>−</strong> e <strong>+</strong>, digite o
          número ou arraste a barra. Em <strong>Tap</strong>, toque no ritmo que você quer, duas vezes ou mais; depois
          de 3 segundos sem toque, a conta recomeça.
        </li>
        <li><strong>Tempos</strong>: quantas batidas tem cada compasso. <strong>Som</strong>: o timbre do clique.</li>
        <li><strong>Contagem</strong>: compassos de clique antes de começar, para você entrar no tempo.</li>
        <li><strong>Subdivisão</strong>: cliques extras dentro de cada tempo (1, 2, 3 ou 4).</li>
        <li><strong>Acento no tempo 1</strong>: o primeiro tempo de cada compasso soa mais forte.</li>
        <li>
          <strong>Compassos em silêncio</strong>: o metrônomo toca alguns compassos e fica mudo em outros, para você
          treinar manter o tempo sozinho.
        </li>
        <li>
          <strong>Encaixar o clique no braço na grade do metrônomo</strong>: com o metrônomo tocando, a nota que você
          toca no braço espera o próximo clique.
        </li>
        <li>Em tela pequena, uma barra no pé da página traz Tocar, o andamento e os tempos.</li>
      </ul>
    </details>

    <details data-secao="instrumento">
      <summary>Instrumento</summary>
      <ul>
        <li><strong>Baixo</strong> (4 a 7 cordas) ou <strong>Guitarra</strong> (6 cordas).</li>
        <li><strong>Afinação</strong>: a nota de cada corda solta; a escolha muda todas as notas do braço.</li>
        <li><strong>Casas</strong>: quantas casas o desenho mostra, de 12 a 24.</li>
      </ul>
    </details>

    <details data-secao="exibicao">
      <summary>Exibição</summary>
      <ul>
        <li><strong>Nomes</strong>: em letras (C D E) ou em sílabas (Dó Ré Mi). C é Dó, D é Ré, e assim por diante.</li>
        <li>
          <strong>Acidentes</strong>: escrever com ♯ (sustenido) ou ♭ (bemol). C♯ e D♭ são o mesmo som com dois
          nomes.
        </li>
        <li><strong>Tema</strong>: claro, escuro ou o do sistema.</li>
        <li><strong>Cores para daltonismo</strong>: troca as cores das notas por uma paleta mais fácil de distinguir.</li>
      </ul>
    </details>

    <details data-secao="salvo">
      <summary>Link e escolhas salvas</summary>
      <p>
        Suas escolhas ficam no endereço da página e no navegador. Ao voltar, tudo está como você deixou; copiando o
        link, outra pessoa abre a mesma configuração. Ao abrir, o link vale mais que o que foi salvo. O ponto de
        partida das oitavas e o metrônomo tocando não são salvos.
      </p>
    </details>

    <details data-secao="teclado">
      <summary>Teclado</summary>
      <p>
        Com <kbd>Tab</kbd> você chega ao braço. As setas andam de casa em casa e de corda em corda, na direção em que
        o braço aparece na tela, e <kbd>Enter</kbd> toca a nota.
      </p>
    </details>
  </section>
</template>

<style scoped>
.guia {
  margin-top: 24px;
}
h2 {
  font-size: 1.2rem;
  margin: 0 0 8px;
}
details {
  border-top: 1px solid var(--borda);
  padding: 4px 0;
}
details:last-of-type {
  border-bottom: 1px solid var(--borda);
}
summary {
  cursor: pointer;
  font-weight: 600;
  padding: 10px 0;
  min-height: 44px;
  box-sizing: border-box;
}
p,
ul {
  margin: 0 0 10px;
  max-width: 70ch;
  line-height: 1.5;
}
ul {
  padding-left: 20px;
}
</style>
