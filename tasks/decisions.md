# Decisões Arquiteturais (ADR)

## ADR-001 — Sem ingestão de streams com DRM
**Data:** 2026-09-21 · **Status:** aceito

Spotify, YouTube Music e Amazon Music entregam áudio criptografado (Ogg cifrado /
Widevine). Não há API oficial que devolva PCM. Extrair exigiria re-gravação de
loopback ou circunvenção de DRM.

**Decisão:** a entrada do Thoth é arquivo local. O `Protocol AudioSource` mantém o
encaixe aberto para outros adapters (ex.: yt-dlp), que ficam a critério do usuário e
fora deste repositório.

**Consequência:** o Spotify permanece útil só para sincronizar o cursor de reprodução
(`/me/player/currently-playing`), nunca para obter áudio.

---

## ADR-002 — CPU-only; ROCm descartado
**Data:** 2026-09-21 · **Status:** aceito

A GPU da estação Pandora é uma Radeon RX 5500 XT (Navi 14, `gfx1012`, RDNA1). A AMD
nunca deu suporte oficial a RDNA1 no ROCm, e o ROCm não está instalado — só há RADV
(Vulkan). Habilitá-lo exigiria build da comunidade com `HSA_OVERRIDE_GFX_VERSION`,
frágil e desproporcional ao ganho.

**Decisão:** inferência em CPU. O Xeon E5-2666 v3 (10c/20t, 31 GiB) sustenta o
MuScriptor `small`/`medium`.

**Consequência:** o tamanho do modelo é um trade-off de tempo, medido na Fase 0.
Cache por estágio deixa de ser conforto e vira requisito.

---

## ADR-003 — MuScriptor como motor de transcrição
**Data:** 2026-09-21 · **Status:** aceito

MuScriptor (Kyutai + Mirelo, arXiv 2607.08168, jul/2026) reporta Onset F1 **60,4**
contra **32,5** do YourMT3+ no mesmo teste. Código MIT, pesos CC BY-NC 4.0 (ok para
uso pessoal). Transcreve a mix direto — não exige separação — e já faz quantização,
detecção de tempo, MusicXML e PDF.

**Decisão:** MuScriptor é o transcritor, atrás do `Protocol Transcriber`.

**Consequência — o que o Thoth escreve de código próprio:** o MuScriptor entrega
tablatura só em **PDF**, sem configuração de afinação nem de 5 cordas. O valor deste
repositório é (1) GP5 **editável**, (2) fret assignment com afinação configurável,
(3) sanity-check de oitava, (4) cache/orquestração/UI.

**Consequência — o que deixa de ser construído por padrão:** Demucs, Beat This! e
quantizador próprio saem do caminho crítico e viram condicionais, só justificados por
evidência medida na Fase 0. Limitação conhecida: notas sobrepostas do mesmo
instrumento degradam o F1 (60,4 → 51,8) — irrelevante para baixo, que é monofônico.

---

## ADR-004 — Python fixado em 3.12
**Data:** 2026-09-21 · **Status:** aceito

O MuScriptor exige Python 3.10–3.12. O Python de sistema da Pandora é 3.14.7, e um
`requires-python = ">=3.12"` resolveria para 3.14 e quebraria na instalação.

**Decisão:** `requires-python = ">=3.12,<3.13"` e `.python-version` = 3.12. O uv
gerencia o interpretador; o Python do sistema não é tocado.

---

## ADR-005 — Ingestão do YouTube via yt-dlp
**Data:** 2026-09-21 · **Status:** aceito · **Revisa:** ADR-001

O ADR-001 manteve a ingestão restrita a arquivo local e deixou o yt-dlp fora do
repositório. O usuário pediu explicitamente o suporte a link do YouTube, ciente de
que isso contraria os termos de uso da plataforma.

**Decisão:** `YtDlpSource` implementa `AudioSource` ao lado de `LocalFileSource`, e
`resolver_fonte()` despacha pela forma da referência (URL http(s) → YouTube).

**Decisão de implementação:** chamar o **binário do sistema**, não a biblioteca
Python. O yt-dlp quebra sempre que o YouTube muda, e o binário do pacman se atualiza
junto com o sistema, sem tocar no `uv.lock`. O custo é depender do PATH — aceito.

**Consequências:**
- `source_id` = `yt_<video_id>`, sem baixar para calcular hash. Cache hit não toca a rede.
- `meta.json` ao lado do WAV guarda título/artista/duração, para o cache hit não
  precisar de rede só para saber o nome da música.
- Teste `@pytest.mark.network` funciona como **canário**: quando o YouTube quebrar o
  yt-dlp, ele falha e aponta o `pacman -Syu`.
- Áudio baixado e stems **nunca** são versionados nem redistribuídos.
- O ADR-001 continua valendo para Spotify, YouTube Music e Amazon Music (DRM).

---

## ADR-006 — Avaliação não depende do ouvido do usuário
**Data:** 2026-09-21 · **Status:** aceito

O plano original media a qualidade da Fase 0 pedindo ao usuário que comparasse a
transcrição com músicas cujo baixo ele soubesse tocar. Ele está **começando a
aprender** e não toca nada ainda — o critério era inexequível, e avaliar por ouvido
inexperiente produziria uma decisão pior do que não avaliar.

**Decisão:** a avaliação passa a ter três camadas, nenhuma exigindo habilidade
instrumental:

1. **Objetiva (principal):** ground truth sintético — MIDI conhecido → fluidsynth +
   soundfont → WAV → pipeline → `mir_eval` Onset F1. Sobe da Fase 2 para a Fase 0,
   porque agora é o critério primário, não um complemento.
2. **Perceptual assistida:** auralização do MuScriptor (original em um canal, MIDI
   transcrito no outro). Descolamento é audível por qualquer pessoa, sem treino.
3. **Referência externa:** comparar com tablatura humana publicada de uma música
   conhecida, para conferir oitava e notas sem precisar tocar.

**Consequência de produto — o iniciante muda as prioridades:**
- O `FretAssigner` ganha um **modo iniciante**: preferir primeira posição, cordas
  soltas e trastes baixos. Para quem começa, tocabilidade vale mais que otimização
  de deslocamento.
- O controle de andamento do alphaTab (estudar a 50–70%) sobe de "opcional" para
  funcionalidade central: é a ferramenta de estudo de fato.
