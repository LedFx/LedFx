#!/usr/bin/env bash
# shellcheck disable=SC1090
sudo apt-get install python3-pip
cd ~
mkdir ledfx-workdir
cd ledfx-workdir
git clone -b dev https://github.com/ahodges9/LedFx/
cd LedFx
pip install -e .
python setup.py build
python setup.py install