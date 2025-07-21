# Radial

TODO: Add better youtube video or similar

This is a simple example using strobe and power effects as inputs to the Radial effect.

<video width="426" height="720" controls loop>
   <source src="../../_static/effects/matrix/radial/radial1.mp4" type="video/mp4">
   Your browser does not support the video tag.
</video>
<br><br>

## Overview

Radial is an effect that allows you to map the rendered output of an existing source virtual running another effect into the render space of the current virtual.

It is intended that the target virtual for the Radial effect is a matrix.

The source virtuals pixel data is rendered into the target virtual with a sweep like mapping.

This can lead to exotic and sometime quite unexpected and impactful matrix effects.

The following demonstrations are based on using a dummy 1d strip of 128 pixels as the source and a 64 x 64 dummy matrix as the target. 

For help in setting up dummy devices

See [Dummy Vumeter How-To](/howto/dummy_vumeter.md) for a 1d strip as the source. We will name our example strip1.

See [Dummy Matrix How-To](/howto/dummy_matrix.md) for a 2d matrix as the target. We will name our example matrix1.

All sources are stetched to fit, so beyond performance, there is no need to match source virtual to the target.

As matrix1 consists of 64x64 = 4096 pixels, all visualisation examples are with settings / Pixel Graphs / Frontend Pixels set to 4096.


## Settings

TODO