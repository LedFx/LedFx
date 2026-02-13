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

```{mermaid}
graph TD
    A[Image Source] --> B{Image Loading}
    B --> C[open_image / save_asset]
    C --> D[PIL Image]
    D --> E[Existing Metadata Extraction]
    E --> F[get_image_metadata]
    F --> G[NEW: extract_gradient_metadata]
    G --> H[Store in Cache/Asset Metadata]
    H --> I[Existing APIs Return Gradients]
    I --> J[Frontend/Effects Use Automatically]

    K[URL] --> B
    L[Upload] --> B
    M[Asset Manager] --> B
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

#### Objectives
- Map existing image handling infrastructure
- Identify gradient utilities and data structures
- Document color correction patterns
- Assess security and validation flows

#### Tasks
1. **Image Loading Analysis**
   - [x] Search for PIL Image usage patterns
   - [x] Identify URL validation logic (`assets.py` likely)
   - [x] Find image cache mechanisms
   - [x] Document size/type restrictions
   - [x] Map security checks (path traversal, SSRF)

2. **Gradient System Analysis**
   - [x] Find gradient data structures
   - [x] Locate color utilities (`color.py`)
   - [x] Identify existing correction functions
   - [x] Document gradient serialization format

3. **REST Pattern Analysis**
   - [x] Review cache API patterns (`api/cache_images.py`)
   - [x] Study asset API security (`api/asset*.py`)
   - [x] Identify response helper usage
   - [x] Map error handling patterns

#### Findings Summary

##### Image Loading Infrastructure

**Core Functions** (`ledfx/utils.py`):
- `open_image(image_path, force_refresh=False, config_dir=None)` - Main entry point
- `open_gif(gif_path, force_refresh=False, config_dir=None)` - GIF-specific handler
- `_validate_and_open_image(resolved_path, original_path, check_size=True)` - Validation helper

**Image Sources Supported**:
1. **Remote URLs**: `http://`, `https://` with automatic caching
2. **Built-in assets**: `builtin://path` from `LEDFX_ASSETS_PATH/test_images/`
3. **User assets**: Plain paths like `"my_image.png"` from `config_dir/assets/`
4. **Cached images**: Retrieved via `ImageCache.get(url)`

**Security Layer** (`ledfx/utilities/security_utils.py`):
- `validate_url_safety(url)` - SSRF protection (blocks private IPs, loopback, metadata endpoints)
- `validate_pil_image(image)` - PIL format and dimension validation
- `is_allowed_image_extension(path)` - Extension whitelist
- `resolve_safe_path_in_directory(root, path)` - Path traversal protection
- Constants: `MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024`, `MAX_IMAGE_PIXELS = 4096 * 4096`

**Image Cache** (`ledfx/libraries/cache.py`):
- Class: `ImageCache(config_dir, max_size_mb=500, max_items=500)`
- Methods: `get(url, params)`, `put(url, data, content_type, etag, last_modified, params)`
- Cache key: SHA-256 hash of `url|params` for thumbnail variants
- Metadata stored: width, height, format, n_frames, is_animated (via `get_image_metadata()`)
- Location: `config_dir/cache/images/`
- No automatic expiration, LRU eviction only

**Asset Storage** (`ledfx/assets.py`):
- Functions: `save_asset()`, `delete_asset()`, `list_assets()`, `get_asset_or_builtin_path()`
- Triple validation: extension → MIME type → PIL format
- Atomic writes via temp files
- Built-in assets: `LEDFX_ASSETS_PATH` (ledfx_assets package)

##### Gradient System

**Gradient Class** (`ledfx/color.py`):
```python
class Gradient:
    __slots__ = "colors", "mode", "angle"
    # colors: List[(RGB, position)] where position ∈ [0.0, 1.0]
    # mode: "linear" or "radial"
    # angle: int (degrees)

    @classmethod
    def from_string(cls, gradient_str: str) -> Gradient

    def sample(self, position: float) -> str  # Returns hex color "#RRGGBB"
```

**Gradient String Format**:
```
"linear-gradient(90deg, rgb(255, 0, 0) 0%, rgb(0, 255, 0) 50%, rgb(0, 0, 255) 100%)"
```

