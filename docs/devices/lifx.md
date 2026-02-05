# LIFX Device

**LIFX** smart lighting products connect directly to your Wi-Fi network without requiring a hub. LedFx provides comprehensive support for all LIFX device types including single bulbs, multizone strips, and 2D matrix devices.

Something to keep in mind about LIFX's matrix products: they are heavily diffused. If you're trying to display text or anything that requires sharpness between pixels, find something else. However, if you want really good plasma or lava-lamp-style effects, this is the hardware for you.

## Supported Devices

LedFx supports the full range of LIFX products through the [lifx-async](https://github.com/Djelibeybi/lifx-async) library:

| Device Type          | Examples                            | Zones          | Notes                  |
| -------------------- | ----------------------------------- | -------------- | ---------------------- |
| **Single Bulbs**     | LIFX A19, BR30, GU10, Mini          | 1              | Single color output    |
| **Multizone Strips** | LIFX Z Strip, Beam, Neon, String    | Varies (8-120) | Per-zone color control |
| **Matrix Devices**   | LIFX Tile, Candle, Path, Spot, Luna | Varies         | Full 2D matrix support |
| **Ceiling Lights**   | LIFX Ceiling (64 or 128 zones)      | 64-128         | Full 2D matrix support |

```{tip}
The LIFX Candle, Path, and Spot are matrix devices, but with very few actual pixels. For example, the Path and Spot are 2x3. They create nice smooth mixes, but can't really display things like equalizers or text.
```

## Key Features

### Auto-Detection

LedFx automatically detects your LIFX device type when you add it, including number of zones, or the matrix dimensions.

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

The Global Actions panel on the Detailed Dashboard also provides LIFX scanning:

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

LIFX devices connect directly to your Wi-Fi network. To find the IP address, check your router's DHCP client list for devices with "LIFX" in the name.

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

## Device Configuration

### Parameters

| Parameter        | Description                            | Default  |
| ---------------- | -------------------------------------- | -------- |
| **Name**         | Friendly name for the device           | Required |
| **IP Address**   | IPv4 address of the LIFX device        | Required |
| **Pixel Count**  | Number of zones/pixels (auto-detected) | 1        |
| **Refresh Rate** | Target FPS for effect updates          | 30       |

### Refresh Rate Recommendations

LedFx uses an optimized animation module for multizone strips and matrix devices, enabling higher frame rates:

| Device Type      | Max FPS  | Notes                                         |
| ---------------- | -------- | --------------------------------------------- |
| Single Bulbs     | 20       | Capped to prevent visible strobing            |
| Multizone Strips | No limit | Push as high as your network or device allows |
| Matrix Devices   | No limit | Push as high as your network or device allows |

The default refresh rate is 30 FPS. Single bulbs are automatically capped at 20 FPS to prevent strobing. For strips and matrix devices, you can increase the rate as high as your WiFi network or LIFX device can handle.

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

| Device Type    | Examples                                                       |
| -------------- | -------------------------------------------------------------- |
| Light          | A19/A21, B22, BR30, E12, E14, E26, E27, GU10, PAR38, Downlight |
| MultiZoneLight | LIFX Z, Lightstrip, Beam, Neon Flex, String                    |
| MatrixLight    | LIFX Tile, Candle, Path, Spot, Luna, Tube                      |
| CeilingLight   | LIFX Ceiling (Round), Ceiling 26" (Capsule)                    |

The detected type, serial number, and device class are saved to configuration for faster subsequent connections.

### Animation Module

LedFx uses the `lifx-async` animation module for high-performance frame delivery to multizone strips and matrix devices. This provides optimized packet handling for smooth animations and higher achievable frame rates.

However, if your WiFi is busy or saturated, performance may degrade. Also note that older LIFX devices have less capable microcontrollers, so their top speed can be limited. You may have to play with FPS values to find a happy medium.

Older controllers are also very picky when it comes to Wi-Fi antenna orientation. If you're experiencing stuttering playback, try rotating the controller box (particularly on older LIFX Z, Beam and String) to better orient it with the closest Wi-Fi access point.

### Color Conversion

LedFx effects output RGB values which are converted to LIFX's HSBK (Hue, Saturation, Brightness, Kelvin) format using NumPy vectors within the LIFX driver for LedFx.

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

## Further Information

- [LIFX Developer Documentation](https://lan.developer.lifx.com/)
- [lifx-async Library](https://github.com/Djelibeybi/lifx-async)
- [LedFx Discord](https://discord.gg/xyyHEquZKQ) - For support and feedback
