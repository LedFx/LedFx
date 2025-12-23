# Assets Workflow

As of LedFx 2.1.3 all graphical assets are managed through the LedFx Asset Workflow.

Please see [Security](/security.md) for details of the security imperatives.

All user file assets must be stored within the .ledfx/assets directory.

LedFx supports GIF, PNG, JPEG, WebP, BMP, TIFF and ICO formats including animation where relevant.

Direct URLs for graphical assets are still supported.

To simplify the workflow, an asset management UX has been added, making adding, assigning and managing assets a drag-drop and click experience.

Additionally extensive caching and thumbnail capabilities have been added in the backend for a fast and efficient experience across local files and remote URLs.

This makes assigning assets to effects such as keybeat, gif player and image, and to controls such as scenes and playlists, far smoother.

## Adding files to the asset manager

To add files to the asset manager from your local machine UI, simply drag and drop the graphical asset into the LedFx browser window. This can be into any view within Ledfx.

### From a local file explorer

<video width="640" height="310" controls loop autoplay muted>
   <source src="../_static/settings/assets/file2browserSmall.mp4" type="video/mp4">
   Your browser does not support the video tag.
</video>
<br><br>

### From another browser instance

<video width="640" height="310" controls loop autoplay muted>
   <source src="../_static/settings/assets/browser2browserSmall.mp4" type="video/mp4">
   Your browser does not support the video tag.
</video>
<br><br>

## Asset Manager Interface

All assets available to Ledfx can be viewed in the Asset Manager interface, found on the settings page.

There are three main tabs within the Asset Manager

- User Assets, image files you have added directly from local drive space
- Built-in Assets, image files that come with LedFx for presets
- Cache, image files cached from user-provided URLs anywhere in the workflow

Various meta data related to the image assets can be seen according to the tab.
Additionally a user can delete images or refresh cache from the asset manager interface.

<video width="640" height="440" controls loop autoplay muted>
   <source src="../_static/settings/assets/assetManagerSmall.mp4" type="video/mp4">
   Your browser does not support the video tag.
</video>
<br><br>

## Using Assets in effects

Where supported by an effect, image assets can be selected with the asset picker from the relevant field.

The example below is from the keybeat effect

<video width="640" height="800" controls loop autoplay muted>
   <source src="../_static/settings/assets/keybeatSmall.mp4" type="video/mp4">
   Your browser does not support the video tag.
</video>
<br><br>

## Using Assets in Scenes and Playlists

The Scenes and Playlist interface supports attaching images, static or animated to the control buttons.

Other interface aspects are likely to be added in the future.

The asset picker example below is from the scenes interface.

<video width="640" height="800" controls loop autoplay muted>
   <source src="../_static/settings/assets/scenesSmall.mp4" type="video/mp4">
   Your browser does not support the video tag.
</video>
<br><br>

## Adding an asset from a URL

Any interface that supports image assets can also accept URLs.

The image will be cached on first access for future performance.

The asset will then be available for use in any other asset workflow.

The cache can be refreshed from the Asset Manager interface.

In the demonstration below, the URL is extracted directly from a browser view of the gif, through right-click, it could just as easily have been drag-and-drop'd.

<video width="640" height="800" controls loop autoplay muted>
   <source src="../_static/settings/assets/urlAndCacheSmall.mp4" type="video/mp4">
   Your browser does not support the video tag.
</video>
<br><br>

---

Implementation of the Asset Manager has been a necessary step on the LedFx journey, it's really transparent and accessible, enjoy!