**Color Utilities** (`ledfx/color.py`):
- `parse_color(color)` → `RGB` namedtuple
- `parse_gradient(gradient_str)` → `Gradient` or `RGB`
- `validate_color(color)` → normalized hex string
- `validate_gradient(gradient)` → validated string
- `get_color_at_position(gradient_like, position)` → hex color
- `hsv_to_rgb(hue, saturation, value)` → RGB array (NumPy)
- `rgb_to_hsv_vect(rgb)` → HSV array (vectorized)

**Predefined Gradients** (`LEDFX_GRADIENTS` dict):
- "Rainbow", "Dancefloor", "Plasma", "Ocean", "Viridis", "Jungle", "Spring", "Winter", "Frost", "Sunset", "Borealis", "Rust", "Winamp"

**GradientEffect Base Class** (`ledfx/effects/gradient.py`):
```python
@Effect.no_registration
class GradientEffect(Effect):
    CONFIG_SCHEMA = vol.Schema({
        vol.Optional("gradient", default="linear-gradient(...)"): validate_gradient,
        vol.Optional("gradient_roll", default=0): vol.Range(min=0, max=10),
    })

    # Internal gradient storage as NumPy array (3, gradient_length)
    _gradient_curve = None  # shape: (3, gradient_pixel_count)

    # Key methods:
    def _generate_gradient_curve(self, gradient, gradient_length)
    def _get_gradient_colors(self, points)  # points ∈ [0, 1]
    def apply_gradient(self, y)  # Apply gradient to intensity array
```

**Gradient Rendering Pipeline**:
1. Parse gradient string → `Gradient` object
2. Generate curve with easing (Bezier-style interpolation via `_ease()`)
3. Store as NumPy array: `(3, gradient_length)` where 3 = RGB channels
4. Sample via normalized positions [0.0, 1.0]
5. Advanced indexing for vectorized color lookup

#### Deliverables
- ✅ Component inventory document (above)
- ✅ Integration points identified (ImageCache.put, save_asset)
- ✅ Security mechanisms understood (reuse existing validation)

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

### Correction Constants (Module-Level)

All tuning parameters defined at module top for easy adjustment:

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

### Phase 3: Pipeline Integration
**Status**: ✅ COMPLETE
**Duration**: 2-3 hours (Completed: February 13, 2026)

#### Objectives
- Integrate gradient extraction into ImageCache
- Integrate gradient extraction into asset storage
- Update existing API responses to include gradients
- **No new REST endpoints needed** ✅

#### Tasks

1. **Integrate with ImageCache** (`ledfx/libraries/cache.py`)
   ```python
   # In ImageCache.put() method, after get_image_metadata():

   # Extract image metadata (existing)
   width, height, img_format, n_frames, is_animated = get_image_metadata(cache_path)

   # NEW: Extract gradient metadata only for original images, not thumbnails
   # Thumbnails have params, original images don't
   gradient_data = None
   if params is None:  # Skip thumbnails
       try:
           gradient_data = extract_gradient_metadata(cache_path)
       except Exception as e:
           _LOGGER.warning(f"Failed to extract gradients for {url}: {e}")
           # Continue without gradients - not a critical failure

   entry = {
       # ... existing fields ...
       "width": width,
       "height": height,
       "format": img_format,
       "n_frames": n_frames,
       "is_animated": is_animated,
       "gradients": gradient_data,  # NEW FIELD (None for thumbnails)
   }
   ```

2. **Integrate with Asset Storage** (`ledfx/assets.py`)
   - [x] Add gradient extraction in `save_asset()` after validation
   - [x] Store gradient metadata alongside image
   - [x] Update `list_assets()` to include gradient metadata in responses
   - [x] **Implement gradient caching** - Store extracted gradients with modification times
   - [x] Skip re-extraction for unchanged files (check cached modified_time)
   - [x] Cache invalidation on file deletion
   - [x] Graceful cache loading (empty or corrupted → return empty dict)
   - [x] Handle extraction errors gracefully (log warning, cache failure, continue)
   - [x] **Cache file**: `.asset_metadata_cache.json` (generic for future extensibility)

3. **Update Existing API Responses** (minimal changes)
   - [x] `/api/cache/images` GET - Already returns cache entries, now includes gradients in `get_stats()` response
   - [x] `/api/assets` GET - Already returns asset list, now includes gradients
   - [x] No schema changes needed - gradients are optional metadata fields
   - [x] Existing clients ignore new fields (backward compatible)

4. **Error Handling**
   - [x] Wrap extraction in try/except to prevent breaking image loading
   - [x] Log warnings for extraction failures
   - [x] Set `gradients: null` if extraction fails
   - [x] Image loading continues normally even if gradient extraction fails

