# Assets API

## Overview

LedFx provides secure API endpoints for managing image assets stored in the configuration directory. Assets are stored under `.ledfx/assets/` with comprehensive security controls including path traversal protection, content validation, and size limits.

## Asset Storage

Assets are stored in:
```
{config_dir}/.ledfx/assets/
```

Where `{config_dir}` is the LedFx configuration directory.

**Example structure:**
```
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
- File content must parse as valid image
- Corrupted or fake images are rejected

### Size Limits

Default maximum file size is 2MB to prevent resource exhaustion.

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
- File size must not exceed 2MB
- Overwriting existing files is rejected by default

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

**Response:**
- Binary image data with appropriate `Content-Type` header

**Status Codes:**
- `200 OK` - Asset found and returned
- `200 OK` with error JSON - Asset does not exist or invalid path

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

### Delete Asset

Delete a specific asset and clean up empty directories.

**Endpoint:** `DELETE /api/assets`

**Query Parameters (recommended):**
- `path` (string, required) - Relative path to the asset to delete

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

## Use Cases

### Effect Icons

Store custom icons for effects:
```bash
curl -X POST http://localhost:8888/api/assets \
  -F "file=@icon.png" \
  -F "path=effects/rainbow/icon.png"
```

### Background Images

Upload background images for visualizations:
```bash
curl -X POST http://localhost:8888/api/assets \
  -F "file=@galaxy.jpg" \
  -F "path=backgrounds/space/galaxy.jpg"
```

### Texture Maps

Store texture maps for effects:
```bash
curl -X POST http://localhost:8888/api/assets \
  -F "file=@fire.webp" \
  -F "path=effects/fire/texture.webp"
```

---

## Error Handling

All endpoints return HTTP 200 with status information in the JSON payload to support frontend notifications:

**Success:**
```json
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

The only exception is the download endpoint, which returns 404 for missing assets.

---

## Example: Complete Upload Flow

```javascript
async function uploadAsset(file, path) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('path', path);

  const response = await fetch('/api/assets', {
    method: 'POST',
    body: formData
  });

  const result = await response.json();

  if (result.status === 'success') {
    console.log('Asset uploaded:', result.data.path);
    return result.data.path;
  } else {
    throw new Error(result.payload.reason);
  }
}

// Usage
const fileInput = document.querySelector('input[type="file"]');
const file = fileInput.files[0];

try {
  const assetPath = await uploadAsset(file, 'effects/my-effect/icon.png');
  // Asset uploaded successfully
} catch (error) {
  // Handle error (validation failed, size exceeded, etc.)
  console.error('Upload failed:', error.message);
}
```
