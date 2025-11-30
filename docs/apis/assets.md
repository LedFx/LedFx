# Assets API

## Overview

LedFx provides secure API endpoints for managing image assets stored in the configuration directory. Assets are stored under `.ledfx/assets/` with comprehensive security controls including path traversal protection, content validation, and size limits.

## Asset Storage

Assets are stored in:
```text
{config_dir}/.ledfx/assets/
```

Where `{config_dir}` is the directory containing the `.ledfx` configuration folder (typically the user's home directory).

**Example structure:**

The directory structure under `assets/` is arbitrary and determined by the frontend or application using the API. Assets can be organized in any folder hierarchy as needed.

```text
.ledfx/
  assets/
    icon.png
    backgrounds/
      galaxy.jpg
      nebula.webp
    effects/
      fire/
        texture.png
```

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

### List Assets

Get a list of all available assets.

**Endpoint:** `GET /api/assets`

**Success Response (bare response - no status wrapper):**
```json
{
  "assets": [
    "icon.png",
    "backgrounds/galaxy.jpg",
    "effects/fire/texture.webp"
  ]
}
```

**Entries sorted by:** Path name (alphabetical)

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

Retrieve a thumbnail version of an asset. Thumbnails are automatically generated on-demand with configurable maximum dimension, maintaining the original aspect ratio.

**Endpoint:** `POST /api/assets/thumbnail`

**Request Body (JSON):**
```json
{
  "path": "backgrounds/galaxy.jpg",      // required
  "size": 256,                           // optional, default: 128
  "dimension": "width"                   // optional, default: "max"
}
```

**Parameters:**
- `path` (string, required) - Relative path to the asset
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
    "reason": "Asset not found: backgrounds/galaxy.jpg"
  }
}
```

**Example:**
```bash
# Default 128px thumbnail
curl -X POST http://localhost:8888/api/assets/thumbnail \
  -H "Content-Type: application/json" \
  -d '{"path": "backgrounds/galaxy.jpg"}' \
  --output thumbnail.png

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
