# Playlists

Backend time-driven [**Scenes**](/settings/scenes.md) based playlists are now supported.

This framework will allow future development of mood-driven scene selection.

<video width="640" height="300" controls loop autoplay muted>
   <source src="../_static/settings/playlists/playlist_shrunk.mp4" type="video/mp4">
   Your browser does not support the video tag.
</video>
<br><br>

## [Example Config](/howto/example_config.md)

Examples shown in this overview are available in the [**Example Config**](/howto/example_config.md)

## Playlist tab

The playlist configuration tab can be accessed via two methods

### Settings Scene Playlists

Hit the big button!

![Hit me](/_static/settings/playlists/settings_playlist.png)

### Bottom Task Bar Playlists

Adding the Playlist button to the bottom bar must be enabled via

<img src="/_static/settings/playlists/bottom_bar_playlists.png" alt="You're Barred" width="550px">

### Playlists examples

This video starts by showing the available scenes in the example config.

We then open the playlists tab via the bottom bar and can see that there are three existing examples.

We will edit "My first playlist" via the 3-dot menu.

We edit the playlist button image, switch to shuffle mode, rather than sequence, shuffle the order of some of the scenes ( which won't matter as we are in shuffle mode ) and then save the changes.

Finally we activate "My first playlist", monitor the playlist playback via the left widget, and watch the devices with the playlists cycling the scenes.

<video width="550" height="700" controls loop>
   <source src="../_static/settings/playlists/playlist_demo1_shrunk.mp4" type="video/mp4">
   Your browser does not support the video tag.
</video>
<br><br>

### Edit Playlist Dialog

**Playlist Name** Put your new playlist name here.<br>
**Default duration** Any added scenes will inherit the default duration.<br>
**Default Mode** play in **Sequence** or **Shuffle** order every full cycle of playlist.<br>
**Image** Use the asset manager to quickly select an asset to attach an image to the playlist.

![All the things](/_static/settings/playlists/edit_playlist.png)

**If no scenes are selected ALL scenes will be used in the playlist**

To add scenes, select from the dropdown.

![Just pick one](/_static/settings/playlists/select_scene.png)

All scenes can be added in one click with **ADD ALL SCENES**

![lots of scenes](/_static/settings/playlists/scenes_list.png)

Scene order for **Sequence** Mode can be adjusted with the arrows to the left in the scene list to move scenes up and down.

The individual scene time can be edited, and any scene can be removed from the list with the red trash can.

By turning on Jitter, a random adjustment to the scene time can be applied according to the set range.

![shake](/_static/settings/playlists/jitter.png)

To commit changes, just hit **CREATE** for a new playlist or **SAVE** if you are editing.

### Playlist Widget

The playlist widget allows direct control of the active playlist.

It can be used to **pause** or **stop** the playlist.<br>
The current scene can be bumped with the **prev** / **next** icons.<br>
The **sequence** or **shuffle** icon on the right can be used to switch the playlist playback mode.

![widget](/_static/settings/playlists/widget.png)
