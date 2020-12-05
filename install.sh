
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
        libatlas-base-dev

python3 -m pip install --upgrade pip wheel setuptools
python3 -m pip uninstall -y ledfx
python3 -m pip uninstall -y ledfx-dev
rm -rf ~/.venv/ledfx-venv
python3 -m venv ~/.venv/ledfx-venv
export PATH=$PATH:$HOME/.venv/ledfx-venv/bin
cd ~/.venvs/ledfx-venv
git clone -b dev https://github.com/shauneccles/LedFx/
python3 -m pip install -r ~/.venvs/ledfx-venv/LedFx/requirements.txt
python3 ~/.venvs/ledfx-venv/LedFx/etup.py build
python3 ~/.venvs/ledfx-venv/LedFx/setup.py install
echo "#!/usr/bin/env bash
export PATH=$PATH:$HOME/.venvs/ledfx-venv/bin
ledfx" > /usr/local/bin/ledfx
chmod +x /usr/local/bin/ledfx
echo " Please type ledfx to launch LedFx"