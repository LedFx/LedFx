# Strategy Document: Image-Derived LED-Safe Gradient Extraction

**Created**: February 13, 2026
**Status**: Phase 3 Complete - Pipeline Integration Finished (with latest optimizations)
**Last Updated**: February 13, 2026
**Target**: LedFx Core Gradient System

---

## Executive Summary

Implement a backend service for extracting LED-optimized color gradients from images (album art, user uploads, cached images). The system will produce multiple gradient variants:
- **Raw**: True to source image, ideal for screen previews
- **LED-safe**: Optimized for WS2812/HUB75 RGB matrices
- **LED-punchy** (optional): Enhanced saturation variant

This addresses current issues where screen-optimized color extraction produces poor results on physical LED hardware due to gamma, brightness limits, and lack of true white.

---

## Problem Statement

### Current Issues
1. **Saturation blowout**: Colors too intense on LED matrices
2. **Washed-out whites**: Near-white colors render poorly without true white LEDs
3. **Accent color dominance**: Minor colors take excessive gradient space
4. **Gradient instability**: Small image changes cause large gradient shifts

### Root Cause
Existing extraction optimized for screens, not LED physics (gamma, brightness, RGB-only color space).

---

## Architecture Overview

**⭐ CRITICAL ARCHITECTURAL DECISION: Integrated Pipeline (Not a Separate API)**

Instead of creating a new REST endpoint, gradient extraction is **integrated directly into the image loading pipeline**. Every image automatically gets gradient metadata extracted and stored alongside other image properties (width, height, format).

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

### Key Integration Points

1. **ImageCache.put()** (`ledfx/libraries/cache.py`)
   - Already extracts: width, height, format, n_frames, is_animated
   - **Add**: Extract gradients (raw, led_safe, led_punchy variants)
   - Store in cache entry metadata
   - One-time extraction, cached forever

2. **save_asset()** (`ledfx/assets.py`)
   - Already validates and stores images
   - **Add**: Extract gradients during save
   - Include in asset list responses

3. **Existing APIs Automatically Enhanced**:
   - `/api/cache/images` - GET returns cache entries with gradients
   - `/api/assets` - GET returns asset list with gradients
   - `/api/assets/download` - Could include gradient metadata in response
   - **No new API endpoint needed!** ✅

### Advantages of Integrated Approach

✅ **Automatic extraction** - Every image gets gradients without explicit request
✅ **One-time cost** - Extract once during cache/save, use forever
✅ **No API changes** - Existing endpoints just return more metadata
✅ **Consistent everywhere** - All images have gradients (URLs, uploads, cached)
✅ **Frontend simplicity** - Load image, get gradients automatically
✅ **Memory efficient** - Gradients are JSON strings (< 1KB per variant)
✅ **Backward compatible** - Old clients ignore new metadata fields

### Automatic Re-extraction via Existing Cache Refresh

For cases where re-extraction is needed (algorithm updates, different parameters):

**Use existing cache refresh endpoint** - No new endpoint needed! 🎉

The existing `/api/cache/images/refresh` endpoint will automatically re-extract gradients:

```
POST /api/cache/images/refresh
{
  "url": "https://example.com/art.jpg"
}
```

**How it works**:
1. Cache entry is deleted (`cache.delete(url)`)
2. Image is re-downloaded and cached (`open_image` → `ImageCache.put()`)
3. **Gradients are automatically re-extracted** during `put()`
4. Response includes fresh gradients in metadata

**Use cases**:
- Algorithm improvements (refresh cache → auto re-extract)
- Parameter tuning (modify extraction code → refresh cache)
- Debugging (force fresh extraction with existing tools)

**No new API needed** - gradient extraction piggybacks on existing cache infrastructure!

---

## Implementation Phases

### Phase 1: Discovery & Analysis
**Status**: ✅ Completed
**Duration**: 1-2 hours

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

### Phase 2: Core Algorithm Implementation
**Status**: ✅ COMPLETE
**Duration**: 3-4 hours (Completed: February 13, 2026)

#### Objectives
- Implement pure extraction functions
- Create LED correction algorithms
- Ensure deterministic, testable behavior
- **NEW**: Create metadata extraction wrapper for integration

