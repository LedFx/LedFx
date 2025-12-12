# Assets API

## Overview

LedFx provides secure API endpoints for managing image assets from two sources:

1. **User Assets** (`GET/POST/DELETE /api/assets`) - User-uploaded images stored in the configuration directory under `.ledfx/assets/` with full read/write access and comprehensive security controls including path traversal protection, content validation, and size limits.

2. **Built-in Assets** (`GET /api/assets_fixed`) - Pre-installed GIFs and images bundled with LedFx in `ledfx_assets/gifs/`. These are read-only and provide default assets for effects.

## Asset Storage

**User Assets** are stored in:
```text
{config_dir}/assets/
```

Where `{config_dir}` is the LedFx configuration directory (e.g., `~/.ledfx` on Linux/macOS or `%USERPROFILE%\.ledfx` on Windows).

**Built-in Assets** are bundled with LedFx installation:
```text
{ledfx_assets}/gifs/
```

Where `{ledfx_assets}` is the LedFx installation assets directory containing pre-installed GIFs and images.

**Example structure:**

The directory structure under `assets/` is arbitrary and determined by the frontend or application using the API. Assets can be organized in any folder hierarchy as needed.

```text
.ledfx/
  assets/                    # User-uploaded assets (read/write)
    icon.png
    backgrounds/
      galaxy.jpg
      nebula.webp
    effects/
      fire/
        texture.png

ledfx_assets/
  gifs/                      # Built-in assets (read-only)
    skull.gif
    catfixed.gif
    bumble.gif
    pixelart/
      animation.gif
```

## Asset Source Selection

LedFx provides **clear separation** between user assets and built-in assets using an explicit prefix system:

### Path Syntax

- **User assets**: Use path without prefix
  - Example: `"backgrounds/galaxy.jpg"` → `{config_dir}/assets/backgrounds/galaxy.jpg`
  - Example: `"skull.gif"` → `{config_dir}/assets/skull.gif`

- **Built-in assets**: Use `builtin://` prefix
  - Example: `"builtin://skull.gif"` → `{ledfx_assets}/gifs/skull.gif`
  - Example: `"builtin://pixelart/dj_bird.gif"` → `{ledfx_assets}/gifs/pixelart/dj_bird.gif`

### Endpoint Support

| Endpoint | User Assets | Built-in Assets |
|----------|-------------|------------------|
| `GET /api/assets` | ✅ List only | ❌ |
| `GET /api/assets_fixed` | ❌ | ✅ List only |
| `GET /api/assets/download` | ✅ (no prefix) | ✅ (`builtin://` prefix) |
| `POST /api/assets/download` | ✅ (no prefix) | ✅ (`builtin://` prefix) |
| `POST /api/assets/thumbnail` | ✅ (no prefix) | ✅ (`builtin://` prefix) |
| `POST /api/assets` (upload) | ✅ | ❌ Read-only |
| `DELETE /api/assets` | ✅ | ❌ Read-only |

## Supported Image Formats

- PNG (`.png`)
- JPEG (`.jpg`, `.jpeg`)
- GIF (`.gif`)
- WebP (`.webp`)
- BMP (`.bmp`)
- TIFF (`.tiff`, `.tif`)
- ICO (`.ico`)

## Security Features

### Path Traversal Protection

All paths are validated to prevent directory traversal attacks:

**Rejected patterns:**
- `../../../etc/passwd`
- `/absolute/path`
- `C:\Windows\system32`
- `\\network\share`
- `file:///etc/passwd`
- Null bytes (`\0`)
- Unicode normalization attacks

### Content Validation

Files are validated using Pillow to ensure they contain actual image data:

- Extension alone is not sufficient
- MIME type must be in allowed list (image/png, image/jpeg, image/gif, etc.)
- File content must parse as valid image with Pillow
- PIL format must match allowed formats
- Extension must match actual file content
- Corrupted or fake images are rejected

### Size Limits

Default maximum file size is 10MB. This limit accounts for animated GIFs and WebP files which can be larger than static images.

### Automatic Cleanup

When deleting assets, empty parent directories are automatically removed.

## API Endpoints

### List User Assets

Get a list of all user-uploaded assets with metadata from `{config_dir}/assets/`.

#### **Endpoint:** `GET /api/assets`

**Success Response (bare response - no status wrapper):**
```json
{
  "assets": [
    {
      "path": "icon.png",
      "size": 15234,
      "modified": "2025-11-30T10:30:00+00:00",
      "width": 512,
      "height": 512,
      "format": "PNG",
      "n_frames": 1,
      "is_animated": false
    },
    {
      "path": "backgrounds/galaxy.jpg",
      "size": 234567,
      "modified": "2025-11-28T14:22:15+00:00",
      "width": 1920,
      "height": 1080,
      "format": "JPEG",
      "n_frames": 1,
      "is_animated": false
    }
  ]
}
```

**Metadata Fields:**
- `path` (string) - Relative path to the asset
- `size` (integer) - File size in bytes
- `modified` (string) - ISO 8601 timestamp of last modification (UTC)
- `width` (integer) - Image width in pixels (0 if unreadable)
- `height` (integer) - Image height in pixels (0 if unreadable)
- `format` (string|null) - Image format detected by PIL (e.g., "PNG", "JPEG", "GIF", "WEBP")
- `n_frames` (integer) - Number of frames (1 for static images, >1 for animated GIF/WebP)
- `is_animated` (boolean) - True if the image contains multiple frames (animated GIF or WebP)

**Entries sorted by:** Path name (alphabetical)

---

### List Built-in Assets

Get a list of all built-in assets with metadata from `{ledfx_assets}/gifs/`.

#### **Endpoint:** `GET /api/assets_fixed`

**Success Response (bare response - no status wrapper):**
```json
{
  "assets": [
    {
      "path": "skull.gif",
      "size": 123456,
      "modified": "2025-10-15T08:30:00+00:00",
      "width": 64,
      "height": 64,
      "format": "GIF",
      "n_frames": 12,
      "is_animated": true
    },
    {
      "path": "catfixed.gif",
      "size": 234567,
      "modified": "2025-10-15T08:30:00+00:00",
      "width": 48,
      "height": 48,
      "format": "GIF",
      "n_frames": 8,
      "is_animated": true
    },
    {
      "path": "pixelart/dj_bird.gif",
      "size": 345678,
      "modified": "2025-10-15T08:30:00+00:00",
      "width": 128,
      "height": 128,
      "format": "GIF",
      "n_frames": 24,
      "is_animated": true
    }
  ]
}
```

**Metadata Fields:**
- `path` (string) - Relative path to the built-in asset from `ledfx_assets/gifs/`
  - Root-level: `"skull.gif"` (refers to `ledfx_assets/gifs/skull.gif`)
  - Subdirectory: `"pixelart/dj_bird.gif"` (refers to `ledfx_assets/gifs/pixelart/dj_bird.gif`)
- `size` (integer) - File size in bytes
- `modified` (string) - ISO 8601 timestamp of last modification (UTC)
- `width` (integer) - Image width in pixels (0 if unreadable)
- `height` (integer) - Image height in pixels (0 if unreadable)
- `format` (string|null) - Image format detected by PIL (e.g., "PNG", "JPEG", "GIF", "WEBP")
- `n_frames` (integer) - Number of frames (1 for static images, >1 for animated GIF/WebP)
- `is_animated` (boolean) - True if the image contains multiple frames (animated GIF or WebP)

**Entries sorted by:** Path name (alphabetical)

**Notes:**
- Built-in assets are **read-only** - they can be used in effects but cannot be modified or deleted via the API
- This endpoint lists **only** built-in assets - use `GET /api/assets` to list user-uploaded assets
- To guarantee accessing a built-in asset (not a user override), check this list first and verify the user hasn't uploaded a file with the same path

---

### Upload Asset

Upload a new image asset. Requires `multipart/form-data` encoding.

