# How to: Pixel mapped virtual matrix

Not all LED matrix come in regimented rows and columns, what if you want to arbitrarily map a 2d effect to your physical devices in wierd and wonderful ways?

This is possible in LedFx

::: warning
**Warning:**
This feature is in heavy early development, it's too useful to hide, but it will be quirky until it's not!

Functionality and compatability may mutate!

Be part of the feedback loop to get it to what we collectively aspire to be!
:::

First we need to create a virtual in which to implement our mapping.

![You should know this by now](/_static/howto/mapping/create_virtual_1.png)

Then name your virtual and set rows to any value above 1 to identify this as a matrix

![Though shalt count at least 2](/_static/howto/mapping/create_virtual_2.png)

On pressing "add & setup segments" you should end up in this screen where classicaly you can add segments of existing devices.

We however, want to create a mapping. As we identified this virtual as a matrix, there will be two new buttons in the top left for switching between this classic view and the mapping view.

![Down the rabbit hole](/_static/howto/mapping/create_virtual_3.png)

Press the matrix icon, and you will enter the mapping edit screen. Note the rows and columns in this case are currently set at 2, and you can see a 2 by 2 grid.

![Deeper down](/_static/howto/mapping/mapping_matrix_1.png)

Slide rows and columns to the values you wish to be the matrix visualisation from which you will map towards your physical devices. Your effect of choice will be rendered onto this matrix at normal runtime, then according to your hand crafted mapping, be projected onto your physical devices!

For our purposes, lets use 25 rows by 15 columns

The grid will scale accordingly, but we are zoomed in

![Deeper down](/_static/howto/mapping/mapping_matrix_2.png)

We can zoom out with the mouse wheel to see the full grid, as well as pan with the left mouse button.

![Deeper down](/_static/howto/mapping/mapping_matrix_3.png)

To map your first pixel right click your mouse on a pixel and select a device towards which you wish to map that pixel.

![It's getting stuffy down here](/_static/howto/mapping/mapping_matrix_4.png)

Select the precise pixel individually

![And it's geting dark](/_static/howto/mapping/mapping_matrix_5.png)

Or through the assign multiple switch, map a range. Note the slider now has a start and end node

![And it's geting dark](/_static/howto/mapping/mapping_matrix_6.png)

Hit save, and your pixels will be populated. note this image has been zoomed back in via the mouse wheel for readability.

![And it's geting dark](/_static/howto/mapping/mapping_matrix_7.png)

From here it's a matter of building up your full arbitrary mapping from the source matrix towards your devices. Allowing mapping into any 2d or 3d layout space.


::: warning
**Warning:**
Put stuff and saving and loading here...
:::

