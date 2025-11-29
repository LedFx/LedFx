# Assets API

The Assets API provides secure management of image assets stored in the LedFx configuration directory. Assets are stored under `.ledfx/assets/` with full path traversal protection and content validation.

## Overview

Assets are image files that can be uploaded, retrieved, listed, and deleted through the REST API. All operations enforce strict security controls including:

- Path traversal prevention
- File extension validation (images only)
- Content validation (actual image data required)
- Size limits (2MB default)
- Automatic directory cleanup

## Supported Image Formats

- PNG (`.png`)
- JPEG (`.jpg`, `.jpeg`)
- GIF (`.gif`)
- WebP (`.webp`)
- BMP (`.bmp`)
- TIFF (`.tiff`, `.tif`)
- ICO (`.ico`)

## Endpoints

### List Assets

```
GET /api/assets
```

Returns a list of all available assets.

**Response:**
```json
{
  "assets": [
    "icon.png",
    "backgrounds/galaxy.jpg",
    "effects/fire/texture.webp"
  ]
}
```

**Status Codes:**
- `200 OK` - Success

---

### Upload Asset

```
POST /api/assets
```

Upload a new image asset. Requires `multipart/form-data` encoding.

**Request Parameters:**
- `file` (file) - The image file to upload
- `path` (string) - Relative path where asset should be stored (e.g., `icons/led.png`)

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

**Status Codes:**
- `200 OK` - Success or validation error (check `status` field)

**Validation Rules:**
- File must be a valid image (content-verified)
- Extension must be in allowed list
- Path must not contain traversal sequences (`..`, absolute paths, etc.)
- File size must not exceed 2MB
- Overwriting existing files is rejected by default

---

### Download Asset

```
GET /api/assets?path={asset_path}
```

Retrieve a specific asset file.

**Query Parameters:**
- `path` (string) - Relative path to the asset (e.g., `icons/led.png`)

**Response:**
- Binary image data with appropriate `Content-Type` header

**Status Codes:**
- `200 OK` - Asset found and returned
- `404 Not Found` - Asset does not exist

**Example:**
```javascript
// Download asset
fetch('/api/assets?path=icons/led.png')
  .then(response => response.blob())
  .then(blob => {
    const url = URL.createObjectURL(blob);
    // Use the image...
  });
```

---

### Delete Asset

```
DELETE /api/assets?path={asset_path}
```

Delete a specific asset and clean up empty directories.

**Query Parameters:**
- `path` (string) - Relative path to the asset to delete

**Success Response:**
```json
{
  "status": "success",
  "data": {
    "deleted": true
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

**Status Codes:**
- `200 OK` - Success or error (check `status` field)

---

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

When deleting assets, empty parent directories are automatically removed:

```
DELETE /api/assets?path=effects/fire/texture.png

Result:
- File deleted: effects/fire/texture.png
- Removed empty directory: effects/fire/
- Removed empty directory: effects/
```

## Use Cases

### Effect Icons

Store custom icons for effects:
```
POST /api/assets
  file: icon.png
  path: effects/rainbow/icon.png
```

### Background Images

Upload background images for visualizations:
```
POST /api/assets
  file: galaxy.jpg
  path: backgrounds/space/galaxy.jpg
```

### Texture Maps

Store texture maps for effects:
```
POST /api/assets
  file: fire.webp
  path: effects/fire/texture.webp
```

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

## Storage Location

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

## Best Practices

1. **Use descriptive paths** - Organize assets in folders: `effects/rainbow/icon.png`
2. **Optimize images** - Compress images before upload to stay under 2MB limit
3. **Check responses** - Always verify `status` field in JSON responses
4. **Handle errors gracefully** - Display error messages from `payload.reason` to users
5. **Clean up unused assets** - Delete assets that are no longer needed

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