5. **Performance Considerations**
   - [x] Gradient extraction adds ~20-50ms per image (acceptable for one-time cost)
   - [x] **Thumbnail optimization**: Skip gradient extraction for thumbnails (identified by `params != None`)
   - [x] Single image with multiple thumbnails: Only extracts gradients once (on original), not per thumbnail
   - [x] Performance impact: One 300ms extraction per image vs. 16× extractions (thumbnails skip extraction)
   - [x] **Asset gradient caching**: Prevents re-extraction on every `list_assets()` call
   - [x] Cache file: `.asset_metadata_cache.json` (hidden file in assets directory, generic for future metadata)
   - [x] Cache hit: Instant gradient retrieval (0ms vs. 20-300ms extraction)
   - [x] Cache miss: Extract once, cache result with modification time
   - [x] Automatic cache invalidation: When file modified or deleted
   - [x] Graceful degradation: Broken cache → re-extract without errors
   - [x] Performance improvement: 16 files = 16 extractions on first list, 0 extractions on subsequent lists
   - [x] Consider making extraction optional via config flag (future enhancement)
   - [x] Cache metadata file size increases ~1-2KB per image (negligible)

#### Acceptance Criteria
- ✅ ImageCache automatically extracts gradients on `put()`
- ✅ Asset uploads automatically extract gradients
- ✅ Existing APIs return gradient metadata without code changes
- ✅ Extraction failures don't break image loading
- ✅ Backward compatible - old clients ignore new fields

#### Integration Testing
- [x] Upload image via `/api/assets` → Check response includes gradients
- [x] Load URL image (cache miss) → Check cache entry includes gradients
- [x] Load cached image → Check `/api/cache/images` returns gradients
- [x] Simulate extraction error → Verify image still loads, `gradients: null`
- [x] Test with various image types (JPEG, PNG, GIF, WebP)
- [x] Thumbnail optimization → Verify thumbnails skip gradient extraction

**Test Results**: 8/8 integration tests passing (test_gradient_integration.py)

---

### Phase 4: Testing & Validation
**Status**: Partially Complete
**Duration**: 2-3 hours

#### Objectives
- Comprehensive test coverage ✅
- Validate LED correction quality (pending visual validation)
- Security testing (pending)

#### Tasks

1. **Unit Tests** (`tests/test_gradient_extraction.py`) ✅ COMPLETE
   - [x] Test palette extraction (5 tests)
   - [x] Test dominant background detection (4 tests)
   - [x] Test LED correction algorithms (6 tests)
   - [x] Test gradient construction (5 tests)
   - [x] Test stability/determinism (2 tests)
   - [x] Test metadata wrapper (2 tests)

2. **Integration Tests** (`tests/test_gradient_integration.py`) ✅ COMPLETE
   - [x] Test ImageCache integration (4 tests)
   - [x] Test Asset integration (4 tests)
   - [x] Test thumbnail optimization
   - [x] Test error handling
   - [x] Test variant validation
   - [x] Test multiple images

3. **Security Tests** (Pending)
   - [ ] Path traversal attempts
   - [ ] SSRF protection validation
   - [ ] Use big-list-of-naughty-strings patterns
   - [ ] Test size limit enforcement
   - [ ] Test MIME type validation

4. **Visual Validation** (Pending)
   - [ ] Create test image set (various color profiles)
   - [ ] Generate gradients for each variant
   - [ ] Document expected vs actual results
   - [ ] Test on physical LED hardware if available

#### Test Image Categories
- High saturation colors
- Pastel/low saturation
- Near-white dominant
- High contrast
- Similar images (stability test)

---

### Phase 5: Integration & Documentation
**Status**: Not Started
**Duration**: 2-3 hours

#### Objectives
- Document automatic gradient extraction
- Provide integration examples
- **Optional**: Create on-demand refresh endpoint

#### Tasks

1. **Update Existing API Documentation**
   - [ ] Update `docs/apis/cache.md` - Document gradient fields in cache entries
   - [ ] Update `docs/apis/assets.md` - Document gradient fields in asset metadata
   - [ ] Add gradient format specification
   - [ ] Include usage examples

2. **Developer Documentation**
   - [ ] Update this strategy doc with outcomes
   - [ ] Document `extract_gradient_metadata()` API
   - [ ] Add algorithm explanations
   - [ ] Provide integration guide for effects

