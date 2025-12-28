# Scenes

Backend managed, collections of device and virtual settings activated via a single scene button or via [**Playlists**](/settings/playlists.md).

<video width="550" height="480" controls loop autoplay muted>
   <source src="../_static/settings/scenes/scenes_splash_shrunk.mp4" type="video/mp4">
   Your browser does not support the video tag.
</video>
<br><br>

In this capture we have two browser tabs side by side, so we can see scene activation and effect visualization in one view.

## [Example Config](/howto/example_config.md)

Examples shown in this overview are available in the [**Example Config**](/howto/example_config.md)

## Scenes tab

The scenes tab can be accessed by the bottom bar icon.

<img src="/_static/settings/scenes/scenes_tab.png" alt="press here" width="550px">

## Adding a Scene

Scenes can be added by capturing the current device and virtual state.

Select the Add Scene item from the (+) menu

<img src="/_static/settings/scenes/scene_add.png" alt="add me" width="550px">

Give your new scene a name...

<img src="/_static/settings/scenes/scene_name.png" alt="name me">

Edit your scene details. Such as adding an image from the asset manager.

The initial configuration is captured from the current active devices and virtuals.

If an effect is using a preset, it will be listed in the preset column.

Effects can be reselected from the dropdown on each row.
Presets can be selected for the current effect from the adjacent dropdown.

The final column is for **Action**, how the device / virtual will be treated by the Scene.

In this example we have modified the first 3 devices. Any device / virtual can be set to

**Activate** - Run the effect configuration captured in the scene.<br>
**Ignore** - No change will be made to the virtual / device on activating the scene.<br>
**Turn Black** - A solid black single color effect will be enforced to keep the device active but visually off.<br>
**Stop** - LedFx will stop sending data to the device, so endpoints such as WLED will revert to their local effect after a timeout.<br>

<img src="/_static/settings/scenes/scene_create.png" alt="edit me" width="550px">

Hit Save and your new Scene will be available in the Scenes Tab.

<img src="/_static/settings/scenes/scene_created.png" alt="done me" width="550px">

## Editing a Scene

A scene can be edited by selecting its 3-dot menu

<img src="/_static/settings/scenes/scene_3dot.png" alt="3 dot">

The same 3-dot menu also allows

Changing the display order of scenes with the < and > controls.<br>
Deleting a scene<br>

<img src="/_static/settings/scenes/scene_3dot_expand.png" alt="3 dot">

When editing a scene, all controls available at creation can be modified.

New devices added since scene creation will be displayed greyed out, with an **Ignore** action.<br>

The scene configuration will be over written on selecting save.

It is also possible to overwrite all device / virtual settings in a scene with the current live configuration by selecting **OVERWRITE**

<img src="/_static/settings/scenes/scene_overwrite.png" alt="3 dot">


