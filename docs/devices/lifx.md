# LIFX Device

**LIFX** smart lighting products connect directly to your Wi-Fi network without requiring a hub. LedFx provides comprehensive support for all LIFX device types including single bulbs, multizone strips, and 2D matrix devices.

## Supported Devices

LedFx supports the full range of LIFX products through the [lifx-async](https://github.com/Djelibeybi/lifx-async) library:

| Device Type | Examples                            | Zones | Notes |
|-------------|-------------------------------------|-------|-------|
| **Single Bulbs** | LIFX A19, BR30, GU10, Mini          | 1 | Single color output |
| **Multizone Strips** | LIFX Z Strip, Beam, Neon, String    | 8-82 | Per-zone color control |
| **Matrix Devices** | LIFX Tile, Candle, Path, Spot, Luna | Varies | Full 2D matrix support |
| **Ceiling Lights** | LIFX Ceiling (64 or 128 zones)      | 64-128 | Matrix downlight + single uplight |

## Key Features

### Auto-Detection

LedFx automatically detects your LIFX device type when you add it:

- **Device Type**: Bulb, strip, or matrix - no manual selection needed
- **Zone Count**: Automatically queried from the device
- **Matrix Dimensions**: Width and height discovered from device chain data
- **Capabilities**: Extended multizone, frame buffer requirements, etc.

After initial detection, device information is cached for faster reconnection.

## Setup

### Auto-Discovery (Recommended)

LedFx can automatically discover LIFX devices on your network. This is the easiest way to add LIFX devices.

#### Using the Setup Wizard

When you first launch LedFx, the setup wizard includes a LIFX option:

1. Enable the **LIFX** toggle in the device discovery section
2. Optionally configure discovery settings:
   - **Broadcast Address**: Default `255.255.255.255` works for most networks. For VLANs or specific subnets, enter the appropriate broadcast address (e.g., `192.168.1.255`)
   - **Timeout**: How long to scan for devices (default: 30 seconds)
3. Click **Next** to start scanning
4. Discovered devices are automatically added to LedFx

#### Using the Dashboard

You can scan for LIFX devices at any time from the Dashboard:

1. Click the **lightbulb icon** (💡) in the Dashboard action bar
2. A popover appears with discovery settings:
   - **Broadcast Address**: Network broadcast address for discovery
   - **Discovery Timeout**: Scan duration in seconds (1-120)
3. Click **Confirm** to start scanning
4. LedFx will poll for discovered devices during the timeout period

#### Using Global Actions

The Global Actions panel also provides LIFX scanning:

1. Expand the **Global Actions** section on the Dashboard
2. Click **Scan for LIFX devices**
3. Configure broadcast address and timeout in the popover
4. Click **Confirm** to begin discovery

```{tip}
Discovery settings are saved to your LedFx configuration, so you only need to configure them once.
```

### Manual Setup

If auto-discovery doesn't find your device (e.g., on a different VLAN), you can add it manually.

#### Finding Your LIFX Device IP Address

LIFX devices connect directly to your Wi-Fi network. To find the IP address:

1. **LIFX App**: Open the LIFX app, select your device, go to Settings > Device Info
2. **Router**: Check your router's DHCP client list for devices with "LIFX" in the name

```{tip}
Reserve a static IP address for your LIFX device in your router's DHCP settings. This ensures the device always has the same IP address after power cycles.
```

#### Adding a LIFX Device Manually

1. In LedFx, click the **(+)** icon and select **Add Device**
2. Select **LIFX** from the device type list
3. Enter a name for your device
4. Enter the IP address
5. Click **Add Device**

LedFx will automatically:
- Connect to the device
- Detect the device type (bulb, strip, or matrix)
- Query the zone/pixel count
- For matrix devices, discover the grid dimensions
- For Ceiling lights, create Downlight and Uplight sub-virtuals

## Device Configuration

### Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| **Name** | Friendly name for the device | Required |
| **IP Address** | IPv4 address of the LIFX device | Required |
| **Pixel Count** | Number of zones/pixels (auto-detected) | 1 |
| **Refresh Rate** | Target FPS for effect updates | 20 |
| **Create Segments** | Auto-create sub-virtuals for Ceiling lights | True |

### Refresh Rate Recommendations

LIFX devices have a recommended maximum refresh rate of 20 FPS to prevent visible strobing and ensure network stability:

| Device Type | Max FPS | Reason                              |
|-------------|---------|-------------------------------------|
| Single Bulbs | 20 | Higher rates cause visible strobing |
| Multizone Strips | 20 | Network stability consideration     |
| Matrix Devices | 20 | Balanced for smooth animation       |

The default refresh rate of 20 FPS works well for most use cases. LedFx automatically caps the rate based on device type. If you have a small number of devices and a sufficiently robust WiFi network, you can experiment with increasing the frame rate on a per device basis.

### Icon Name

The icon displayed in the LedFx UI. Supports Material Design Icons (MDI) or Material UI Icons (MUI):

- **MDI format**: `mdi:<icon-name-in-kebab-case>`
  - [Material Design Icons](https://pictogrammers.com/library/mdi/)
  - Example: `mdi:lightbulb`

- **MUI format**: `<IconNameInCamelCase>`
  - [Material UI Icons](https://mui.com/material-ui/material-icons/)
  - Example: `Lightbulb`

## Technical Details

### Device Type Detection

When a LIFX device is added, LedFx queries the device to determine its type. If a LIFX device has multiple zones, each zone gets its own color and brightness value.

| Device Type | Examples                                                       |
| ----------- |----------------------------------------------------------------|
| Light      | A19/A21, B22, BR30, E12, E14, E26, E27, GU10, PAR38, Downlight |
 | MultiZoneLight | LIFX Z, Lightstrip, Beam, Neon Flex, String                    |
| MatrixLight | LIFX Tile, Candle, Path, Spot, Luna, Tube                      |
| CeilingLight | LIFX Ceiling (Round), Ceiling 26" (Capsule)                    |

The detected type, serial number, and device class are saved to configuration for faster subsequent connections.

### Multizone Strip Protocol

For LIFX Z Strips, Beams, and Neon:

- **Extended Multizone**: Newer devices support sending all zone colors in a single packet
- **Legacy Multizone**: Older devices receive one zone at a time with a final "apply" command.

LedFx automatically detects and uses the appropriate protocol, though it is strongly recommended not to attempt to use a LIFX Z or Beam that does not support extended multizone messages as the animations are likely to overwhelm the device.

### Matrix Pixel Mapping

Matrix devices have a 2D arrangement of LEDs but use a permutation-based pixel reordering system:

1. LedFx queries the device chain to get tile positions (`user_x`, `user_y`)
2. A permutation array maps LedFx's row-major pixel order to the LIFX tile layout
3. This handles multi-tile configurations (original LIFX Tile) and single-tile matrix devices

The original LIFX Tile is the only Matrix device ever released that supported multiple tiles on its chain. All subsequent Matrix devices only have a single tile and don't support device chains. The LIFX Tile has been discontinued and is no longer available to purchase, but is still supported by LedFx.

The matrix width and height are computed from the tile coordinate data and used to automatically configure the virtual's row count for proper 2D effect rendering.

### Ceiling Light Sub-Virtuals

LIFX Ceiling lights are Matrix lights but they have two distinct light components:

- **Downlight**: The main matrix array (63 or 127 zones). Due to their shape, certain zones are not implemented as actual visible lights.
- **Uplight**: A single ambient light zone which is actually the last zone in the overall matrix, i.e. zone 64 or 128.

When `create_segments` is enabled (default), LedFx automatically creates two sub-virtuals for Ceiling lights, similar to WLED segments. This allows you to run different effects on the downlight and uplight independently.

### Frame Buffer Handling

Large matrix devices with more than 64 zones (currently only the LIFX Ceiling 26") use a double-buffering strategy to prevent visual tearing:

1. Pixel data is written to an off-screen buffer
2. The buffer is copied to the visible display in a single operation
3. This ensures smooth, tear-free updates

This is handled automatically - no configuration required.

### Color Conversion

LedFx effects output RGB values. These are converted to LIFX's HSBK (Hue, Saturation, Brightness, Kelvin) format using the `lifx-async` library's `HSBK.from_rgb()` method.

### Async Fire-and-Forget

To maintain high frame rates, LedFx sends packets to LIFX devices without waiting for acknowledgment. This "fire-and-forget" approach:

- Minimizes latency and frame drops due to network delays
- Relies on UDP's best-effort delivery as occasional dropped frames are acceptable for real-time visualization

However, if your WiFi is busy or saturated, performance will suffer. Things that can cause network saturation include streaming media and downloading large files.

## Troubleshooting

### Device Not Found

If LedFx cannot find your LIFX device:

1. Verify the device is powered on and connected to Wi-Fi
2. Check the IP address is correct (use the LIFX app to confirm)
3. Ensure your computer and LIFX device are on the same network/VLAN
4. Check for firewall rules blocking UDP traffic

### Strobing or Flickering

If effects appear to strobe or flicker:

1. Lower the refresh rate (try 15-20 FPS)
2. Ensure only one application is controlling the device
3. Check your Wi-Fi signal strength to the device

### Matrix Dimensions Incorrect

For matrix devices showing wrong dimensions:

1. Power cycle the LIFX device
2. Remove and re-add the device in LedFx
3. Check the device configuration in the LIFX app

### Ceiling Sub-Virtuals Not Created

If Downlight/Uplight sub-virtuals don't appear:

1. Ensure `create_segments` is enabled in device config
2. Remove and re-add the device
3. Check the logs for any detection errors

## Further Information

- [LIFX Developer Documentation](https://lan.developer.lifx.com/)
- [lifx-async Library](https://github.com/Djelibeybi/lifx-async)
- [LedFx Discord](https://discord.gg/xyyHEquZKQ) - For support and feedback
