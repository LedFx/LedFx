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
whiptail --msgbox --backtitle "Welcome to LedFx Installer" --title "LedFx automated installer" "\\n\\nThis installer will transform your device into a LedFx powered LED driver for networked LEDs! \\n\\n\\n\\nPlease visit ledfx.app or the LedFx Discord if you have any issues" "${r}" "${c}"
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
python3 -m pip -q uninstall -y ledfx
python3 -m pip -q uninstall -y ledfx-dev
sudo systemctl stop ledfx
sudo systemctl disable ledfx
sudo rm /etc/systemd/system/ledfx.service
curruser=$USER
IP=$(/sbin/ip -o route get to 8.8.8.8 | sed -n 's/.*src \([0-9.]\+\).*/\1/p')
rm -rf ~/ledfx-workdir
echo "Downloading and installing latest version from github"
python3 -m pip install git+https://github.com/LedFx/LedFx@dev
echo "Adding" $curruser "to Audio Group"
sudo usermod -a -G audio $curruser
whiptail --yesno "Are you using a USB sound device for input?" --yes-button "Yes" --no-button "No" "${r}" "${c}"
USB=$?
if [ "$USB" = "0" ]; then
  echo "Updating alsa.conf - backup created in /usr/share/alsa/alsa.conf.bak"
  sudo sed --in-place=.bak 's/defaults.ctl.card 0/defaults.ctl.card 1/' /usr/share/alsa/alsa.conf
  sudo sed -i 's/defaults.pcm.card 0/defaults.pcm.card 1/' /usr/share/alsa/alsa.conf
fi
whiptail --yesno "Create Audio loopback for sound playing from this device?" --yes-button "Yes" --no-button "No" "${r}" "${c}" 
LOOPBACK=$?

if [ "$LOOPBACK" = "0" ]; then

  sudo modprobe snd-aloop
  echo "Adding alsa loopback to /etc/modules for next boot"
  echo "snd-aloop" | sudo tee -a /etc/modules

fi
whiptail --yesno "Create service so LedFx launches automatically on boot?" --yes-button "Yes" --no-button "No" "${r}" "${c}"
SERVICE=$?
if [ "$SERVICE" = "0" ]; then

echo "Creating Service"
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
echo "You may need to restart your pi for the sound device to be accessable"

else

echo "LedFx is now installed. Please type ledfx to start."
fi
