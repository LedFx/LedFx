# Network & Performance Troubleshooting

The host system and networking in which LedFx and the client devices live, is a big space and there are MANY things that can wrong impacting your experience.

These normally start with "why does LedFx lag". We strive to ensure that LedFx runs smoothly where possible.

We are currently not aware of lag scenarios induced by LedFx itself ( yes, the more we say that, the more likely it is we have a deep dark dirty secret somewhere ).

Major efforts have removed sources of glitching, and we generally run heavy weight system regressions that will identify issues during development and release.

## Common sources of lag

LedFx can't tell you how to fix your system, but there are places your problem is likely to be from general experience.

### Underpowered host

Yes you can run LedFx on that dusty old Pi3 you had in a drawer, but LedFx cannot help with the underlying performance of the OS on the hardware. Yes, LedFx core is mostly written in python, but that is part of its charm for us developers, and anywhere we do heavy lifting of data and math, we strive to implement in numpy or other optimised libaries.

If you are running a reasonable system, and not trying to push around 100K pixels, noting we regularly test with 20K+, then your host should generally be able to cope. Look at processor loading, ensure there is headroom in there. If you are running multiple services on a constrained system, then LedFx can only use the time it is given. Do you have services spinning up aggressively at inopportune times, such a deep virus check across all your storage etc.

## Tools to investigate

### Diagnostic Effects

Some simple deterministic effects are built into LedFx to allow investigation of pixel progression and device syncronous time aligned behaviours without audio impacts.

Note that improvements in front end rendering via GPU acceleration have greatly improved the visualisation of the effects to meet realtime against the core. LedFx had always been written to service the physical devices as the priority, but this GPU advancement has removed many sources of delay to the browser front end, and if run on a local browser instance should be very tight to actuals.

#### Metro Effect

Metro runs a sequence that by default will display half black and half white for 300 ms every 1 second.

The pattern progresses further dividing by 2 the black and white division.

The default 4 step behaviour on a 1d strip is

![look mummy, zebras](/_static/howto/trouble/metro_strip.gif)

The behaviour with steps, the number of such divisions to make before looping, set to 6 on a 2d matrix is

![ah, my eyes!](/_static/howto/trouble/metro_array.gif)

By watching the browser visualisation, on a browser hosted on the same machine as LedFx to avoid any network implications, and comparing that to the behaviour on the physical device LEDs, it should be easy to identify if there is distinct Lag or pattern mismatch.

If there is a mismatch, then it implies that there is artifacting between the LedFx / browser visualisation running on the host and the endpoint itself. That artifacting could be due to network impacts, or even crashes and lags on the endpoint device.

Metro is good for looking at tight tracking between the LedFx core and the device as it should be reasonably possible to see the very simple pattern correlation and the dynamic hard changes from off to white on both at the same time.

If you have to use a remote browser instance to look at the visualisation, this introduces the risk of network delay impacting the visualisation as well, but can still be used to assess to some degree.

#### Pixels Effect

Pixel runs by default a single pixel from index 0 to the end of the strip or matrix in 1 second increments.

For a simple 16 pixel strip at default it looks like the following

![watching the pot](/_static/howto/trouble/pixel_strip1.gif)

This diagnostic effect can be used for various needs

- Ensure that the pixel mapping is smooth and consistant to expectation.
- Enusre that the periodic step is smooth and without jitter
  - For visualtion front end
  - For physical device
- General comparisson between front end visualisation and physical device

To investigate periodic step smoothness, looking for lag and jitter, it is better to turn the step period down to 0.1 seconds. This may also be needed for longer strips and matrix looking at ordering issues.

If the visualisation on the browser is smooth, but the device is lagging / jittery then the issue is in the network or device.

If the visualisation on the browser is NOT smooth then the host is glitching / underpowered or are you sure you are on a local browser?

![wheeee](/_static/howto/trouble/pixel_strip2.gif)

Using the BUILD UP switch will cumulatively fill the strip

![ahhhh](/_static/howto/trouble/pixel_strip3.gif)

For extreme cases turn up the pixels count to step in blocks.

![no one got time for that](/_static/howto/trouble/pixel_matrix1.gif)

### Talk about wled2graph

## Networking Improvements

###UDP Latency

LedFx is *extremely* latency sensitive and will expose inherit
weaknesses in WiFi. To minimize this, we reccomend:

1.  Disabling WiFi Sleep Mode on WLED.
2.  Minimize WiFi activity on your network - use ethernet where reasoanble. If you are a commercial operation and performance REALLY matters use ethernet.
3.  Ensure router is appropriate for number of devices and amount of traffic. Enterprise class routers are intended to support MANY more client devices that your average consumer grade.
4.  Attempting to ensure your WiFi access point is located in an appropriate area, and is using an appropriate WiFi channel. GIVE LINKS TO USERFULL WEBSITE FOR THIS

### DNS name resolution

If you are having difficulty with DNS name resolution and your devices are configured as mydevice.local for the ip address try giving them fixed IP addresses in your router and using those IP addresses in LedFx

### mDNS WLED crash issues

There are community reports of excessive mDNS traffic in the host network leading to intermittent WLED crashes as its mDNS support gets overloaded.

See https://quinled.info/wled-crashes-and-reboots-every-xx-minutes-mdns/

These may be attributed to HA and Matter implementation, but may also be due to other sources.

Try turning off mDNS support in WLED as recommended in the quinled article.

### Access via LAN

All current builds should be by default accessible from LAN - please ensure that you allow traffic from port 8888 from the host machine according to the firewall configuration of your OS or router.

## I only get something less than 480 LEDs in WLED

With a long led strip, of greater than 480 pixels, ledfx only seems to drive 480 or less.

### Maybe it's the network interface MTU

If the MTU of the networking interface on your host PC is not set to the common default 1500 bytes, fragmentation of the UDP packets that DDP is transported on, may cause issue with WLED at consumption of the DDP protocol

By default, LedFx splits up seperate DDP packets at 480 pixel boundaries. So for example in a 1024 pixels device, it will take 3 DDP over UDP packets to transmit a single frame of data. Each packet will have a max UDP size of 1492 bytes made up of headers plus 3 x 480 bytes for RGB data

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

#### On macOS

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
