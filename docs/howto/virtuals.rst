================================
How to: Create and edit virtuals
================================

This page is intended to give guidance on how to use virtuals.

Virtuals are a way to create a "virtual" device that can be assigned its own active effects. The virtual is then mapped into other virtuals or devices.

With virtuals it is possible to

- Have multiple physical devices running exectly the same effect, fully synchonised, irrespective of led count
- Spread a single effect across multiple physical devices to slice that effect up into portions that are displayed on different devices
- Use multiple matrix to make one large matrix, as long as they are vertically stacked

Devices vs Virtuals
-------------------

Under the covers, in the dark depths of the LedFx code, there is a single virtual created for each device, automagically. it is these virtuals that the user interacts with via the UI, when assigning effects.

So mapping new virtuals to devices, is really mapping new virtuals to other virtuals, its virtuals all the way down.

Segments
--------

When building virtuals, they are made up of **segments** of devices, you can select any range of pixels in any order. They don't have to be complete devices.

Creating a virtual
------------------

To add a new virtual, click on the large **+ icon** at the bottom of the user interface and select **Add Virtual**

.. image:: /_static/howto/virtuals/virtuals1.png
   :alt: press the + icon


This will open the **Add Virtual Device** dialog

.. image:: /_static/howto/virtuals/virtuals2.png
   :alt: Add Virtual Device dialog


Thats a lot of options!!! Don't worry, we can ignore most of them, but lets go them all anyway first.

1) **Name** - Give the virtual a name, this is what you will see in the UI, make it meaningful, once you have a hand full of physical devices, and your own virtuals on top, you want to be able to find what you are lookng for.

2) **Grouping** - Advanced feature. This is a way to group pixels in a virtual or device into 1 pixel from the effect perspective, imagine you had a device with 10 LEDs but you want them to be treated as 1 pixel, you would set the grouping to 10.

3) **Mapping** - Important! This is where you select how the effect will be mapped into the segments that make up the virtual

- **span** - The effect will be spread across all the segments that make up the virtual