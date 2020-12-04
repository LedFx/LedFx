#!/usr/bin/env bash
# shellcheck disable=SC1090
sudo apt-get update 
sudo apt-get install -y python3-pip \
        alsa-utils \
        libasound2 \
        libasound2-plugins \
        portaudio19-dev \
        pulseaudio
cd ~
mkdir ledfx-workdir
cd ledfx-workdir
git clone -b dev https://github.com/ahodges9/LedFx/
cd LedFx
pip3 install -r requirements.txt
python3 setup.py build
python3 setup.py install
rm -rf ~/ledfx-workdir/