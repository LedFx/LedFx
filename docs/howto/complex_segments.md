# How To: Complex Segments

## Overview

Complex Segments is an advanced performance optimization mode for virtuals that significantly improves pixel mapping speed when using a high number of segments with span mapping. When enabled, it precompiles segment-to-device mapping data structures and uses efficient numpy scatter operations to achieve up to 13x faster frame rendering compared to the standard segment processing approach with thousands of segments configured.

## What is Complex Segments?

Complex Segments mode changes how LedFx maps virtual pixels to physical device pixels. Instead of processing each segment individually during every frame render, it:

1. **Precompiles mapping data** - At configuration time, it builds numpy index arrays that define exactly where each virtual pixel should go on each device
2. **Groups by device** - It consolidates all segments targeting the same device into a single operation
3. **Uses scatter indexing** - It leverages numpy's advanced indexing (fancy indexing) to update multiple non-contiguous pixel ranges in a single operation

This approach trades a small amount of memory for significant CPU time savings during frame rendering, which is critical for maintaining high frame rates.

## When to Use Complex Segments

### Ideal Use Cases

Complex Segments mode is beneficial when:

- **Multiple segments per device** - You have several segments from the same virtual mapping to different parts of a single device.
- **Many segments** - Your virtual has numerous segments (e.g., 10+ segments across multiple devices)
- **Complex layouts** - You have intricate LED installations with reversed segments, gaps, or non-contiguous mappings
- **Span mapping** - You're using span mode to spread an effect across multiple segments

Complex segments has been developed against and tested against virtuals with several thousand segments, to support some of the more extreme physical setups out in the community.

### When NOT to Use Complex Segments

Complex Segments may not provide benefits or could be inappropriate when:

- **Simple configurations** - Simple virtuals with a few dozen segments. Simple virtuals will run slightly slower if set as complex_segments.

## Requirements and Limitations

## How It Works

### Compilation Phase

When Complex Segments mode is enabled, LedFx performs a one-time compilation:

1. **Builds device buffers** - Groups segments by target device_id
2. **Creates index arrays** - For each device, builds two numpy arrays:
   - `src`: Virtual pixel indices to read from the effect output
   - `dst`: Device pixel indices to write to on the physical device
3. **Handles reversals** - Segments marked as reversed have their source indices flipped
4. **Filters invalid devices** - Removes references to non-existent devices

The compiled data structure looks like:

```python
_device_remap = {
    "device_1": {
        "src": np.array([0, 1, 2, ..., 50]),  # Virtual pixels
        "dst": np.array([10, 11, 12, ..., 60])  # Device pixels
    },
    "device_2": {
        "src": np.array([51, 52, 53, ..., 100]),
        "dst": np.array([0, 1, 2, ..., 49])
    }
}
```

### Render Phase

During each frame render, the optimized flush path:

1. **Extracts pixels** - Uses `pixels[src_indices]` to gather the relevant pixels in one operation
2. **Applies oneshots** - Processes any oneshot effects on the extracted segment
3. **Sends scatter data** - Transmits pixels with target indices to the device using scatter mode: `(pixels, dst_indices)`
4. **Device updates** - The device uses fancy indexing to scatter pixels to the correct locations: `self._pixels[dst_indices] = pixels`

This eliminates the overhead of iterating through segments and performing individual range assignments.