================================
How to: Create and edit virtuals
================================

This page is intended to give guidance on how to use virtuals.

Virtuals are a way to create a "virtual" device that can be assigned its own active effects. The virtual is then mapped into other devices.

With virtuals it is possible to

- Have multiple physical devices running exectly the same effect, fully synchonised, irrespective of led count
- Spread a single effect across multiple physical devices to slice that effect up into portions that are displayed on different devices
- Use multiple strips or matrix blocks to make one large matrix, as long as they are vertically stacked

Devices vs Virtuals
-------------------

Under the covers, in the dark depths of the LedFx code, there is a single virtual created for each device, automagically. it is these virtuals that the user interacts with via the UI, when assigning effects.

So mapping new virtuals to devices, is really mapping new virtuals to other virtuals, its virtuals all the way down.

Segments
--------

When building virtuals, they are made up of **segments** of devices, you can select any range of pixels in any order. They don't have to be complete devices, and the can be easily reversed.

Creating a virtual
------------------

To add a new virtual, click on the large **+ icon** at the bottom of the user interface and select **Add Virtual**

.. image:: /_static/howto/virtuals/virtuals1.png
   :alt: press the + icon


This will open the **Add Virtual Device** dialog

.. image:: /_static/howto/virtuals/virtuals2.png
   :alt: Add Virtual Device dialog


Thats a lot of options!!! Don't worry, we can ignore most of them, but lets go over them all anyway first.

1. **Name** - Give the virtual a name, this is what you will see in the UI, make it meaningful, once you have a hand full of physical devices, and your own virtuals on top, you want to be able to find what you are looking for.

2. **Grouping** - This is a way to group pixels in a virtual or device into 1 pixel from the effect perspective, imagine you had a device with 10 LEDs but you want them to be treated as 1 pixel, you would set the grouping to 10. Generally leave this to default 1

3. **Mapping** - Important! This is where you select how the effect will be mapped into the segments that make up the virtual

   - **span** - A single instance of the active effect will be spread across all the segments that make up the virtual

   - **copy** - A copy of the active effect will be displayed on each segment that makes up the virtual

4. **icon name** - This is the icon that will be displayed in the UI, select something that makes sense to you. It is a string entry field, supported icons and their string mappings can be found at `Material Design Icons <https://pictogrammers.com/library/mdi/>`_

5. **Max Brightness** - This is the maximum brightness that the virtual will display at, from 0 to 1. Generally leave at 1

6. **Center Offset** - Pixel count by which to offset the center of the virtual when applying effects. Generally leave at 0

7. **Preview Only** - Preview the effect wihout updating the real devices. Generally leave off.

8. **Transition Time** - Length of transition when switching between effects.

9. **Transition Mode** - How to blend between old and new effects during transition. Modes are Add, Dissolve, Push, Slide, Iris, Through White, Through Black, None. Default is Add.

10. **Frequency Min** - Use to limit the low end of the frequency range for audio effects on this virtual.

11. **Frequency Max** - Use to limit the high end of the frequency range for audio effects on this virtual.

12. **Rows** - Number of rows in the virtual. For a 1d strip this is 1. For a 2d Matrix, set as desired. For example a 512 pixel 16 columns by 8 rows, would need this value set to 8.

Once all of these have been configured, the next step is to add and setup the segments that make up the virtual. So press the button handily marked as **Add and Setup Segments**

Adding Segments
---------------

.. image:: /_static/howto/virtuals/virtuals3.png
   :alt: Add and Setup Segments

We are ready to add our first segment, press the **Add Segment** button

.. image:: /_static/howto/virtuals/virtuals4.png
   :alt: Select Segment

Hit the drop down and a list of all devices will appear, select the device from which you want to assign your first segment

.. image:: /_static/howto/virtuals/virtuals5.png
   :alt: Our first segment setup

In this case we have selected a relatively large WLED based matrix that is 32x32 = 1024 pixels. By default, all the pixels on the device have been added.

The live physical device will show an animated white pattern with a dark bar moving through it, this is an aid to adjusting where you want the virtual segment to be by observing the changes live.

It is white as this is the current segment being edited.

.. raw:: html

   <picture>
      <source srcset="../_static/howto/virtuals/virtuals6.gif" type="image/webp">
      <img src="../_static/howto/virtuals/virtuals6.gif" alt="Active Segment">
   </picture>

If we now set the start and end values by dragging the blue blobs, we can change the range for this segment

.. image:: /_static/howto/virtuals/virtuals7.png
   :alt: Adjusting the segment

The live physical device will also update the white wash pattern to indicate the change as it is adjusted.

.. raw:: html

   <picture>
      <source srcset="../_static/howto/virtuals/virtuals8.gif" type="image/webp">
      <img src="../_static/howto/virtuals/virtuals8.gif" alt="Active Segment">
   </picture>