3. **Frontend Integration Guide**
   - [ ] Show how to access gradients from asset/cache responses
   - [ ] Provide examples of using gradients in visualizations
   - [ ] Document gradient string format parsing

4. **Optional: Refresh Endpoint** (`ledfx/api/gradients_refresh.py`)
   ```python
   class GradientsRefreshEndpoint(RestEndpoint):
       ENDPOINT_PATH = "/api/gradients/refresh"

       async def post(self, request):
           # Accept: cache_key or url
           # Delete cached gradient metadata
           # Re-extract with current algorithm
           # Return: new gradients
   ```
   - [ ] Only if on-demand re-extraction is needed
   - [ ] Use case: Algorithm improvements, parameter tuning

5. **Configuration (if needed)**
   - [ ] Optional: Add config flag to disable automatic extraction
   - [ ] Document any new config options
   - [ ] Provide sensible defaults

---

## Technical Specifications

### Core Data Structures

```python
@dataclass
class ColorWeight:
    """Dominant color with frequency weight (internal use)"""
    rgb: Tuple[int, int, int]
    hsv: Tuple[float, float, float]
    frequency: float  # 0.0-1.0

@dataclass
class GradientStop:
    """Single stop in gradient (internal use)"""
    position: float  # 0.0-1.0
    color: str  # hex format "#RRGGBB"

# Note: These structures are used internally for gradient construction
# API responses only expose: gradient (CSS string), background_color, background_frequency
```

### LED Correction Parameters

```python
LED_SAFE_CONFIG = {
    "max_value": 0.85,        # Cap brightness at 85%
    "max_saturation": 0.90,   # Reduce saturation to 90%
    "gamma": 2.2,             # LED-appropriate gamma
    "white_threshold": 0.15,  # Detect near-white (low saturation)
    "white_replacement": {
        "warm": "#FFE4B5",    # Moccasin
        "cool": "#F0F8FF",    # AliceBlue
    }
}

LED_PUNCHY_CONFIG = {
    **LED_SAFE_CONFIG,
    "max_saturation": 0.95,   # Higher saturation
    "boost_midtones": 1.1,    # Slight brightness boost
}
```

### Metadata Format (Stored in Cache/Assets)

Gradients are integrated into image metadata and stored in cache entries and asset metadata:

```javascript
{
  "url": "https://example.com/art.jpg",
  "cached_at": "2026-02-13T12:00:00Z",
  "file_size": 102400,
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
      "extraction_version": "1.0",
      "extracted_at": "2026-02-13T12:00:00Z"
    }
  }
}
```

**API Response Fields**:
- `gradient` (per variant): CSS linear-gradient string (used by effects)
- `background_color` (in metadata): Hex color of the most frequent color (always populated)
- `background_frequency` (in metadata): Frequency of the most frequent color (0.0-1.0)
- `has_dominant_background` (in metadata): `true` if most frequent color is >50%, `false` otherwise

**Internal Implementation**:
- Internally uses stops array and dominant_colors for gradient construction
- These are NOT exposed in API responses - only gradient CSS string and background info
- When `has_dominant_background` is `true`, uses interleaved gradient pattern (bg separates accents)
- When `has_dominant_background` is `false`, uses weighted gradient pattern (all colors distributed)
- Background color/frequency are extraction metadata, not gradient-variant-specific

### Asset Metadata Cache Format

The asset metadata cache (`.asset_metadata_cache.json`) stores extracted image metadata with modification times to prevent redundant extraction on every `list_assets()` call. Currently stores gradients, but designed to accommodate other metadata in the future:

```json
{
  "path/to/image1.png": {
    "gradients": {
      "raw": { /* Full gradient structure as above */ },
      "led_safe": { /* LED-corrected variant */ },
      "led_punchy": { /* Punchy variant */ },
      "metadata": { /* Extraction metadata */ }
    },
    "modified_time": "2026-02-13T12:00:00.123456+00:00"
  },
  "subfolder/image2.jpg": {
    "gradients": null,  // Cached extraction failure
    "modified_time": "2026-02-13T12:05:00.789012+00:00"
  }
}
```

**Cache Behavior**:
- **Cache Hit**: File's `modified_time` matches cache entry → Use cached gradients (0ms)
- **Cache Miss**: File is new or modified → Extract gradients, update cache entry
- **Extraction Failure**: Store `gradients: null` to avoid re-attempting every list
- **File Deletion**: Cache entry removed via `delete_asset()` invalidation
- **Corrupted Cache**: Returns empty dict, all files re-extracted
- **Cache Location**: `{config_dir}/assets/.asset_metadata_cache.json` (hidden file)
- **Cache File Size**: ~1-2KB per image (negligible overhead)
- **Future-ready**: Generic structure allows adding other metadata beyond gradients

**Performance Impact**:
- First `list_assets()` call: Extract gradients for all images (one-time cost)
- Subsequent calls: Instant retrieval from cache
- Example: 16 images × 50ms = 800ms first call, 0ms subsequent calls

tests/
  test_gradient_extraction.py         # Core function tests
  test_gradient_integration.py        # Integration tests (cache/assets)

docs/apis/
  (updates to existing cache.md and assets.md)
```

### Modified Files

```
ledfx/libraries/cache.py    # Add gradient extraction in put() method
                             # Update get_stats() to expose gradients in API response
ledfx/assets.py              # Add gradient extraction + caching in list_assets()
                             # Add cache invalidation in delete_asset()
                             # Add _load_asset_metadata_cache() and _save_asset_metadata_cache()
                             # Update IGNORED_FILES to exclude .asset_metadata_cache.json
docs/apis/cache.md           # Document gradient fields
docs/apis/assets.md          # Document gradient fields
```

### Generated Files (Runtime)

```
{config_dir}/cache/images/metadata.json          # ImageCache metadata (stores gradients)
{config_dir}/assets/.asset_metadata_cache.json   # Asset metadata cache (hidden file)
```

### Optional Files (Phase 5, if needed)

```
ledfx/api/
  gradients_refresh.py       # Optional on-demand refresh endpoint
  test_gradient_extraction.py         # Core function tests
  test_api_gradients_extract.py       # API tests

docs/apis/
  gradients.md              # API documentation
```

### Modified Files (Minimal Changes Expected)

```
ledfx/color.py              # May add LED correction utilities (optional)
ledfx/utils.py              # May add gradient helper functions (optional)
docs/developer/index.rst    # Link to new docs
```

### Key Existing Files (Referenced, Not Modified)

```
ledfx/color.py              # Gradient and color utilities
ledfx/utils.py              # open_image(), ImageCache access
ledfx/api/__init__.py       # RestEndpoint base class
ledfx/utilities/security_utils.py   # Security validation functions
ledfx/utilities/image_utils.py      # get_image_metadata()
ledfx/effects/gradient.py   # GradientEffect base class
```

### New Files Created

```
ledfx/utilities/gradient_extraction.py   # Core extraction functions (642 lines)
tests/test_gradient_extraction.py        # Unit tests (329 lines, 25/25 passing)
tests/test_gradient_integration.py       # Integration tests (283 lines, 8/8 passing)
docs/developer/strategy_led_safe_gradients.md  # This document (1099 lines)
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Color extraction too slow | ~~Medium~~ **Low** | High | **✅ Mitigated**: Thumbnail skip + asset caching implemented |
| LED correction subjective | High | Medium | Provide tunable parameters |
| Security bypass potential | Low | Critical | Reuse existing validation, comprehensive tests |
| Gradient format incompatibility | Low | High | Use existing structures, integration tests |
| Unstable gradients | Medium | Medium | Implement hashing/sorting stability |

---

## Dependencies

### External Libraries (already in project)
- `PIL` / `Pillow`: Image processing
- `numpy`: Numerical operations
- `colorsys`: Color space conversions
- `aiohttp`: REST endpoints

### Internal Dependencies
- `ledfx.color`: Color utilities
- `ledfx.utils`: Base classes
- `ledfx.assets`: Secure image loading
- `ledfx.api`: REST patterns

---

## Success Metrics

### Functional
- [ ] Gradients render correctly on WS2812 matrices
- [ ] Whites are controlled and visually pleasing
- [ ] No accent color dominance
- [ ] Stable gradients for similar images

### Technical
- [ ] 100% test coverage for core functions
- [ ] API follows all LedFx patterns
- [ ] No security vulnerabilities
- [ ] Processing time < 100ms for typical images

### Integration
- [ ] Usable from effects
- [ ] Frontend can consume API
- [ ] No breaking changes to existing code

---

## Resolved Design Decisions ✅

1. **Color Quantization Algorithm**:
   - ✅ **Pillow quantize()** - Built-in, good balance, sufficient quality

2. **LED Correction Parameters**:
   - ✅ **Hard-coded initially** - LED_SAFE defaults, configurable params later

3. **Gradient Stop Count**:
   - ✅ **Fixed at 8 maximum** - Sufficient for LED effects, parameterize later

4. **Dominant Background Handling**: ⭐ **CRITICAL DECISION**
   - ✅ **Separate background when >50% frequency**
   - ✅ **Build gradient from remaining accent colors**
   - ✅ **Return background_color as separate field**
   - **Rationale**: Prevents washed-out gradients, matches human perception

5. **Caching Strategy**:
   - ✅ **Extend ImageCache metadata** with extracted gradients

6. **API Variants**:
   - ✅ **Return all variants** (raw/safe/punchy), let client choose

7. **LED Hardware Profiles**:
   - ✅ **Start with WS2812 standard**, extend to profiles later if needed

8. **Architecture**:
   - ✅ **Integrate into ImageCache/asset pipeline** instead of separate API
   - ✅ **Auto-extract on all image loads** (one-time cost, cached)
   - ✅ **No new REST endpoint needed** - existing APIs return gradients

9. **API Response Structure**:
   - ✅ **Expose gradient CSS string, background_color, background_frequency only**
   - ✅ **Internal stops/dominant_colors arrays not exposed** (implementation details)

---

## Next Steps (Phase 4-5)

**Phase 4 Remaining**: Visual validation, security testing
**Phase 5**: Documentation updates (cache.md, assets.md), usage examples

**Implementation Notes**:
- Core extraction complete with all variants (raw/safe/punchy) ✅
- Integrated into ImageCache and Assets with caching ✅
- Unit & integration tests complete (33/33 passing) ✅
- Each variant contains only gradient CSS string
- Background color/frequency in metadata section (extraction properties, not variant-specific)
- background_color is always the most frequent color
- has_dominant_background metadata indicates if >50% threshold met
- Internal stops/dominant_colors used for construction but not exposed

---

## Appendix

### References
- LedFx gradient format: (TBD - document during Phase 1)
- Existing color utilities: `ledfx/color.py`
- Asset security: `ledfx/assets.py`
- API patterns: `ledfx/api/README.md` (if exists)

### Algorithm Research
- Color quantization: [Pillow Image.quantize](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.quantize)
- LED gamma correction: Standard 2.2-2.8 range
- HSV color space: Python `colorsys` module

### Dominant Background Strategy

Images with dominant backgrounds (>50% single color) use interleaved gradient pattern:
1. Detect background color (>50% frequency threshold)
2. Build gradient alternating: `bg → accent1 → bg → accent2 → bg → accent3 → bg`
3. Creates distinct color "islands" separated by background
4. Prevents washed-out gradients, maintains vibrant accent colors

**Example**: Album art with 70% black, 15% red, 10% blue, 5% gold
- Without detection: Gradient is 70% black (poor)
- With interleaved pattern: Black separates vibrant red/blue/gold islands (excellent)

**Stop Allocation** (8 max):
- 4 accents: `bg, c1, bg, c2, bg, c3, bg, c4` (8 stops)
- 3 accents: `bg, c1, bg, c2, bg, c3, bg` (7 stops)
- 2 accents: `bg, c1, bg, c2, bg` (5 stops)
- No dominant: All colors weighted (8 stops)

### Color Deduplication Strategy

To prevent gradients dominated by close color variants (e.g., 5 shades of blue that are perceptually similar), colors are deduplicated after quantization:

**Method**: Weighted HSV distance calculation
- **Hue difference** (most important): Weighted 0.65 for saturated colors
- **Saturation difference**: Weighted 0.20
- **Value difference**: Weighted 0.15
- **Threshold**: Colors within 0.20 weighted distance are merged

**Special handling for grays** (saturation < 15%):
- Hue matters less (weight 0.1) since grays have undefined hue
- Value matters more (weight 0.7) to distinguish light/dark grays
- Prevents all grays from merging into a single color

**Merging behavior**:
- Similar colors have their frequencies combined
- The first (highest frequency) color in each cluster is kept
- Results in cleaner gradients with distinct, perceptually different colors

**Example**: Image with 5 similar blues (hues 0.55-0.62) → Merged to 1-2 distinct blues

---

## Phase 2 & 3 Completion Summary

### Phase 2: Core Module Implementation ✅

**gradient_extraction.py** (642 lines): Complete extraction pipeline with all functions

