FROM python:3.12 AS build
RUN apt update && apt install -y cmake gcc portaudio19-dev && rm -rf /var/lib/apt/lists/*
RUN python -m venv /ledfx/venv && python -m pip install --no-cache-dir -U pip wheel setuptools
ENV PATH="/ledfx/venv/bin:$PATH"
RUN python -m pip install --no-cache-dir ledfx


FROM python:3.12-slim AS runner
RUN apt update && apt install -y libportaudio2 pulseaudio --no-install-recommends && rm -rf /var/lib/apt/lists/*

FROM runner
ENV HOME="/home/ledfx"
ENV PATH="/ledfx/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PULSE_SERVER="unix:$HOME/.config/pulse/pulseaudio.socket"
ENV PULSE_COOKIE="$HOME/.config/pulse/cookie"
COPY --from=build /ledfx/venv /ledfx/venv
COPY ./pulse /etc/pulse
COPY --chmod=755 start.sh $HOME/start.sh

RUN useradd --create-home --home-dir "$HOME" --uid 1000 ledfx \
	&& usermod -aG audio,pulse,pulse-access ledfx \
	&& chown -R ledfx:ledfx "$HOME"
WORKDIR "$HOME"
USER ledfx

HEALTHCHECK --interval=60s --timeout=3s --start-period=3s --retries=3 \
  CMD pactl info > /dev/null 2>&1 || exit 1
EXPOSE 8888/tcp
ENTRYPOINT ["/home/ledfx/start.sh"]
#build with "docker build -t ledfx ."
#Sourced from https://hub.docker.com/r/ssankur/ledfx for ledfx docker part and https://github.com/jessfraz for pulseaudio part and some ChatGPT assistance.