# Gradient Extraction Overview

**Feature**: Automatic LED-Optimized Gradient Extraction from Images
**Created**: February 13, 2026
**Last Updated**: February 13, 2026

---

## Introduction

LedFx automatically extracts LED-optimized color gradients from all loaded images (album art, user uploads, cached images). Every image that enters the system receives gradient extraction, producing three variants optimized for different use cases:

- **LED-safe**: Raw colors from source image with no correction (for color accuracy)
- **LED-punchy**: Moderate saturation boost (20%) for vibrant physical LEDs
- **LED-max**: Aggressive saturation boost (65%) + brightness boost (15%) + gamma blend (30%) for maximum vibrancy

Gradients are extracted once during image loading and cached permanently, making them instantly available to effects and the frontend with zero runtime cost.

---

## Problem & Solution

### The Problem

Screen-optimized color extraction produces poor results on physical LED hardware:

1. **Saturation blowout**: Colors appear too intense on RGB LED matrices
2. **Washed-out whites**: Near-white colors render poorly (no dedicated white LEDs)
3. **Background dominance**: Large background areas wash out accent colors in gradients
4. **Incorrect gamma**: Screen gamma (sRGB) differs from LED gamma requirements
5. **Brightness limitations**: LEDs can't safely display full-brightness colors

### The Solution

Automatic extraction pipeline with LED-specific corrections:

- **Saturation boost**: Pull colors towards primaries (20% punchy, 65% max)
- **Brightness boost**: Brighten darker accent colors (max mode only, 15%)
- **Brightness capping**: Max 95% (punchy) or 100% (max)
- **White replacement**: Near-white colors mapped to pure white
- **Background detection**: Any dominant color (>50% frequency) triggers interleaved banding
- **Background protection**: Brightness boost excludes dark background colors (V<0.16)
- **Gamma blend**: Per-variant (0% punchy for accuracy, 30% max for vibrancy)

---

## Architecture

### Integrated Pipeline Design

Gradient extraction is **integrated into the image loading pipeline**, not a separate API. Every image automatically receives gradient extraction during initial load/save, with results cached permanently alongside other metadata (width, height, format).

```
Image Source → Image Loading → PIL Image → Metadata Extraction
    ↓              ↓               ↓              ↓
  URL         open_image      get_image_     extract_gradient_
  Upload      save_asset       metadata           metadata
  Cache          ↓               ↓                   ↓
                 └───────────────┴───────────────────┘
                                 ↓
                    Store in Cache/Asset Metadata
                                 ↓
                    Existing APIs Return Gradients
                                 ↓
                    Frontend/Effects Use Automatically
```

### Integration Points

**1. ImageCache** (`ledfx/libraries/cache.py`)
- Extracts gradients in `put()` method alongside width, height, format
- **Thumbnail optimization**: Skips extraction for thumbnails (identified by `params != None`)
- Stores in built-in `metadata.json` with cache entries
- One-time extraction, cached permanently
- ~20-50ms per original image, 0ms for thumbnails

**2. Asset Storage** (`ledfx/assets.py`)
- Extracts gradients during `list_assets()` directory walk
- **Metadata caching**: Separate `.asset_metadata_cache.json` file
- Cache hit: Instant retrieval (0ms vs 20-300ms extraction)
- Cache invalidation: Automatic on file modification or deletion
- Graceful degradation: Broken cache → re-extract without errors

**3. Existing APIs Enhanced**
- `/api/cache/images` - Returns gradients in cache entry metadata
- `/api/assets` - Returns gradients in asset list
- **No new endpoints** - gradients are optional metadata fields
- Backward compatible - old clients ignore gradient fields

### Architecture Benefits

- **Automatic**: Every image gets gradients without explicit requests
- **One-time cost**: Extract once, use forever (cached)
- **Zero API changes**: Existing endpoints return more metadata
- **Consistent**: All image sources get gradients (URLs, uploads, assets)
- **Performant**: ~20-50ms one-time cost, then instant retrieval
- **Memory efficient**: Gradients are JSON strings (< 1KB per variant)
- **Backward compatible**: Optional metadata fields, old clients unaffected

### Cache Refresh & Re-extraction

For re-extraction (algorithm updates, debugging), use the existing cache refresh:

```
POST /api/cache/images/refresh
{"url": "https://example.com/art.jpg"}
```

**Process**:
1. Cache entry deleted
2. Image re-downloaded and cached
3. Gradients automatically re-extracted
4. Response includes fresh gradients

**Use cases**: Algorithm improvements, parameter tuning, debugging