#### **Endpoint:** `POST /api/assets`

**Request Parameters:**
- `file` (file) - The image file to upload
- `path` (string) - Relative path where asset should be stored (e.g., `icons/led.png`)

**Success Response:**
```json
{
  "status": "success",
  "data": {
    "path": "icons/led.png"
  }
}
```

**Error Response:**
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Extension .txt is not allowed"
  }
}
```

**Validation Rules:**
- File must be a valid image (content-verified)
- Extension must be in allowed list
- Path must not contain traversal sequences (`..`, absolute paths, etc.)
- File size must not exceed 10MB
- Uploading to an existing path will replace the file

**Example:**
```bash
curl -X POST http://localhost:8888/api/assets -F "file=@/path/to/image.png" -F "path=icons/led.png"
```

---

### Download Asset

Download a specific asset file (user or built-in).

**Methods:** Both GET and POST supported
- **GET** - Browser-friendly, query parameters
- **POST** - Programmatic, JSON body

**Asset Sources:**
- **User assets**: No prefix → `{config_dir}/assets/{path}`
- **Built-in assets**: `builtin://` prefix → `{ledfx_assets}/gifs/{path}`

#### GET /api/assets/download

Browser-friendly method using query parameters.

**Query Parameters:**
- `path` (string, required) - Asset path
  - User: `"icons/led.png"`
  - Built-in: `"builtin://skull.gif"`

**Response:**
- **Success**: Binary image data with `Content-Type` header (HTTP 200)
- **Error**: JSON error message (HTTP 200)

**Examples:**
```bash
# User asset
curl "http://localhost:8888/api/assets/download?path=icons/led.png" --output led.png

# Built-in asset
curl "http://localhost:8888/api/assets/download?path=builtin://skull.gif" --output skull.gif
```

**Browser Usage:**
```html
<!-- User asset -->
<img src="http://localhost:8888/api/assets/download?path=icons/led.png" alt="LED Icon">

<!-- Built-in asset -->
<img src="http://localhost:8888/api/assets/download?path=builtin://skull.gif" alt="Skull">

<!-- Download link -->
<a href="http://localhost:8888/api/assets/download?path=galaxy.jpg" download>Download</a>
```

#### POST /api/assets/download

Programmatic method using JSON body.

**Request Body:**
```json
{
  "path": "icons/led.png"              // User asset
}
```
```json
{
  "path": "builtin://skull.gif"        // Built-in asset
}
```

**Response:**
- **Success**: Binary image data with `Content-Type` header (HTTP 200)
- **Error**: JSON error message (HTTP 200)

**Examples:**
```bash
# User asset
curl -X POST http://localhost:8888/api/assets/download \
  -H "Content-Type: application/json" \
  -d '{"path": "icons/led.png"}' \
  --output led.png

# Built-in asset
curl -X POST http://localhost:8888/api/assets/download \
  -H "Content-Type: application/json" \
  -d '{"path": "builtin://skull.gif"}' \
  --output skull.gif
```

**Error Response:**
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Asset not found: icons/led.png"
  }
}
```

---

### Get Asset Thumbnail

Generate a thumbnail for an asset (user or built-in).

**Thumbnail Caching:** Generated thumbnails are automatically cached for improved performance. The cache key includes the asset path and all parameters (size, dimension, animated), so different thumbnail variations are cached separately. Cached thumbnails follow the same LRU eviction policy as remote images and are subject to the same cache size/count limits.

#### **Endpoint:** `POST /api/assets/thumbnail`

**Asset Sources:**
- **User assets**: No prefix → `{config_dir}/assets/{path}`
- **Built-in assets**: `builtin://` prefix → `{ledfx_assets}/gifs/{path}`

**Request Body:**
```json
{
  "path": "backgrounds/galaxy.jpg",    // Required: asset path
  "size": 256,                         // Optional: 16-512, default: 128
  "dimension": "width",                // Optional: "max"|"width"|"height", default: "max"
  "animated": true,                    // Optional: preserve animation, default: true
  "force_refresh": false               // Optional: force regeneration, default: false
}
```

