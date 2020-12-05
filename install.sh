#!/usr/bin/env bash
# shellcheck disable=SC1090
echo "  _                   _   ______                          ";
echo " | |                 | | |  ____|                         ";
echo " | |        ___    __| | | |__    __  __                  ";
echo " | |       / _ \  / _\` | |  __|   \ \/ /                  ";
echo " | |____  |  __/ | (_| | | |       >  <                   ";
echo " |______|  \___|  \__,_| |_|      /_/\_\                  ";
echo "  _____                 _             _   _               ";
echo " |_   _|               | |           | | | |              ";
echo "   | |    _ __    ___  | |_    __ _  | | | |   ___   _ __ ";
echo "   | |   | '_ \  / __| | __|  / _\` | | | | |  / _ \ | '__|";
echo "  _| |_  | | | | \__ \ | |_  | (_| | | | | | |  __/ | |   ";
echo " |_____| |_| |_| |___/  \__|  \__,_| |_| |_|  \___| |_|   ";
echo "                                                          ";

sudo apt-get update
sudo apt-get install -y python3-pip \
        alsa-utils \
        libasound2 \
        libasound2-plugins \
        portaudio19-dev \
        pulseaudio \
        git \
        build-essential \

python3 -m pip install --upgrade pip wheel setuptools
python3 -m pip uninstall -y ledfx
python3 -m pip uninstall -y ledfx-dev

sudo rm -rf ~/ledfx-workdir
mkdir ~/ledfx-workdir
cd ~/ledfx-workdir
git clone -b dev https://github.com/shauneccles/LedFx/
cd ~/ledfx-workdir/LedFx
python3 -m pip install -r ~/ledfx-workdir/LedFx/requirements.txt
python3 ~/ledfx-workdir/LedFx/setup.py build
sudo python3 ~/ledfx-workdir/LedFx/setup.py install
sudo rm -rf ~/ledfx-workdir/
echo " Please type ledfx to launch LedFx"