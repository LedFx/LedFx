FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=0
WORKDIR /app
RUN apt update && apt install -y cmake gcc portaudio19-dev && rm -rf /var/lib/apt/lists/*
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev \
	uv pip install /app/ledfx
#RUN python -m venv /ledfx/venv && python -m pip install --no-cache-dir -U pip wheel setuptools
#ENV PATH="/ledfx/venv/bin:$PATH"
#RUN python -m pip install --no-cache-dir ledfx


FROM python:3.12-slim AS runner
RUN apt update && apt install -y libportaudio2 pulseaudio --no-install-recommends && rm -rf /var/lib/apt/lists/*

FROM runner
ENV HOME="/home/ledfx"
ENV PATH="/ledfx/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PULSE_SERVER="unix:$HOME/.config/pulse/pulseaudio.socket"
ENV PULSE_COOKIE="$HOME/.config/pulse/cookie"
COPY --from=build --chown=1000:1000 /app/.venv /ledfx/venv
COPY ./ledfx_docker/pulse /etc/pulse
COPY --chmod=755 --chown=1000:1000 ./ledfx_docker/start.sh $HOME/start.sh

RUN useradd --create-home --home-dir "$HOME" --uid 1000 ledfx \
	&& usermod -aG audio,pulse,pulse-access ledfx \
	&& chown -R ledfx:ledfx "$HOME"
WORKDIR "$HOME"
USER ledfx

HEALTHCHECK --interval=60s --timeout=3s --start-period=3s --retries=3 \
  CMD pactl info > /dev/null 2>&1 || exit 1
EXPOSE 8888/tcp
ENTRYPOINT ["/home/ledfx/start.sh"]
LABEL maintainer="www.github.com/ledfx/ledfx"
#build with "docker build -t ledfx ."
#Sourced from https://hub.docker.com/r/ssankur/ledfx for ledfx docker part and https://github.com/jessfraz for pulseaudio part and some ChatGPT assistance.