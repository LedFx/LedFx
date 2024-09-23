Artnet Device
=============

**Artnet** is a common implementation of DMX over Ethernet. It is widely used in the lighting industry and is supported by a large variety of devices.

For more information, see `Art-Net on Wikipedia <https://en.wikipedia.org/wiki/Art-Net>`_.

Pre and Post Amble
==================

To support Artnet devices, it is important to be able to set fixed values in channels that can be positioned before or after the RGB data, for example, to control brightness.

In LedFx, these values can only be static, but the simple implementation of **pre-amble** and **post-amble** values supports most simple devices. The pre-amble and post-amble fields can be treated as comma or space-separated values from the ``uint8`` range (0-255).

Common Use Cases
----------------

1. **Single Pixel RGB Device with Brightness Before RGB Data:**

   - Set the pre-amble to ``255`` for maximum brightness and leave the post-amble empty.
   - The resulting channel data sent to the Artnet device universe will be in the format::

     [255, R, G, B]

2. **Single Pixel RGB Device with Brightness After RGB Data:**

   - Set the post-amble to ``255`` for maximum brightness and leave the pre-amble empty.
   - The resulting channel data sent to the Artnet device universe will be in the format::

     [R, G, B, 255]

3. **Pixel RGB Device with Brightness and Additional Channels:**

   - Set the pre-amble to ``255, 0, 0, 0`` for maximum brightness with other channels turned off. Leave the post-amble empty.
   - The resulting channel data sent to the Artnet device universe will be in the format::

     [255, 0, 0, 0, R, G, B]

Device Repeat
=============

It is common to have multiple Artnet devices on one universe with the same channel format. Each device requires its own pre- and post-amble. The ``device_repeat`` field can be set to the number of pixels assigned to each device. LedFx will then consume that number of pixels serially, wrapping each set with pre- and post-amble sequences until all pixels are used. Any leftover pixels are ignored.

If ``device_repeat`` is set to ``0``, all pixels are sent to the first device, wrapped with the pre- and post-amble sequences.

Examples
--------

- **Pixel Count:** 6
- **Pre-amble:** ``255``
- **Post-amble:** ``0, 0``

With ``device_repeat`` set to ``0``::

    [255, RGB1, RGB2, RGB3, RGB4, RGB5, RGB6, 0, 0]

With ``device_repeat`` set to ``1`` (6 endpoints with 1 pixel each)::

    [255, RGB1, 0, 0, 255, RGB2, 0, 0, 255, RGB3, 0, 0, 255, RGB4, 0, 0, 255, RGB5, 0, 0, 255, RGB6, 0, 0]

With ``device_repeat`` set to ``2`` (3 endpoints with 2 pixels each)::

    [255, RGB1, RGB2, 0, 0, 255, RGB3, RGB4, 0, 0, 255, RGB5, RGB6, 0, 0]

With ``device_repeat`` set to ``3`` (2 endpoints with 3 pixels each)::

    [255, RGB1, RGB2, RGB3, 0, 0, 255, RGB4, RGB5, RGB6, 0, 0]

With ``device_repeat`` set to ``4`` (1 endpoint with 4 pixels, last 2 pixels dropped)::

    [255, RGB1, RGB2, RGB3, RGB4, 0, 0]