---

## Color Extraction Pipeline

### Overview

The extraction pipeline processes images through four stages:

1. **Color Quantization**: Extract dominant colors using MEDIANCUT
2. **Background Detection**: Identify any dominant background color (>50%)
3. **Color Deduplication**: Merge perceptually similar colors
4. **Gradient Construction**: Build interleaved or weighted gradient stops

### 1. Color Quantization

**Algorithm**: Pillow's MEDIANCUT quantization

```python
quantized = pil_image.quantize(colors=9, method=Image.Quantize.MEDIANCUT)
palette = quantized.getpalette()[:n_colors * 3]  # RGB triplets
```

**Process**:
- Extract 9-12 dominant colors from image
- Count pixel frequency for each color (frequency weighting)
- Convert to HSV for perceptual operations
- Sort by frequency (most dominant first)

**Two-pass extraction**:
1. **Full-image pass** (12 colors): Robust background detection
2. **Accent pass** (9 colors): With optional accent masking if background detected

### 2. Background Detection

**Threshold**: >50% frequency indicates dominant background

**Detection method**:
- Simply checks if the most frequent color exceeds 50% threshold
- Works for ANY dominant color (white, black, bright colors, etc.)
- Not limited to dark backgrounds - applies to all solid backgrounds
- Triggers interleaved banding pattern to prevent background wash-out

**Examples**:
- **White album art**: 80% white → white detected as background → banding used
- **Black album art**: 70% black → black detected as background → banding used
- **Blue background**: 60% bright blue → blue detected as background → banding used
- **Multi-color**: No single color >50% → weighted gradient (no banding)

### 3. Color Deduplication

**Problem**: Quantization may produce multiple perceptually similar colors (5 shades of blue)

**Solution**: Weighted HSV distance calculation

**For saturated colors** (S ≥ 0.15):
- Hue weight: 0.65 (most important - red vs blue)
- Saturation weight: 0.20
- Value weight: 0.15
- Threshold: 0.12 (tight for distinct colors)

**For grays** (S < 0.15):
- Hue weight: 0.1 (hue meaningless for grays)
- Saturation weight: 0.2
- Value weight: 0.7 (brightness is key)
- Threshold: 0.20 (looser for gray shades)

**Merging**: Similar colors combined, frequencies summed, most frequent kept

**Floor recovery**: If merging collapses below 3 colors, recover using farthest-point sampling from original palette

### 4. Gradient Construction

**Two modes** based on background detection:

**A. Interleaved Pattern** (dominant background >50%):
```
bg → accent1_start → accent1_end → bg → accent2_start → accent2_end → bg
```
- Triggered when ANY color exceeds 50% frequency
- Each accent color gets TWO stops (start and end) creating a flat color region
- Flat regions are 40% of each section width, providing defined color presence
- Background fills the remaining 60% space with smooth blends
- Prevents gradient being overwhelmed by dominant background color
- Stop allocation formula: **3N + 1** (where N = number of accents)
  - 2 accents: `bg, c1_start, c1_end, bg, c2_start, c2_end, bg` (7 stops)
  - 3 accents: `bg, c1_start, c1_end, bg, c2_start, c2_end, bg, c3_start, c3_end, bg` (10 stops)
  - 8 accents (typical max from extraction): 25 stops total (3*8 + 1)
- Each accent is centered in its section with 40% flat width for color prominence
- Uses all accent colors from extraction (up to 9 total colors minus background)

**B. Island Gradient** (no background):
- Weighted color "bands" based on frequency
- Soft blending at boundaries (10% blend fraction)
- Even distribution across [0, 1] position range
- Creates smooth transitions between colors

---

## LED Correction

### The Need for Correction

LED matrices differ from screens:
- **No true white**: RGB-only (no dedicated white LEDs)
- **Gamma mismatch**: LEDs require 2.2 gamma (not sRGB 2.4)
- **Safety limits**: Full brightness can overdraw power or damage LEDs
- **Perceptual differences**: Colors appear more saturated on LEDs

### Correction Parameters

Two correction profiles are defined at the top of `gradient_extraction.py`:

**LED-Punchy** (moderate enhancement):
- 95% brightness cap for power safety
- 20% saturation boost toward primary colors
- No gamma blending (preserves accuracy)
- White detection at S<0.15 threshold

**LED-Max** (extreme vibrancy):
- No brightness cap
- 65% saturation boost toward primary colors
- 15% brightness boost for darker non-background colors
- 30% gamma blending for enhanced vibrancy
- White detection at S<0.15 threshold

