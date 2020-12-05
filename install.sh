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
        git
pip3 remove -y ledfx
pip3 remove -y ledfx-dev
cd ~
mkdir ledfx-workdir
cd ledfx-workdir
git clone -b dev https://github.com/ahodges9/LedFx/
cd LedFx
pip3 install -r requirements.txt
python3 setup.py build
python3 setup.py install
rm -rf ~/ledfx-workdir/