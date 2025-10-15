# DDP Device

**DDP** (Distributed Display Protocol) is a modern protocol designed specifically for sending real-time data to distributed LED lighting displays where synchronization and efficiency are important.

Unlike Art-Net and E1.31, which transport the legacy DMX protocol over Ethernet, DDP was designed from the ground up for controlling large-scale LED displays with high efficiency and large packet sizes.

For more information, see the [DDP Protocol Specification](http://www.3waylabs.com/ddp/).

## Why DDP?

DDP is more efficient than DMX-based protocols (E1.31, Art-Net) for controlling LED displays. See the [DDP Protocol Specification](http://www.3waylabs.com/ddp/) for full technical details.

### Protocol Efficiency Comparison

| Protocol | Header Length | Max Data Per Packet | Efficiency | Pixels at 45fps on 100Mbit |
|----------|---------------|---------------------|------------|------------------------------|
| E1.31    | 126 bytes     | 512 bytes           | 72.7%      | 67,340                       |
| Art-Net  | 18 bytes      | 512 bytes           | 85.9%      | 79,542                       |
| **DDP**  | **10 bytes**  | **1440 bytes**      | **94.9%**  | **87,950**                   |

## Device Configuration

### Generic Parameters

Many of the configuration parameters for DDP are common to network-connected devices:

- **Pixel Count** — Number of addressable pixels in device
- **IP Address** — IPv4 address of device
- **icon name** - The icon displayed in the UI, select something that makes sense to you. It is a string entry field, from MDI (Material Design Icons) or MUI (Material UI Icons)

    If using MDI the string should be preceded by mdi:
  -   "mdi: \<icon-name-in-kebab-case\>"
  -   [Material Design Icons](https://pictogrammers.com/library/mdi/)

    If using MUI the string should be just the icon name without a prefix
  -   "\<iconNameInCamelCase\>"
  -   [Material UI Icons](https://mui.com/material-ui/material-icons/)

- **Center Offset** — Simple offset of effect mapping into the device pixel layout
- **Refresh Rate** — Rate at which the effect will be updated and pushed to the device
- **Port** — UDP port for transmitted packets. Default: **4048** (DDP standard port)

### DDP Specific Parameters

#### Destination ID

The **Destination ID** parameter allows you to target specific outputs or regions on a DDP device. This is useful when a single DDP device manages multiple physical displays or display regions.

> **Note:** For most common devices (WLED, Falcon Player), leave `destination_id` at the default value of **1**.

- **Default**: 1 (default output device)
- **Range**: 1-255

**Advanced Use Cases:**
- Send different effects to different LED strips connected to the same DDP controller
- Address specific regions of a large LED display
- Control multiple virtual displays on a single physical device

For example, if your DDP device has two separate LED strips, you could configure one LedFx device with `destination_id: 1` for the first strip and another LedFx device pointing to the same IP with `destination_id: 2` for the second strip.

## Technical Details

### Automatic Multi-Packet Handling

LedFx automatically splits large LED arrays into multiple DDP packets when needed. The DDP protocol supports up to 480 RGB pixels (1440 bytes) per packet, which fits efficiently into standard Ethernet MTU sizes.

If your device has more than 480 pixels, LedFx will:
1. Split the pixel data into multiple packets
2. Set appropriate offsets for each packet
3. Set the PUSH flag on the final packet for synchronized display

This is all handled automatically - you just need to set the total pixel count.

### Protocol Synchronization

DDP uses the PUSH flag to ensure synchronized updates across multiple devices or packets:

- **Single Device**: The PUSH flag is set on the last packet of a frame
- **Multiple Devices**: All devices receive their data, then a broadcast PUSH synchronizes the display update

This ensures that large displays update smoothly without visible tearing or timing issues.

### Data Type

LedFx sends RGB data with 8-bit per channel (data type `0x0B` for RGB888). See the [DDP Protocol Specification](http://www.3waylabs.com/ddp/) for detailed protocol information.

## Device Compatibility

DDP is supported by many LED controllers, including:

- WLED devices (firmware 0.10.0+)
- ESPixelStick
- Custom ESP8266/ESP32 controllers
- Many commercial LED controllers

Check your device documentation to confirm DDP support and any specific configuration requirements.