See `LED_PUNCHY_CONFIG` and `LED_MAX_CONFIG` in [gradient_extraction.py](../../ledfx/utilities/gradient_extraction.py) for exact parameter values. LED-safe uses raw colors with no configuration.

### Correction Pipeline

The `apply_led_correction()` function processes each color through these steps:

1. **White detection**: Returns pure white for near-white colors (low saturation, high value)
2. **Brightness cap**: Limits maximum brightness (config-dependent)
3. **Brightness boost**: Enhances darker accent colors (max mode only, excludes backgrounds)
4. **Saturation boost**: Pushes colors toward primaries using `s + (1 - s) * boost` formula
5. **Saturation cap**: Ensures saturation stays within limits
6. **Gamma correction**: Blends linear and gamma-corrected values for LED characteristics
7. **RGB conversion and clamping**: Converts HSV back to RGB and clamps to 0-255 range

See `apply_led_correction()` in [gradient_extraction.py](../../ledfx/utilities/gradient_extraction.py) for implementation details.

### Tuning Constants

All correction parameters and thresholds are defined as module-level constants for easy tuning:

- **Color similarity weights**: Separate weights for gray vs saturated color comparisons (hue, saturation, value)
- **Deduplication thresholds**: Distance thresholds for color deduplication (different for grays vs saturated)
- **Background detection**: Frequency threshold (50%) for detecting dominant backgrounds
- **Accent masking**: HSV thresholds for filtering dark pixels in accent pass (legacy, dark backgrounds only)

See constant definitions at top of [gradient_extraction.py](../../ledfx/utilities/gradient_extraction.py).

#### Example Constants

```
BG_LOW_S_V = 0.28
BLEND_FRAC = 0.10  # Island gradient blend fraction
GAMMA_BLEND = 0.00  # Disabled for accuracy
```

---

## Metadata Format

Gradients are stored in image metadata and exposed through API responses:

```javascript
{
  "url": "https://example.com/art.jpg",
  "width": 1200,
  "height": 800,
  "format": "JPEG",
  "n_frames": 1,
  "is_animated": false,
  "gradients": {
    "led_safe": {
      "gradient": "linear-gradient(90deg, rgb(255,0,0) 0%, rgb(0,255,0) 50%, rgb(0,0,255) 100%)"
    },
    "led_punchy": {
      "gradient": "linear-gradient(90deg, rgb(255,0,0) 0%, ...)"
    },
    "led_max": {
      "gradient": "linear-gradient(90deg, rgb(255,0,0) 0%, ...)"
    },
    "metadata": {
      "image_size": [1200, 800],
      "processing_time_ms": 45,
      "extracted_color_count": 8,
      "has_dominant_background": true,
      "gradient_stop_count": 7,
      "pattern": "interleaved",
      "background_color": "#000000",
      "background_frequency": 0.65,
      "extraction_version": "1.1",
      "extracted_at": "2026-02-13T12:00:00Z"
    }
  }
}
```

### Metadata Fields

**Per-variant fields** (`led_safe`, `led_punchy`, `led_max`):
- `gradient`: CSS linear-gradient string for use in effects

**Extraction metadata** (`metadata` section):
- `background_color`: Hex color of most frequent color (always populated)
- `background_frequency`: Frequency of most frequent color (0.0-1.0)
- `has_dominant_background`: `true` if >50% threshold met, triggers interleaved pattern
- `pattern`: `"interleaved"` (background-separated) or `"weighted"` (distributed)
- `extracted_color_count`: Number of distinct colors after deduplication
- `gradient_stop_count`: Number of stops in gradient
- `processing_time_ms`: Extraction duration
- `extraction_version`: Algorithm version for tracking changes

---

## API Integration

### Accessing Gradients

Gradients are automatically included in existing API responses:

**From Image Cache**:
```text
GET /api/cache/images
```

Response:
```
{
  "entries": [
    {
      "url": "https://example.com/art.jpg",
      "width": 1200,
      "height": 800,
      "gradients": {
        "led_safe": {"gradient": "linear-gradient(...)"},
        "led_punchy": {"gradient": "linear-gradient(...)"},
        "led_max": {"gradient": "linear-gradient(...)"},
        "metadata": {...}
      }
    }
  ]
}
```

**From Assets**:
```text
GET /api/assets
```

Response:
```
{
  "assets": [
    {
      "path": "album_art.png",
      "size": 102400,
      "gradients": {
        "led_safe": {"gradient": "linear-gradient(...)"},
        "led_punchy": {"gradient": "linear-gradient(...)"},
        "led_max": {"gradient": "linear-gradient(...)"},
        "metadata": {...}
      }
    }
  ]
}
```

