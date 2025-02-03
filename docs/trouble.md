# Troubleshooting

## Firmware Issues

### WLED

> -   Sending data, WLED going into E1.31 mode but lights not working?
>     -   Try turning off multicast and setting the start universe to 1.
> -   As long as the universe size is set to 510 LedFx should output to
>     all pixels. Maybe something in the code is not working past 1
>     universe as 1 universe is 170 LEDs
> -   Make sure \"disable WiFi sleep\" is ticked in WiFi Settings on the
>     WLED web interface.
> -   How many devices do you have?
>     -   Try 1 WLED device to start and work your way up to see where
>         the problem lies, whilst monitoring your computer performance
>         usage.
> -   Determine if it's a networking problem: Try pinging the device -
>     any large variances in ping will cause issues - LedFx is extremely
>     latency sensitive. Command prompt ping the IP address of the WLED
>     device. For example: ping 192.168.1.101

### ESPixelStick

The ESPixelStick firmware is extremely streamlined and by far the lowest
latency option.

ESPixelStick will drive all LEDs via the RX pin (like any real pixel
pusher FW should do) and will let you have thousands of LEDs in any
pixel order you want. The problem with the code is, it can\'t handle
more than a single universe, which limits you to 170 pixels. More
advanced FW will consume input spanning multiple universes.

## LedFx Configuration File

Did you try host: 0.0.0.0 or host: your-ipv4 (i.e.: 192.168.1.10)? The
127 is your localhost internal network and running anything on that
subnet will only be available from that device. Putting it on 0.0.0.0 or
your host\'s LAN IP opens up the port, 8888 in our case, to other
devices on your LAN from your host\'s IP.

## Ledfx Configuration File Corruption Recovery

If you are concerned that your ledfx config.json is corrupted.

Everything was working and you changed an effect setting or similar, and
now things no longer work, even if you restart / reboot / reinstall, it
is likely that the config.json has persisted a configuration that is
triggering a bug and causeing a crash from startup.

We will be very interested in a copy of your config.json file, please
share in discord with context.

There are two methods which can be used to attempt recovery

### Clear all active effects

Launch ledfx and clear all active effects from config.json

> ``` console
> ledfx --clear-effects
> ```

If the issue is a poisoned configration of a specific effect, using this
launch option all active effects are cleared leaving all virtuals and
other configurations untouched.

The effect configuration will still be present in your config, and if
the specific effect is re-enabled, the crash will likely express again.

However with this method, you can recover and continue using ledfx with
the other effects, and all your existing configuration.

You can also isolate which effect is poisoned by re-enabling them one by
one, until the crash expresses.

Then pass your config.json to the ledfx team for further investigation
via #help_and_support on Discord.

### Backup and create clean config

Launch ledfx, backup and then create a clean config.json

> ``` console
> ledfx --clear-config
> ```

This nuclear option will first backup, then completely clear your
existing config.json, resolving any possible config poisoning.

Note the backup json file will be named according to the following
format

config_backup_YYYY-MM-DD_HH-MM-SS.json

It will be in the .ledfx directory along with the ledfx.log instances

Please note: This is a dotfile naming convention and may be hidden by
default in your file manager.

.ledfx directory will be located in a number of possible locations
according to OS.

Examples of being, but not limited to, the following locations

Windows:

> ``` console
> C:\Users\username\AppData\Roaming\.ledfx
> %appdata%\.ledfx
> ```

Linux:

> ``` console
> /home/username/.ledfx
> ~/.ledfx
> ```

MacOS:

> ``` console
> /Users/username/.ledfx
> ~/.ledfx
> ```

## Speaker Sound

My solution to this exact problem is ChromeCast audios, I have two in a
group and ChromeCast to the group. One of them is connected to my DAC
that is then connected to my amplifiers, and another is connected to a
line in on my computer in a separate room that LedFx is running on.

They\'re perfectly synchronized, but if you need to, you can do a delay
on any of the ChromeCasts within the group to adjust sync.

### Windows:

For setting up \"Stereo Mix\" recording device , please see
<https://thegeekpage.com/stereo-mix/>

If \"Stereo Mix\" is not picking up any sound, your \"Playback\" device
is probably digital (e.g.: HDMI) and external tool must be used. See the
\"Directing Audio\" documentation page.

### Squeezebox Server - Logitech

MultiRoom: <https://www.picoreplayer.org/>

### VBAN audio sync

Using Voicemeeter use VBAN, also allows mobile phone app to play your
audio. Needs a little tinkering between multi speaker devices for ms
delay. Make sure you have static IP addresses for your device and it
does support up to 4 outgoing devices streams.

Alternatively:
<https://www.audioanimals.co.uk/news/reviews/v-player-2-review-free-standalone-vst-host>

## Networking Improvements

**DPC Latency**

LedFx is *extremely* latency sensitive and will expose inherit
weaknesses in WiFi. To minimize this, we reccomend:

1.  Disabling WiFi Sleep Mode on WLED.
2.  Minimize WiFi activity on your network - using ethernet where
    possible.
3.  Ensure router appropriate for number of devices and amount of
    traffic.
4.  Attempting to ensure your WiFi access point is located in an
    appropriate area, and is using an appropriate WiFi channel.

**Access via LAN**

All current builds should be able to be accessed from LAN - please
ensure that you allow traffic from port 8888 from the host machine.

## I only get something less that 480 leds in WLED

With a long led strip, of greater than 480 pixels, ledfx only seems to drive 480 or less.

### Maybe its the network interface MTU

If the MTU of the networking interface on your host PC is not set to the common default 1500 bytes, fragmentation of the UDP packets that DDP is transported on, may cause issue with WLED at consumption of the DDP protocol

By default ledfx splits up seperate DDP packets at 480 pixel boundaries. So for example in a 1024 pixels device, it will take 3 DDP over UDP packets to transmit a single frame of data. Each packet will have a max UDP size of 1492 bytes made up of headers plus 3 x 480 bytes for RGB data

If the MTU of the network interface is less that 1500, the UDP packets will get fragmented, and its possible that WLED will only service the first fragment and ignore the remaining fragement and all folllowing DDP packets until the next frame cycle.

If any interface has less that 1500 it is recommended to fix it to 1500. Use Chatgpt or other sources to resolve exact steps for your system.

### Checking your MTU
#### On Windows

Open Powershell and run

``` console
Get-NetIPInterface | Select-Object InterfaceAlias, AddressFamily, NlMtu
```

#### On Linux

```console
ip link show
```

#### On Mac OSX

```console
ifconfig | grep mtu
```

## Need more help?

Reach out to the LedFx team through Discord. Preferably copy and paste
with your answers below

> -   New build/recent upgrades?
> -   python version?
> -   LedFx version you are using?
> -   restarted your PC and issue continues?
> -   any changes/deleted your LedFx config file?
> -   Problem:
