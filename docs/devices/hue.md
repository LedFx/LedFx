# Philips Hue Device

LedFx streams to **Philips Hue** lights through the bridge's Entertainment
API: frames go to the bridge over an encrypted DTLS connection on UDP, and
the bridge drives every light in one Entertainment area.

## Requirements

- A Hue bridge on the same network as LedFx.
- An Entertainment area set up in the Hue app, containing the lights you
  want LedFx to drive.

Hue works on every Python version LedFx supports. No extra system package
is needed.

## Setup

1. In the Hue app, create an Entertainment area and note its name.
2. Press the link button on the Hue bridge.
3. Within 30 seconds, in LedFx click the big (+) icon and select
   **Add Device**, then select **Hue**.
4. Enter the bridge's IP address or hostname, and the Entertainment area's
   name as the group name. The name match ignores case.
5. Save. LedFx pairs with the bridge, stores the credentials, and reads
   the area's lights.

If the error says to press the link button, press it and add the device
again. If it says to set up the Entertainment area, check the area exists
in the Hue app and that its name matches.

## Pixels

The device has one pixel per channel of the Entertainment area, in the
order the bridge lists them. LedFx sends 30 frames a second.

## Pairing again

If the bridge forgets LedFx, for example after a bridge reset or after
removing LedFx from the Hue app, LedFx pairs again the next time it
starts. Press the link button on the bridge, then restart LedFx within
30 seconds.