### Using in Effects

Effects can access gradients through the `gradient` config parameter:

```python
class MyEffect(GradientEffect):
    CONFIG_SCHEMA = vol.Schema({
        vol.Optional("gradient", default="Rainbow"): validate_gradient,
    })

    def config_updated(self, config):
        # Gradient string can come from:
        # 1. Predefined gradients ("Rainbow", "Sunset", etc.)
        # 2. Custom gradient strings
        # 3. Image-extracted gradients (led_safe/led_punchy/led_max)
        super().config_updated(config)
```

**Frontend sets gradient from image**:
```javascript
// User selects image, frontend reads gradient from metadata
const imageMeta = await fetch('/api/assets').then(r => r.json());
const gradient = imageMeta.assets[0].gradients.led_safe.gradient;

// Apply to effect
await fetch(`/api/virtuals/${virtualId}/effects/${effectId}`, {
  method: 'PUT',
  body: JSON.stringify({ config: { gradient } })
});
```

---

## Developer Guide

### Core Module Location

**File**: `ledfx/utilities/gradient_extraction.py` (~1000 lines)

**Key functions**:
- `extract_gradient_metadata()`: Main entry point, returns all variants and metadata
- `extract_dominant_colors()`: Color extraction using MEDIANCUT quantization
- `detect_dominant_background()`: Detects any dominant color exceeding 50% frequency
- `apply_led_correction()`: LED-specific color correction with configurable parameters
- `build_gradient_stops()`: Gradient stop construction from colors
- `build_gradient_string()`: LedFx gradient string formatting

See function signatures and docstrings in [gradient_extraction.py](../../ledfx/utilities/gradient_extraction.py).

### Testing

**Test Coverage**: 33/33 passing (100%)

**Unit Tests** (`tests/test_gradient_extraction.py`):
- 25 tests covering core algorithms
- Color extraction, background detection, LED correction
- Gradient construction, stability, metadata wrapper

**Integration Tests** (`tests/test_gradient_integration.py`):
- 8 tests covering cache and asset integration
- Thumbnail optimization, error handling
- Multiple images, variant validation

### Performance

**Extraction Time**: ~20-50ms per image (one-time cost)

**Caching Strategy**:
- **ImageCache**: Built-in `metadata.json` stores gradients with cache entries
- **Assets**: Separate `.asset_metadata_cache.json` for directory caching
- **Thumbnails**: Skip extraction (0ms), only extract for original image

**Cache Performance**:
- First extraction: 20-50ms
- Subsequent retrievals: 0ms (instant)
- 16 thumbnails: 1 extraction (original), 15 skipped

### Error Handling

Extraction failures handled gracefully:

```python
try:
    gradients = extract_gradient_metadata(image)
except Exception as e:
    _LOGGER.warning(f"Failed to extract gradients: {e}")
    gradients = None  # Image still loads, just no gradients
```

**Failure scenarios**:
- Invalid image formats → logged warning, `gradients: null`
- Corrupted images → logged warning, continues
- Extraction crashes → caught, logged, continues
- **Image loading NEVER fails** due to gradient extraction

### Extending the System

**Adding new correction modes**:
1. Define config dict in `gradient_extraction.py`:
   ```python
   LED_CUSTOM_CONFIG = {
       "max_value": 0.90,
       "max_saturation": 0.85,
       "gamma": 2.2,
       "white_threshold": 0.15,
       "white_replacement": "#F8F8F8",
   }
   ```

2. Add mode to `apply_led_correction()`:
   ```python
   if mode == "custom":
       config = LED_CUSTOM_CONFIG
   ```

3. Add variant to `extract_gradient_metadata()`:
   ```python
   custom_colors = [
       {"rgb": apply_led_correction(c["rgb"], mode="custom"), ...}
       for c in colors
   ]
   custom_stops = build_gradient_stops(custom_colors, custom_background)
   custom_gradient = build_gradient_string(custom_stops)

   return {
       # ... existing variants ...
       "led_custom": {"gradient": custom_gradient}
   }
   ```

**Tuning parameters**:
- All constants defined at module top for easy adjustment
- Modify thresholds, weights, or blend fractions as needed
- Run tests after changes: `uv run pytest tests/test_gradient_extraction.py`

---

## Runtime Generated Files

```
{config_dir}/cache/images/metadata.json          # ImageCache metadata
{config_dir}/assets/.asset_metadata_cache.json   # Asset metadata cache
```