✅ **Color Extraction**: Pillow MEDIANCUT quantization, frequency-weighted sorting, perceptual color deduplication
✅ **Background Detection**: >50% threshold detection with interleaved gradient pattern
✅ **LED Correction**: Brightness cap (0.85), saturation (0.90), gamma 2.2, white replacement
✅ **Gradient Construction**: Interleaved pattern for backgrounds, weighted for others
✅ **Metadata Wrapper**: `extract_gradient_metadata()` returns all variants + metadata

**Test Coverage**: 25/25 passing (test_gradient_extraction.py)
- extract_dominant_colors: 5 tests
- detect_dominant_background: 4 tests
- apply_led_correction: 6 tests
- build_gradient_stops: 5 tests
- build_gradient_string: 3 tests
- extract_gradient_metadata: 2 tests

**Performance**: ~20-50ms total per image (one-time cost)

---

### Phase 3: Pipeline Integration ✅

**ImageCache Integration** (ledfx/libraries/cache.py):
- Gradient extraction in `put()` method (lines 175-191)
- **Thumbnail optimization**: Skips extraction when `params != None` (thumbnails only)
- Prevents redundant extraction (1 image = 16 thumbnails → only 1 gradient extraction)
- **Built-in caching**: Stores in existing `metadata.json` file (no separate cache needed)
- Stored in cache metadata with width, height, format, n_frames, is_animated
- Try/except prevents breaking on failures
- One-time extraction, cached forever
- **API exposure**: `get_stats()` updated to include gradients in response (line 378)

**Asset Integration** (ledfx/assets.py):
- **Metadata caching system** for performance optimization
  - Cache file: `.asset_metadata_cache.json` in assets directory (generic structure for extensibility)
  - Functions: `_load_asset_metadata_cache()`, `_save_asset_metadata_cache()`
  - Cache structure: `{"path": {"gradients": {...}, "modified_time": "..."}}`
  - Added to `IGNORED_FILES` to exclude from asset listings
- Gradient extraction in `_list_assets_from_directory()` with caching (lines 540-630)
  - Load cache at start of directory walk
  - Check cache for each file (compare modification time)
  - Cache hit: Use stored gradients (instant retrieval)
  - Cache miss: Extract gradients, update cache
  - Cache failure: Store `gradients: null` to avoid re-attempting
  - Save cache after directory walk if updated
- Cache invalidation in `delete_asset()` (lines 468-478)
  - Remove cache entry when file deleted
  - Keeps cache synchronized with filesystem
- Graceful error handling:
  - Empty cache file: Returns empty dict, extracts all fresh
  - Corrupted cache: Logs warning, returns empty dict
  - Cache save failure: Continues without caching (degrades to extraction per list)
- Performance impact: 16 files on first list → 16 extractions, subsequent lists → 0 extractions

**API Enhancement** (Zero New Endpoints):
- `/api/cache/images` GET - Returns gradients in cache entries via `get_stats()` (ImageCache built-in caching)
- `/api/assets` GET - Returns gradients in asset list (with separate metadata cache file)
- Backward compatible - optional metadata field
- No breaking changes

**Caching Strategy**:
- **cache.py**: Uses built-in `metadata.json` for all cache metadata (one-time extraction per image)
- **assets.py**: Uses separate `.asset_metadata_cache.json` for directory-level caching

**Test Coverage**: 33/33 passing (100%)
- test_gradient_extraction.py: 25 tests (core algorithms)
- test_gradient_integration.py: 8 tests (ImageCache, Assets, thumbnail optimization)

**API Responses**:
- Each variant (raw, led_safe, led_punchy) contains only the gradient CSS string
- background_color and background_frequency are in metadata section (extraction properties, not variant-specific)
- background_color always populated when extraction succeeds
- has_dominant_background metadata field indicates if most frequent color is >50%
- Internal stops/dominant_colors arrays not exposed (used for construction only)

---

## Implementation Status

**Phases Complete**: 3.5/5 (70%)
**Current Phase**: Phase 4 - Testing & Validation (Partially Complete)

**Completed**:
- Phase 1: Discovery & Analysis ✅
- Phase 2: Core Module Implementation ✅
- Phase 3: Pipeline Integration ✅
- Phase 4: Unit & Integration Tests ✅

**Remaining Work**:
- Phase 4: Visual validation, security testing
- Phase 5: Documentation updates (cache.md, assets.md), usage examples

Core implementation complete. Gradients automatically extracted for all images.
