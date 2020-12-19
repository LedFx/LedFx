
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
sudo apt-get install -y gcc \
        git \
        libatlas3-base \
        libavformat58 \
        portaudio19-dev \
        pulseaudio \
        python3-pip

python3 -m pip install  --upgrade pip wheel setuptools
python3 -m pip uninstall -y ledfx
python3 -m pip uninstall -y ledfx-dev
curruser=$USER
IP=$(/sbin/ip -o route get to 8.8.8.8 | sed -n 's/.*src \([0-9.]\+\).*/\1/p')
sudo rm -rf ~/ledfx-workdir
mkdir ~/ledfx-workdir
cd ~/ledfx-workdir
git clone --depth 1 -b dev https://github.com/LedFx/LedFx
cd ~/ledfx-workdir/LedFx
python3 -m pip install --user -r ~/ledfx-workdir/LedFx/requirements.txt
python3 ~/ledfx-workdir/LedFx/setup.py build
python3 ~/ledfx-workdir/LedFx/setup.py install --user
echo "Adding" $curruser "to Audio Group"
sudo usermod -a -G audio $curruser
sudo rm /etc/systemd/system/ledfx.service
echo "[Unit]
Description=LedFx Music Visualizer
After=network.target
Wants=network-online.target
StartLimitIntervalSec=0
[Service]
Type=simple
Restart=always
RestartSec=1
User="$curruser"
ExecStart=/home/"$curruser"/.local/bin/ledfx
[Install]
WantedBy=multi-user.target
" >> ~/ledfx-workdir/ledfx.service
sudo cp ~/ledfx-workdir/ledfx.service /etc/systemd/system/ledfx.service
sudo systemctl enable ledfx 
sudo systemctl start ledfx
echo "LedFx is now running. Please navigate to "$IP":8888 in your web browser"
