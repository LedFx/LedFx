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

There is no installation required, the application is portable.

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

3.  Launch LedFx with the `open-ui` option to launch the browser:

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
    $ brew install python@3.9
    $ brew install portaudio --HEAD
    $ brew install virtualenv
    $ virtualenv -p python3.9 ~/ledfx-venv
    $ source ~/ledfx-venv/bin/activate
    $ pip install --force-reinstall ledfx
    ```

2.  If you get a numpy/aubio error please do the following:

    ``` console
    $ pip uninstall numpy aubio
    $ pip install numpy --no-cache-dir
    $ pip install aubio --no-cache-dir
    ```

3.  Launch LedFx with the `open-ui` option to launch the browser:

    ``` console
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


