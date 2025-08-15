# Installation and Setup

LedFx is a network controller that aims to enable synchronization of
multiple lights across a network. To be able to add your LED strips to
LedFx your device needs to be capable of receiving data via one of the
supported protocols. See below for a list of tested ESP8266 firmware
that can be used with LedFx.

Here is everything you need to get started with LedFx:

> 1.  A Computer (or Raspberry Pi) with Python \>= 3.9
> 2.  An E1.31 capable device with addressable LEDs connected

Here is a list of tested ESP8266 firmware that works with LedFx:

> -   [WLED](https://github.com/Aircoookie/WLED) is preferred and has
>     lots of great firmware effects (ESP32/ESP8266)
> -   [ESPixelStick](https://github.com/forkineye/ESPixelStick) is a
>     great E1.31 based firmware
> -   [Scott's Audio Reactive ESP8266](https://github.com/scottlawsonbc/Reactive-LED) is another option

## Windows Installation

To get started on Windows the easiest option is to [download the latest
release](https://download.ledfx.app).

There is no installation required, the application is portable. From within the unzipped folder, navigate up into the folder containing LedFx.exe

Launch LedFx with the `--open-ui` option to launch the back end and automatically open the front end in the browser:

``` console
$ .\LedFx.exe --open-ui
```

## Linux Installation

To install on Linux first ensure you have at least Python 3.9 installed.

1.  Install LedFx and all the dependencies using pipx:

    ``` console
    $ python -m pip install ledfx
    ```

2.  Run LedFx!

    ``` console
    $ ledfx
    ```

## macOS Installation

To install on macOS first ensure you have at least Python 3.9 installed.

1.  Install LedFx and all the dependencies using
    [homebrew](https://docs.brew.sh/Installation) and pip:

    ``` console
    $ brew install portaudio
    $ python3 -m pip install ledfx
    ```

2.  Alternatively, install LedFx in a [python
    venv](https://docs.python.org/3/tutorial/venv.html):

    ``` console
    $ python3 -m venv ~/ledfx-venv
    $ source ~/ledfx-venv/bin/activate
    $ python -m pip install -U pip setuptools wheel
    $ python -m pip install ledfx
    ```

3.  Launch LedFx with the `--open-ui` option to launch the back end and automatically open the front end in the browser:

    ``` console
    $ ledfx --open-ui
    ```

## macOS Installation (Apple Silicon)

To install on macOS (Apple Silicon) first ensure you have at least
Python 3.9 installed.

1.  Install LedFx and all the dependencies using
    [homebrew](https://docs.brew.sh/Installation) in a [python
    venv](https://docs.python.org/3/tutorial/venv.html):

    ``` console
    $ brew install python@3.12
    $ brew install python@3.12
    $ brew install portaudio --HEAD
    $ brew install virtualenv
    $ virtualenv -p python3.12 ~/ledfx-venv
    $ virtualenv -p python3.12 ~/ledfx-venv
    $ source ~/ledfx-venv/bin/activate
    $ pip install numpy~=1.23 --no-cache-dir
    $ export CFLAGS="-Wno-incompatible-function-pointer-types"
    $ pip install aubio==0.4.9 --no-cache-dir
    $ pip install numpy~=1.23 --no-cache-dir
    $ export CFLAGS="-Wno-incompatible-function-pointer-types"
    $ pip install aubio==0.4.9 --no-cache-dir
    $ pip install --force-reinstall ledfx
    $ ledfx --open-ui
    $ ledfx --open-ui
    ```

2.  If you get a numpy/aubio error please do the following:

    ``` console
    $ pip uninstall numpy aubio
    $ pip install numpy~=1.23 --no-cache-dir
    $ pip install aubio==0.4.9 --no-cache-dir
    $ pip install numpy~=1.23 --no-cache-dir
    $ pip install aubio==0.4.9 --no-cache-dir
    ```

3.  Launch LedFx with the `--open-ui` option to launch the back end and automatically open the front end in the browser:

    ``` console
    $ source ~/ledfx-venv/bin/activate
    $ ledfx --open-ui
    ```

## Raspberry Pi Installation

<!-- Warning Box -->
<div style="border: 2px solid red; padding: 10px; background-color: #f8d7da; color: #721c24; border-radius: 5px;">
  <strong>Warning!</strong> This installation method is still in development. Use at your
discretion.
</div>
<br>
<!-- Note Box -->
<div style="border: 2px solid blue; padding: 10px; background-color: #d1ecf1; color: #0c5460; border-radius: 5px;">
  <strong>Note:</strong> To use LedFx on a pi you will need a USB audio card.
</div>
<br>
Verify you have Python 3.9 or greater by running `python3 --version`

**1.** Modify /usr/share/alsa/alsa.conf:

We need to change the default audio card from the built-in hardware on
the pi to the USB audio card in use.

``` console
$ sudo nano /usr/share/alsa/alsa.conf
```

Look for the following lines and change them accordingly:

FROM:

``` shell
defaults.ctl.card 0
defaults.pcm.card 0
```

TO:

``` shell
defaults.ctl.card 1
defaults.pcm.card 1
```

**2.** Install LedFx and all the dependencies using our [LedFx Bash
Install Script](https://install.ledfx.app):

``` console
$ curl -sSL https://install.ledfx.app/ | bash
```

## Docker

LedFx can be run in a Docker container with some limitations – graphical entity-based features such as **Clone** will not work.

Prebuilt multi-architecture images are published to:  
- **GitHub Container Registry (GHCR)**: [ghcr.io/ledfx/ledfx](https://ghcr.io/ledfx/ledfx)  
- **Docker Hub**: [hub.docker.com/r/ledfxorg/ledfx](https://hub.docker.com/r/ledfxorg/ledfx)  

Example pull commands:  

```bash
# From GHCR
docker pull ghcr.io/ledfx/ledfx:latest

# From Docker Hub
docker pull ledfxorg/ledfx:latest
```

Tags:  
- `latest` – most recent stable release  
- `edge` – development build from the `main` branch


### Pulseaudio

There are two modes of running LedFx container with different behaviours of pulseaudio.  

In pulseaudio server mode, pulseaudio is run as ledfx user and exposes pulseaudio socket at $HOME/.config/pulse/pulseaudio.socket.  

This socket can be shared to other applications which support pulseaudio, such as [shairport-sync](https://github.com/mikebrady/shairport-sync), or such players.  

The following guideline has been tailored to linux docker-compose or portainer stack.

### LedFx container in pulseaudio server mode

1. Create a folder "pulse" as your primary user with UID:GID=1000:1000

    ``` console
    $ mkdir -p ~/ledfx/pulse
    $ sudo chown 1000:1000 ~/ledfx/pulse
    ```

2. Docker-compose sample below should get LedFx running with pulseaudio socket in the folder ~/ledfx/pulse.

    ``` yaml
    volumes:
      ledfx-config:
    services:
      ledfx:
        image: ghcr.io/ledfx/ledfx:latest
        container_name: ledfx
        restart: on-failure:3
        network_mode: host
        command: ["--offline", "--clear-effects"] #optional command line arguments passed to LedFx
        volumes:
        - ledfx-config:/home/ledfx/ledfx-config:rw # Path to LedFx configuration files
        - $HOME/ledfx/pulse:/home/ledfx/.config/pulse:rw # Necessary when running in pulseaudio server mode. /path/to/ledfx/pulse should be with read write access for UID:GID=1000:1000
    ```

3. The below code can be appended to enable shairport-sync to play audio into LedFx container.

    ``` yaml
      shairportforledfx:
        image: mikebrady/shairport-sync:latest
        container_name: shairportforledfx
        restart: on-failure:3
        command: -o pa #Use this only if you do not provide a custom shairport-sync.conf file with pulseaudio backend.
        depends_on:
        ledfx:
          condition: service_healthy #so that the pulseaudio socket is available before being mounted here
        environment:
        - PULSE_SERVER="unix:/tmp/pulseaudio.socket" # Path for PulseAudio socket
        - PULSE_COOKIE="/tmp/cookie" # Path for PulseAudio cookie
        volumes:
        #- /path/to/shairportforledfx/shairport-sync.conf:/etc/shairport-sync.conf # Customised Shairport Sync configuration file. Ensure pulseaudio backend is selected. Suggested to set the ignore_volume_control to "yes" in general settings in shairport-sync.conf
        - /path/to/ledfx/pulse:/tmp # PulseAudio socket when using that backend
        logging:
        options:
          max-size: "200k"
          max-file: "10"
        network_mode: host
    ```

4. The following can be appended to run another shairport-sync to play audio to audio hardware.

    ``` yaml
      shairportaudio:
        image: mikebrady/shairport-sync:latest
        container_name: shairportaudio
        restart: unless-stopped
        devices:
        - "/dev/snd"
        volumes:
        - $HOME/shairportaudio/shairport-sync.conf:/etc/shairport-sync.conf # Customised Shairport Sync configuration file.
        logging:
        options:
          max-size: "200k"
          max-file: "10"
        networks:
        spsnet:
          ipv4_address: 192.168.1.234

    networks:
      spsnet:
        name: spsnet
        driver: macvlan
        driver_opts:
        # this is the hardware network interface of the docker host (ifconfig)
        parent: eth0
        ipam:
        config:
          # this is the subnet on which the docker host resides
          # set in a range outside of the primary DHCP server
          - subnet: 192.168.1.0/24
            gateway: 192.168.1.2 # this is the IP address of the docker host
            #use ip range 232 to 239 when using /29 as CIDR
    ```

5. A complete [docker-compose.yml](https://github.com/LedFx/LedFx/blob/main/ledfx_docker/docker-compose-example.yml) is available for a quick start.

### LedFx container in pulseaudio client mode

In LedFx pulseaudio client mode, LedFx container latches on to host's pulseaudio socket for audio input. Ensure the default recording input device is selected using pavucontrol or similar [pulseaudio command](https://wiki.archlinux.org/title/PulseAudio/Examples#Set_default_input_source) before starting the container. An assumption is that the default user is set to autologin in a headless setup, without which pulseaudio will not be running. This can cause issues when restarting the system, since docker containers usually start without a user login. Restart/recreate the container in that situation after logging in.

1. Docker-compose sample below should get LedFx running in pulseaudio client mode.

    ``` yaml
    volumes:
      ledfx-config:
    services:
      ledfx:
        image: ghcr.io/ledfx/ledfx:latest
        container_name: ledfx
        restart: on-failure:3
        network_mode: host
        command: ["--offline", "--clear-effects"] #optional command line arguments passed to LedFx
        environment:
          - PULSECLIENTMODE=1 # Set to anything to use the PulseAudio client mode Ensure correct default source is set in host pulseaudio Eg using pactl set-default-source
        volumes:
        - ledfx-config:/home/ledfx/ledfx-config:rw # Path to LedFx configuration files
        - /run/user/1000/pulse/native:/home/ledfx/.config/pulse/pulseaudio.socket # Necessary when running in pulseaudio client mode, to access host's PulseAudio socket
        - $HOME/.config/pulse/cookie:/home/ledfx/.config/pulse/cookie:ro # Necessary when running in pulseaudio client mode, to access host's PulseAudio cookie
    ```

## Device Firmware

Please visit one of the following links to obtain firmware for your
ESP8266/ESP32 device that works with LedFx.

> -   [ESPixelStick](https://github.com/forkineye/ESPixelStick)
>
>     > -   Compatible Devices:
>     >     -   ESP8266
>     >     -   `Configuration Settings </configuring>`{.interpreted-text
>     >         role="doc"}
>
> -   [Scott\'s Audio Reactive
>     Firmware](https://github.com/scottlawsonbc/audio-reactive-led-strip)
>
>     > -   Compatible Devices:
>     >     -   ESP8266
>     >     -   `Configuration Settings </configuring>`{.interpreted-text
>     >         role="doc"}
>
> -   [WLED](https://github.com/Aircoookie/WLED)
>
>     > -   Compatible Devices:
>     >     -   ESP8266
>     >     -   ESP32
>     >     -   `Configuration Settings </configuring>`{.interpreted-text
>     >         role="doc"}


