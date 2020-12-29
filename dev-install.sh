#!/usr/bin/env bash
# shellcheck disable=SC1090
if [ -t 0 ] ; then
  screen_size=$(stty size)
else
  screen_size="24 80"
fi
# Set rows variable to contain first number
printf -v rows '%d' "${screen_size%% *}"
# Set columns variable to contain second number
printf -v columns '%d' "${screen_size##* }"

# Divide by two so the dialogs take up half of the screen, which looks nice.
r=$(( rows / 2 ))
c=$(( columns / 2 ))
# Unless the screen is tiny
r=$(( r < 20 ? 20 : r ))
c=$(( c < 70 ? 70 : c ))
whiptail --msgbox --backtitle "Welcome to LedFx Installer" --title "LedFx automated installer" "\\n\\nThis installer will transform your device into a LedFx powered LED driver for networked LEDs! \\n\\n\\n\\nPlease visit ledfx.app or the LedFx Discord if you have any issues" "${r}" "${c}"
curl -sSL https://install.ledfx.app/ledfxrainbow.out | cat
sudo apt-get update
sudo apt-get install -y gcc \
        git \
        libatlas3-base \
        libavformat58 \
        portaudio19-dev \
        pulseaudio \
        python3-pip
python3 -m pip install  --upgrade pip wheel setuptools
echo "Removing prior ledfx installation data"
python3 -m pip -q uninstall -y ledfx 2> /dev/null
python3 -m pip -q uninstall -y ledfx-dev 2> /dev/null
sudo systemctl stop ledfx 2> /dev/null
sudo systemctl disable ledfx 2> /dev/null
sudo rm /etc/systemd/system/ledfx.service 2> /dev/null
curruser=$USER
IP=$(/sbin/ip -o route get to 8.8.8.8 | sed -n 's/.*src \([0-9.]\+\).*/\1/p')
echo "Downloading and installing latest version from github"
python3 -m pip install git+https://github.com/LedFx/LedFx@dev
echo "Adding" $curruser "to Audio Group"
sudo usermod -a -G audio $curruser
whiptail --yesno "Install LedFx as a service so it launches automatically on boot?" --yes-button "Yes" --no-button "No" "${r}" "${c}"
SERVICE=$?
if [ "$SERVICE" = "0" ]; then

echo "Installing LedFx Service"
echo "[Unit]
Description=LedFx Music Visualizer
After=network.target sound.target
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=5
User="$curruser"
Group=audio
ExecStart=/usr/bin/python3 /home/"$curruser"/.local/bin/ledfx
[Install]
WantedBy=multi-user.target
" >> ~/ledfx.service
sudo mv ~/ledfx.service /etc/systemd/system/ledfx.service
sudo systemctl enable ledfx
sudo systemctl start ledfx
sudo systemctl status ledfx
echo "LedFx is now running. Please navigate to "$IP":8888 in your web browser"
echo "If you have no audio devices in LedFx, please run 'sudo raspi-config' and setup your audio device (System Devices -> Audio)"

else

echo "LedFx is now installed. Please type ledfx to start."
echo "If you have no audio devices in LedFx, please run 'sudo raspi-config' and setup your audio device (System Devices -> Audio)"
fi
