#!/usr/bin/env bash
# shellcheck disable=SC1090

apt-get update
apt-get install -y --no-install-recommends \
        libatlas3-base \
        libavformat58 \
        portaudio19-dev \
        pulseaudio
npm install -g yarn
apt-get clean -y
apt-get autoremove -y
rm -rf /var/lib/apt/lists/*