#!/bin/bash
set -eu
echo "Cleaning up old PulseAudio files..."
rm -rf "$HOME/.config/pulse/"* || echo "Failed to clean Pulseaudio files. Check permissions on mounted folder."
echo "Starting pulseaudio"
pulseaudio --daemonize=yes --disallow-module-loading --log-target=stderr --disable-shm=yes --exit-idle-time=-1 --load="module-native-protocol-unix auth-anonymous=1 auth-cookie-enabled=0 socket=$HOME/.config/pulse/pulseaudio.socket" --load="module-always-sink"
sleep 1
echo "Starting ledfx"
exec ledfx -c "$HOME/ledfx-config" "$@"