#### Tasks

1. **Create Core Module** (`ledfx/utilities/gradient_extraction.py`)
   - Pure functions for color extraction, background detection, gradient construction
   - LED correction algorithms (safe/punchy variants)
   - `extract_gradient_metadata(pil_image)` wrapper returns all variants + metadata
   - Internally uses stops and dominant_colors; API exposes gradient string + background info

2. **Palette Extraction Algorithm**
   - [x] Implement color quantization using Pillow's `image.quantize()`
   - [x] Add frequency weighting logic (pixel count per color)
   - [x] **Color deduplication** to prevent gradients dominated by similar colors
     - Uses HSV distance with weighted importance (hue > saturation > value)
     - Merges colors within perceptual similarity threshold
     - Combines frequencies when merging
   - [x] Create stability mechanisms (sort by frequency, then hue)
   - [x] Optimize with NumPy operations

3. **Dominant Background Detection** ⭐ **NEW**
   - [x] Detect if one color is significantly dominant (>50% frequency)
   - [x] When detected: build INTERLEAVED gradient pattern
   - [x] Pattern: `bg → c1 → bg → c2 → bg → c3 → bg → ...`
   - [x] Creates distinct "islands" of accent colors separated by background
   - [x] Stop allocation: With 8 stops max, supports up to 4 accent colors
     - 3 accent colors: `bg, c1, bg, c2, bg, c3, bg` (7 stops)
     - 4 accent colors: `bg, c1, bg, c2, bg, c3, bg, c4` (8 stops)
   - [x] If no dominant background: build normal gradient from all colors (max 8 stops)

4. **LED Correction Algorithms**
   - [x] Implement brightness capping (max_value = 0.85)
   - [x] Add saturation reduction (max_saturation = 0.90)
   - [x] Create white detection and replacement (low saturation + high value)
   - [x] Apply LED gamma correction (2.2)
   - [x] Add RGB channel clamping

5. **Gradient Construction**
   - [x] **Normal mode** (no dominant background): Weighted stop placement based on frequency
   - [x] **Interleaved mode** (dominant background detected):
     - Alternate between background and accent colors
     - Even spacing: 0%, 12.5%, 25%, 37.5%, 50%, 62.5%, 75%, 87.5%, 100%
     - Creates visual "splotches" of color separated by background
     - Pattern: `bg → accent1 → bg → accent2 → bg → accent3 → bg`
   - [x] LedFx gradient format conversion (linear-gradient string)
   - [x] Variant generation (raw/safe/punchy modes)
   - [x] Always include background_color (most frequent color) and background_frequency

6. **Metadata Extraction Wrapper** ⭐
   ```python
   def extract_gradient_metadata(pil_image: Image.Image) -> dict:
       """
       Extract all gradient variants and metadata from PIL image.

       Returns dict suitable for storage in ImageCache or asset metadata:
       {
           "gradients": {
               "raw": {"gradient": "..."},
               "led_safe": {"gradient": "..."},
               "led_punchy": {"gradient": "..."},
               "metadata": {
                   "background_color": "#...",
                   "background_frequency": 0.7,
                   ...
               }
           }
       }
       """
   ```

#### Acceptance Criteria
- Functions accept PIL Image input
- No I/O operations in core functions
- NumPy-optimized (no pixel loops)
- Deterministic output for same input
- Unit testable
- **Metadata wrapper returns dict ready for JSON storage** ⭐

#### Test Scenarios
- Extract from solid color image → Should detect as 100% background, derive simple gradient
- Extract from multi-color gradient image → Should distribute colors evenly
- Handle near-white colors → Should apply LED white correction
- Process small vs large images → Should maintain consistency
- Validate stability (similar images → similar gradients)
- **Album art with 70% black background** → Should separate background, vibrant accent gradient ⭐
- **Album art with 80% white background** → Should separate, apply white correction ⭐
- **Photo with no dominant color (<50%)** → Should use all colors in gradient ⭐
- **Two-color image (60% bg + 40% accent)** → Should detect bg, single-color gradient ⭐
- **Metadata serialization** → Dict is JSON-serializable, no PIL objects ⭐

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
