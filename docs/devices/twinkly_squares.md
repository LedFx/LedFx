# Twinkly Squares Device

**Twinkly Squares** are modular LED panel systems that can be arranged in various configurations. LedFx now supports Twinkly Squares devices through their realtime UDP protocol, enabling audio-reactive visualizations on these LED panels.

```{Warning}
ONLY rectangular configurations are supported, for example 6 panels can be 1x6, 2x3, 3x2 and 6x1

Non-rectangular layouts, such as winding shapes are not supported.
```

## Overview

Twinkly Squares are Wi-Fi connected LED panels featuring:
- **8×8 LED matrix per panel** (64 LEDs per square)
- **Modular design** - combine multiple panels into larger displays
- **Wi-Fi connectivity** - control over local network
- **Realtime protocol support** - low-latency streaming from LedFx

Each Twinkly Squares panel contains 64 individually addressable RGB LEDs arranged in an 8×8 grid. Multiple panels can be combined to create larger displays.

## Device Requirements

- Twinkly Squares device(s) connected to your local network
- IP address of the Twinkly Squares controller
- Number of panels in your configuration

The Twinkly Squares must be preconfigured via the Twinkly app to have generated the layout mappings. Ledfx will consume this mapping information, LedFX cannot generate this independantly.

## Setup

### Finding Your Twinkly Device IP Address

1. Open the Twinkly app on your smartphone
2. Select your Twinkly Squares device
3. Go to device settings
4. Note the IP address displayed

Alternatively, check your router's DHCP client list for devices with "Twinkly" in the name.

### Adding Twinkly Squares in LedFx

1. In LedFx, go to **Devices** → **Add Device**
2. Select **TwinklySquares** from the device type list
3. Configure the device parameters (see below)
4. Click **Add Device**

## Device Configuration

### Name
A friendly name for your device in LedFx.

- **Example**: "Living Room Squares", "Desk Panels"

### IP Address
The IPv4 address of your Twinkly Squares controller on your local network.

- **Example**: `192.168.1.100`

### Panel Count
The number of 8×8 Twinkly Squares panels in your configuration.

- **Default**: 1
- **Minimum**: 1
- **Example**: If you have 4 panels arranged in a 2×2 grid, set this to `4`

The pixel count is automatically calculated as `64 × panel_count`. You don't need to manually set the pixel count.

```{Warning}
Currently, LedFX does not automatically set the row count for the device. It must be changed from its default value of 1, Click the down arrow, on the top right of you new device, select Settings and edit the ROWS value accordingly. For a 3 height by 2 wide squares panel configuration, rows would be 3 squares x 8 pixels = 24 rows.
```

### Icon Name
The icon displayed in the UI. Can be from Material Design Icons (MDI) or Material UI Icons (MUI).

- **MDI format**: `mdi:<icon-name-in-kebab-case>`
  - [Material Design Icons](https://pictogrammers.com/library/mdi/)
  - Example: `mdi:grid`
  
- **MUI format**: `<IconNameInCamelCase>`
  - [Material UI Icons](https://mui.com/material-ui/material-icons/)
  - Example: `GridOn`

### Center Offset
Simple offset for effect mapping into the device pixel layout. Unless you have specific reasons, leave this at 0.

### Refresh Rate
Rate at which effects are updated and pushed to the device. It is not known what frame rate Twinkly Squares can actually support. If issues are seen with default 62, try an aggressive reduction to 30, and then increase frame rate until things start to fail again.

## Technical Details

### Automatic Coordinate Mapping

LedFx automatically handles the complex coordinate mapping required for Twinkly Squares as long as the Twinkly Squares have been preconfigured in the Twinkly App:

1. **Layout Discovery**: When the device activates, LedFx queries the Twinkly device for its LED layout coordinates
2. **Grid Calculation**: The actual grid dimensions are calculated from the coordinate distribution
3. **Permutation Mapping**: A permutation array is built to map LedFx's raster-order pixels to Twinkly's native layout
4. **Coordinate Normalization**: LED positions are normalized and mapped to the correct grid positions

This all happens automatically - you don't need to configure any coordinate mappings manually.

### Realtime Protocol

The device uses Twinkly's realtime UDP protocol for low-latency streaming:

- **Protocol Version 3**: Supports larger packets for efficient data transmission
- **Direct Frame Upload**: Frames are sent directly to the device via UDP

### Device Modes

When LedFx activates a Twinkly Squares device:
1. Device is turned on
2. Brightness is set to 100%
3. Device is switched to realtime mode (`rt`)
4. LedFx begins streaming pixel data

When deactivated:
- Device is returned to `movie` mode (default Twinkly mode)

### Pixel Count Auto-Configuration

The pixel count is automatically determined:
- **Initial**: Calculated as `64 × panel_count` based on your configuration
- **Verification**: Actual LED count is verified when device activates
- **Auto-Update**: If the actual count differs, the configuration is automatically updated and saved

This ensures your device configuration stays in sync with the physical hardware.

For more information about Twinkly products, visit [Twinkly's official website](https://www.twinkly.com/).
