# Gradient Extraction Overview

**Feature**: Automatic LED-Optimized Gradient Extraction from Images
**Created**: February 13, 2026
**Last Updated**: February 13, 2026

---

## Introduction

LedFx automatically extracts LED-optimized color gradients from all loaded images (album art, user uploads, cached images). Every image that enters the system receives gradient extraction, producing three variants optimized for different use cases:

- **Raw**: True to source image colors, ideal for screen previews
- **LED-safe**: Optimized for physical LED hardware (WS2812/HUB75 matrices)
- **LED-punchy**: Enhanced saturation variant for vibrant displays

Gradients are extracted once during image loading and cached permanently, making them instantly available to effects and the frontend with zero runtime cost.

---

## Problem & Solution

### The Problem

Screen-optimized color extraction produces poor results on physical LED hardware:

1. **Saturation blowout**: Colors appear too intense on RGB LED matrices
2. **Washed-out whites**: Near-white colors render poorly (no dedicated white LEDs)
3. **Background dominance**: Large background areas wash out accent colors in gradients
4. **Incorrect gamma**: Screen gamma (sRGB) differs from LED gamma requirements
5. **Brightness limitations**: LEDs can't safely display full brightness colors

### The Solution

Automatic extraction pipeline with LED-specific corrections:

- **Brightness capping**: Max 85% brightness for safe operation
- **Saturation reduction**: 90% max saturation prevents oversaturation
- **White replacement**: Near-white colors mapped to defined white points
- **Background detection**: Dominant backgrounds (>50%) separated from accent colors
- **Interleaved gradients**: Background-separated accent "islands" for vibrant displays
- **LED gamma correction**: 2.2 gamma appropriate for LED physics

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
2. **Background Detection**: Identify dominant background clusters (>50%)
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

**Background cluster detection**:
- Treats "background" as a cluster of background-like colors
- Dark colors (V < 0.16) OR low-saturation dark (S < 0.18, V < 0.28)
- Sums frequencies of all background-ish colors
- Returns most frequent color if cluster exceeds threshold

**Example**: Album art with 70% black background
- Black pixels + dark grays counted together
- Total frequency: 70% → background detected
- Gradient uses remaining 30% accent colors

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

**A. Interleaved Pattern** (background detected):
```
bg → accent1 → bg → accent2 → bg → accent3 → bg
```
- Alternates background with accent colors
- Creates distinct "islands" of vibrant color
- Prevents background wash-out
- Stop allocation (8 max stops):
  - 4 accents: `bg, c1, bg, c2, bg, c3, bg, c4` (8 stops)
  - 3 accents: `bg, c1, bg, c2, bg, c3, bg` (7 stops)

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

**LED-Safe Config** (conservative):
```python
LED_SAFE_CONFIG = {
    "max_value": 0.85,          # Cap brightness at 85%
    "max_saturation": 0.90,     # Reduce saturation to 90%
    "gamma": 2.2,               # LED-appropriate gamma
    "white_threshold": 0.15,    # Detect near-white (S < 15%)
    "white_replacement": "#F5F5F5",  # WhiteSmoke for whites
}
```

**LED-Punchy Config** (vibrant):
```python
LED_PUNCHY_CONFIG = {
    "max_value": 0.95,          # Higher brightness
    "max_saturation": 1.0,      # Full saturation
    "gamma": 2.2,
    "white_threshold": 0.15,
    "white_replacement": "#FFFFFF",  # Pure white
}
```

### Correction Pipeline

For each color in extracted palette:

1. **White detection** (S < 0.15 AND V > 0.95):
   ```python
   if saturation < 0.15 and value > 0.95:
       return white_replacement  # Replace with defined white
   ```

2. **Brightness cap**:
   ```python
   value = min(value, max_value)  # Cap at 85% (safe) or 95% (punchy)
   ```

3. **Saturation cap**:
   ```python
   saturation = min(saturation, max_saturation)  # 90% (safe) or 100% (punchy)
   ```

4. **Gamma correction** (currently disabled):
   ```python
   # Apply gamma to each RGB channel, blend with original
   gamma_corrected = pow(color, 1.0 / gamma)
   final = color * (1 - blend) + gamma_corrected * blend
   # blend = 0.00 (disabled for accuracy)
   ```

5. **Clamp to valid range**:
   ```python
   rgb = [int(max(0, min(255, c * 255))) for c in rgb_float]
   ```

### Tuning Constants

All correction parameters defined at module top (`gradient_extraction.py`) for easy tuning:

```python
# Color similarity weights
GRAY_HUE_WEIGHT = 0.1
GRAY_SAT_WEIGHT = 0.2
GRAY_VAL_WEIGHT = 0.7
SATURATED_HUE_WEIGHT = 0.65
SATURATED_SAT_WEIGHT = 0.20
SATURATED_VAL_WEIGHT = 0.15

# Deduplication thresholds
COLOR_DISTANCE_THRESHOLD = 0.20  # For grays
SATURATED_COLOR_THRESHOLD = 0.12  # For saturated colors

# Background detection
BACKGROUND_CLUSTER_THRESHOLD = 0.50
BG_DARK_V = 0.16
BG_LOW_S = 0.18
BG_LOW_S_V = 0.28

# Gradient building
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
    "raw": {
      "gradient": "linear-gradient(90deg, rgb(255,0,0) 0%, rgb(0,255,0) 50%, rgb(0,0,255) 100%)"
    },
    "led_safe": {
      "gradient": "linear-gradient(90deg, rgb(217,0,0) 0%, ...)"
    },
    "led_punchy": {
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

**Per-variant fields** (`raw`, `led_safe`, `led_punchy`):
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
        "raw": {"gradient": "linear-gradient(...)"},
        "led_safe": {"gradient": "linear-gradient(...)"},
        "led_punchy": {"gradient": "linear-gradient(...)"},
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
        "raw": {"gradient": "linear-gradient(...)"},
        "led_safe": {"gradient": "linear-gradient(...)"},
        "led_punchy": {"gradient": "linear-gradient(...)"},
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
        # 3. Image-extracted gradients (raw/led_safe/led_punchy)
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

**File**: `ledfx/utilities/gradient_extraction.py` (974 lines)

**Main entry point**:
```python
def extract_gradient_metadata(image_source) -> dict:
    """
    Extract all gradient variants and metadata from an image.

    Args:
        image_source: Either a file path (str) or PIL Image object

    Returns:
        dict: Complete gradient metadata with all variants
    """
```

### Key Functions

**Color Extraction**:
```python
def extract_dominant_colors(
    pil_image: Image.Image,
    n_colors: int = 9,
    use_accent_mask: bool = False
) -> list[dict]:
    """Extract dominant colors using MEDIANCUT quantization."""
```

**Background Detection**:
```python
def detect_dominant_background(
    colors: list[dict],
    threshold: float = 0.5
) -> Optional[dict]:
    """Detect if image has dominant background cluster."""
```

**LED Correction**:
```python
def apply_led_correction(
    rgb: list[int],
    mode: str = "safe"
) -> list[int]:
    """Apply LED-specific color correction to RGB values."""
```

**Gradient Construction**:
```python
def build_gradient_stops(
    colors: list[dict],
    background_color: Optional[dict] = None,
    max_stops: int = 8
) -> list[dict]:
    """Build gradient stops from extracted colors."""

def build_gradient_string(stops: list[dict]) -> str:
    """Build LedFx gradient string from stops."""
```

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