**Parameters:**
- `path` (string, required) - Asset path
  - User: `"backgrounds/galaxy.jpg"`
  - Built-in: `"builtin://skull.gif"`
- `size` (integer, optional) - Dimension in pixels (16-512, default: 128)
- `dimension` (string, optional) - Sizing mode (default: "max")
  - `"max"` - Size to longest axis (maintains aspect ratio)
  - `"width"` - Set width to size, scale height proportionally
  - `"height"` - Set height to size, scale width proportionally
- `animated` (boolean, optional) - Preserve animation (default: true)
  - `true` - Return animated WebP for GIF/WebP
  - `false` - Return static PNG of first frame
- `force_refresh` (boolean, optional) - Force regeneration bypassing cache (default: false)
  - `true` - Clear cache and regenerate thumbnail
  - `false` - Use cached thumbnail if available

**Response:**
- **Success**: Thumbnail image (HTTP 200)
  - Static: PNG format (`image/png`)
  - Animated: WebP format (`image/webp`)
- **Error**: JSON error message (HTTP 200)

**Examples:**
```bash
# Default 128px thumbnail (user asset)
curl -X POST http://localhost:8888/api/assets/thumbnail \
  -H "Content-Type: application/json" \
  -d '{"path": "backgrounds/galaxy.jpg"}' \
  --output thumb.png

# 64px animated thumbnail (built-in asset)
curl -X POST http://localhost:8888/api/assets/thumbnail \
  -H "Content-Type: application/json" \
  -d '{"path": "builtin://skull.gif", "size": 64}' \
  --output skull-thumb.webp

# 256px width-constrained thumbnail
curl -X POST http://localhost:8888/api/assets/thumbnail \
  -H "Content-Type: application/json" \
  -d '{"path": "image.png", "size": 256, "dimension": "width"}' \
  --output thumb-256w.png

# Static PNG of first frame
curl -X POST http://localhost:8888/api/assets/thumbnail \
  -H "Content-Type: application/json" \
  -d '{"path": "builtin://skull.gif", "animated": false}' \
  --output skull-static.png

# Force regenerate thumbnail (bypass cache)
curl -X POST http://localhost:8888/api/assets/thumbnail \
  -H "Content-Type: application/json" \
  -d '{"path": "backgrounds/galaxy.jpg", "force_refresh": true}' \
  --output fresh-thumb.png
```

**Error Response:**
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Asset not found: backgrounds/galaxy.jpg"
  }
}
```

---

### Delete Asset

Delete a user asset and clean up empty directories.

#### **Endpoint:** `DELETE /api/assets`

**Query Parameters (recommended):**
```bash
DELETE /api/assets?path=icons/led.png
```

**OR Request Body (alternative):**
```json
{
  "path": "icons/led.png"
}
```

**Response:**
- **Success**: Confirmation with deleted path (HTTP 200)
- **Error**: JSON error message (HTTP 200)

**Examples:**
```bash
# Query parameter (recommended)
curl -X DELETE "http://localhost:8888/api/assets?path=icons/led.png"

# JSON body (alternative)
curl -X DELETE http://localhost:8888/api/assets \
  -H "Content-Type: application/json" \
  -d '{"path": "icons/led.png"}'
```

**Success Response:**
```json
{
  "status": "success",
  "data": {
    "deleted": true,
    "path": "icons/led.png"
  }
}
```

**Error Response:**
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Asset not found: icons/missing.png"
  }
}
```

**Note:** Empty parent directories are automatically removed after deleting an asset.

---

## Error Handling

All endpoints return HTTP 200 with status information in the JSON payload to support frontend notifications:

**Success:**
```text
{
  "status": "success",
  "data": { ... }
}
```

**Failure:**
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Detailed error message"
  }
}
```

**Note:** The download endpoint returns binary image data on success, or the standard JSON error response on failure (both with HTTP 200 status).
