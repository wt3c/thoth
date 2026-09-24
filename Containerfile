# Thoth em contêiner, só CPU (ADR-040).
#
# Os pesos do MuScriptor NÃO entram na imagem (CC BY-NC 4.0, ADR-005): o cache do
# HuggingFace da máquina é montado como volume pelo `compose.yaml`. O demucs e o
# MuScriptor continuam sendo baixados pelo `uvx` no primeiro uso, para o volume do
# cache do uv — a imagem não carrega torch.

# --- alphaTab: `npm pack` só existe aqui, a imagem final não leva Node ------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS alphatab
RUN apt-get update \
    && apt-get install -y --no-install-recommends npm \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY scripts/vendor_alphatab.py scripts/
RUN mkdir web && uv run --no-project python scripts/vendor_alphatab.py

# --- aplicação ---------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fluidsynth fluid-soundfont-gm \
    && rm -rf /var/lib/apt/lists/* \
    # O Debian instala o soundfont em /usr/share/sounds/sf2; a auralização o procura
    # onde o Arch o põe.
    && mkdir -p /usr/share/soundfonts \
    && ln -s /usr/share/sounds/sf2/FluidR3_GM.sf2 /usr/share/soundfonts/FluidR3_GM.sf2

# O yt-dlp do Debian envelhece rápido demais para o YouTube: vai pelo uv, fora do projeto.
ENV UV_TOOL_DIR=/opt/uv-tools UV_TOOL_BIN_DIR=/usr/local/bin
RUN uv tool install yt-dlp

RUN useradd --create-home --uid 1000 thoth \
    # Os volumes nomeados herdam o dono do ponto de montagem: sem isto nascem de root.
    && install -d -o thoth /home/thoth/.cache/uv /home/thoth/.cache/torch \
        /home/thoth/.cache/huggingface
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src/ src/
COPY web/ web/
COPY --from=alphatab /app/web/vendor web/vendor
# Sem `chown`: o app só escreve em /data, e o chown recopiaria o venv inteiro numa camada.
RUN uv sync --frozen --no-dev

USER thoth
ENV PATH=/app/.venv/bin:$PATH
EXPOSE 8000
# 0.0.0.0 dentro do contêiner; quem restringe ao localhost é o `ports` do compose.
CMD ["thoth", "serve", "--host", "0.0.0.0", "--out", "/data/out", "--cache", "/data/cache"]
