FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=0
ARG TARGETARCH
WORKDIR /app
RUN --mount=type=cache,id=apt-cache-${TARGETARCH},target=/var/cache/apt,sharing=locked \
    --mount=type=cache,id=apt-lib-${TARGETARCH},target=/var/lib/apt,sharing=locked \
    apt update && apt install -y cmake gcc portaudio19-dev && rm -rf /var/lib/apt/lists/*
COPY uv.lock pyproject.toml /app/
RUN --mount=type=cache,id=uv-cache-${TARGETARCH},target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev --no-editable 
COPY . /app
RUN --mount=type=cache,id=uv-cache-${TARGETARCH},target=/root/.cache/uv \
    uv sync --extra hue --frozen --no-editable

FROM python:3.12-slim AS runner
ARG TARGETARCH
RUN --mount=type=cache,id=apt-cache-${TARGETARCH},target=/var/cache/apt,sharing=locked \
    --mount=type=cache,id=apt-lib-${TARGETARCH},target=/var/lib/apt,sharing=locked \
    apt update && apt install -y libportaudio2 pulseaudio --no-install-recommends && rm -rf /var/lib/apt/lists/*
#FROM runner
ENV HOME="/home/ledfx"
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PULSE_SERVER="unix:$HOME/.config/pulse/pulseaudio.socket"
ENV PULSE_COOKIE="$HOME/.config/pulse/cookie"
RUN groupadd --gid 1000 ledfx \
  && useradd --uid 1000 --gid 1000 --create-home --home-dir "$HOME" ledfx \
  && usermod -aG audio,pulse,pulse-access ledfx \
  && chown -R ledfx:ledfx "$HOME"
WORKDIR "$HOME"
COPY ./ledfx_docker/pulse /etc/pulse
COPY --chmod=755 --chown=1000:1000 ./ledfx_docker/start.sh $HOME/start.sh
COPY --from=build --chown=1000:1000 /app/.venv /app/.venv
ARG GITHUB_SHA
ARG IS_RELEASE
ENV GITHUB_SHA=$GITHUB_SHA
ENV IS_RELEASE=$IS_RELEASE
USER ledfx
HEALTHCHECK --interval=60s --timeout=3s --start-period=3s --retries=3 \
  CMD pactl info > /dev/null 2>&1 || exit 1
EXPOSE 8888/tcp
ENTRYPOINT ["/home/ledfx/start.sh"]
LABEL org.opencontainers.image.source="https://github.com/LedFx/LedFx"
LABEL org.opencontainers.image.description="LedFx makes your LEDs dance to audio"
#build with "docker build -f ledfx_docker/Dockerfile -t ledfx ."