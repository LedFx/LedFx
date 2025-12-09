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

**Endpoint:** `GET /api/assets`

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

**Endpoint:** `GET /api/assets_fixed`

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

**Endpoint:** `POST /api/assets`

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
```javascript
const formData = new FormData();
formData.append('file', imageFile);
formData.append('path', 'icons/led.png');

fetch('/api/assets', {
  method: 'POST',
  body: formData
});
```

---

### Download Asset

Retrieve a specific asset file.

**Endpoint:** `POST /api/assets/download`

**Request Body (JSON):**
```json
{
  "path": "icons/led.png"
}
```

**Parameters:**
- `path` (string, required) - Relative path to the asset

**Success Response:**
- Binary image data with appropriate `Content-Type` header (HTTP 200)

**Error Response (HTTP 200 with JSON):**
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Asset not found: icons/led.png"
  }
}
```

**Example:**
```bash
curl -X POST http://localhost:8888/api/assets/download \
  -H "Content-Type: application/json" \
  -d '{"path": "icons/led.png"}' \
  --output led.png
```

```javascript
// Download asset
fetch('/api/assets/download', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ path: 'icons/led.png' })
})
  .then(response => response.blob())
  .then(blob => {
    const url = URL.createObjectURL(blob);
    // Use the image...
  });
```

---

### Get Asset Thumbnail

Generate a thumbnail of an asset on-demand.

**Supports both user and built-in assets** using explicit path syntax:
- **User assets**: Path without prefix (e.g., `"backgrounds/image.jpg"`)
- **Built-in assets**: Path with `builtin://` prefix (e.g., `"builtin://skull.gif"`)

**Endpoint:** `POST /api/assets/thumbnail`

**Request Body (JSON):**
```json
// User asset
{
  "path": "backgrounds/galaxy.jpg",      // User asset (no prefix)
  "size": 256,                           // optional, default: 128
  "dimension": "width"                   // optional, default: "max"
}

// Built-in asset
{
  "path": "builtin://skull.gif",         // Built-in asset (builtin:// prefix)
  "size": 128
}
```

**Parameters:**
- `path` (string, required) - Path to the asset with explicit source selection
  - **User assets** (no prefix): `{config_dir}/assets/{path}`
    - `"backgrounds/galaxy.jpg"` → `{config_dir}/assets/backgrounds/galaxy.jpg`
    - `"my-image.png"` → `{config_dir}/assets/my-image.png`
  - **Built-in assets** (`builtin://` prefix): `{ledfx_assets}/gifs/{path}`
    - `"builtin://skull.gif"` → `{ledfx_assets}/gifs/skull.gif`
    - `"builtin://pixelart/dj_bird.gif"` → `{ledfx_assets}/gifs/pixelart/dj_bird.gif`
- `size` (integer, optional) - Dimension size in pixels (default: 128)
  - Must be an integer between 16 and 512
  - Values outside this range will return a validation error
- `dimension` (string, optional) - Which dimension to apply size to (default: "max")
  - `"max"` - Apply size to longest axis (default behavior, maintains aspect ratio)
  - `"width"` - Apply size to width, scale height proportionally
  - `"height"` - Apply size to height, scale width proportionally

**Success Response:**
- PNG image data with `Content-Type: image/png` header (HTTP 200)
- Dimensions: Calculated based on `size` and `dimension` parameters
  - `dimension="max"`: Size applied to longest axis (default)
  - `dimension="width"`: Width set to `size`, height scaled proportionally
  - `dimension="height"`: Height set to `size`, width scaled proportionally
- Aspect ratio: Always preserved from original

**Error Response (HTTP 200 with JSON):**
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Asset not found in user assets or built-in assets: backgrounds/galaxy.jpg"
  }
}
```

**Example:**
```bash
# User asset: Default 128px thumbnail
curl -X POST http://localhost:8888/api/assets/thumbnail \
  -H "Content-Type: application/json" \
  -d '{"path": "backgrounds/galaxy.jpg"}' \
  --output thumbnail.png

# Built-in asset (root level): Thumbnail of skull.gif
curl -X POST http://localhost:8888/api/assets/thumbnail \
  -H "Content-Type: application/json" \
  -d '{"path": "builtin://skull.gif", "size": 64}' \
  --output skull-thumb.png

# Built-in asset (subdirectory): Thumbnail from pixelart folder
curl -X POST http://localhost:8888/api/assets/thumbnail \
  -H "Content-Type: application/json" \
  -d '{"path": "builtin://pixelart/dj_bird.gif", "size": 128}' \
  --output dj-bird-thumb.png

# Custom 256px thumbnail
curl -X POST http://localhost:8888/api/assets/thumbnail \
  -H "Content-Type: application/json" \
  -d '{"path": "backgrounds/galaxy.jpg", "size": 256}' \
  --output thumbnail-large.png

# 200px wide thumbnail (height scaled proportionally)
curl -X POST http://localhost:8888/api/assets/thumbnail \
  -H "Content-Type: application/json" \
  -d '{"path": "backgrounds/galaxy.jpg", "size": 200, "dimension": "width"}' \
  --output thumbnail-200w.png

# 150px tall thumbnail (width scaled proportionally)
curl -X POST http://localhost:8888/api/assets/thumbnail \
  -H "Content-Type: application/json" \
  -d '{"path": "backgrounds/galaxy.jpg", "size": 150, "dimension": "height"}' \
  --output thumbnail-150h.png
```

**Notes:**
- Thumbnails are generated on-demand and not cached
- All thumbnails are returned as PNG regardless of source format
- For animated images (GIF, WebP), the first frame is used
- Size parameter must be between 16 and 512 pixels (validation enforced)

---

### Delete Asset

Delete a specific asset and clean up empty directories.

**Endpoint:** `DELETE /api/assets`

**Query Parameters (recommended):**
- `path` (string, required) - Relative path to the asset to delete


`DELETE /api/assets?path=icons/led.png`

**OR Request Body (JSON, alternative):**
```json
{
  "path": "icons/led.png"
}
```

**Note:** Query parameter method is preferred for browser compatibility. JSON body is supported as fallback.

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

**Examples:**

Using query parameter (recommended):
```bash
curl -X DELETE "http://localhost:8888/api/assets?path=icons/led.png"
```

Using JSON body (alternative):
```bash
curl -X DELETE http://localhost:8888/api/assets \
  -H "Content-Type: application/json" \
  -d '{"path": "icons/led.png"}'
```

**Note:** When deleting assets, empty parent directories are automatically removed:

```bash
curl -X DELETE "http://localhost:8888/api/assets?path=effects/fire/texture.png"

Result:
- File deleted: effects/fire/texture.png
- Removed empty directory: effects/fire/
- Removed empty directory: effects/
```

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
