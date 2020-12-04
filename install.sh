#!/usr/bin/env bash
# shellcheck disable=SC1090
cd ~
mkdir ledfx-workdir
cd ledfx-workdir
git pull -b dev https://github.com/ahodges9/LedFx/
cd LedFx
pip install -e .
python setup.py build
python setup.py install