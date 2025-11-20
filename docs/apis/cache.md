# Image Cache API

## Overview

LedFx provides API endpoints for managing cached images from remote URLs. The cache implements a "cache and keep" policy with explicit control.

## Cache Policy

- **No automatic expiration**: Images cached indefinitely
- **No TTL**: No time-based refresh
- **LRU eviction**: Least Recently Used items evicted when cache limits exceeded
- **Explicit control**: Refresh/clear only via API calls
- **Access tracking**: Updates `last_accessed` and `access_count` on every cache hit

## Cache Limits

- **Default max size**: 500MB (configurable in `config.json`)
- **Default max items**: 500 images (configurable in `config.json`)
- **Eviction strategy**: LRU (Least Recently Used)

## Configuration

Add to `config.json`:

```json
{
  "image_cache": {
    "enabled": true,
    "max_size_mb": 500,
    "max_items": 500
  }
}
```

## API Endpoints

### Get Cache Statistics

Get current cache statistics including all cached entries.

**Endpoint:** `GET /api/cache/images`

**Response:**
```json
{
  "total_size": 52428800,
  "total_count": 45,
  "max_size": 524288000,
  "max_count": 500,
  "cache_policy": {
    "expiration": "none",
    "refresh": "explicit only",
    "eviction": "LRU when limits exceeded"
  },
  "entries": [
    {
      "url": "https://example.com/image.gif",
      "cached_at": "2024-01-15T10:30:00Z",
      "last_accessed": "2024-01-20T14:20:00Z",
      "access_count": 42,
      "file_size": 524288,
      "content_type": "image/gif"
    }
  ]
}
```

**Entries sorted by:** `access_count` (descending) - most frequently used first

---

### Clear Cache

Clear specific URL from cache or clear entire cache.

**Endpoint:** `DELETE /api/cache/images`

**Query Parameters:**
- `url` (optional): Specific URL to clear

**Examples:**

Clear specific URL:
```
DELETE /api/cache/images?url=https://example.com/image.gif
```

Clear entire cache:
```
DELETE /api/cache/images
```

**Response:**
```json
{
  "status": "success",
  "message": "Entire cache cleared",
  "cleared_count": 45,
  "freed_bytes": 52428800
}
```

---

### Refresh Image

Explicitly refresh a cached image by forcing re-download on next access.

**Endpoint:** `POST /api/cache/images/refresh`

**Request Body:**
```json
{
  "url": "https://example.com/image.gif",
  "force": false
}
```

**Parameters:**
- `url` (required): The URL to refresh
- `force` (optional, default false): If true, force download; if false, use conditional request (future feature)

**Response:**
```json
{
  "status": "success",
  "message": "Cache entry cleared. Image will be re-downloaded on next access.",
  "url": "https://example.com/image.gif",
  "force": false
}
```

---

## Image Request Endpoints

The following endpoints use the cache automatically:

### Get Image

**Endpoint:** `GET /api/get_image`

**Behavior:**
- First request: Downloads image and caches it
- Subsequent requests: Returns cached version
- No automatic expiration

### Get GIF Frames

**Endpoint:** `GET /api/get_gif_frames`

**Behavior:**
- First request: Downloads GIF and caches it
- Subsequent requests: Extracts frames from cached version
- No automatic expiration

---

## Cache Workflow

### First Access
1. User requests image via `/api/get_image?path=https://example.com/image.gif`
2. Image not in cache → download from URL
3. Validate file type (extension, MIME, PIL format)
4. Validate size (max 10MB, max 4096×4096 pixels)
5. Store in cache with metadata
6. Return image to user

### Subsequent Access
1. User requests same image
2. Image found in cache → validate cached file
3. If valid: return immediately
4. If corrupted/invalid: delete corrupt entry, re-download, cache fresh copy
5. Update `last_accessed` timestamp
6. Increment `access_count`
7. No expiration check

### Cache Error Handling
1. Cached file corrupted or unreadable
2. Log warning: "Error reading cached image, re-downloading"
3. Delete corrupt cache entry
4. Download fresh copy from original URL
5. Validate and cache new download
6. Return fresh image to user

This ensures the cache is **self-healing** - corruption doesn't break functionality.

### Cache Full (LRU Eviction)
1. New image exceeds cache limits
2. Find least recently accessed item (lowest `last_accessed`)
3. Tiebreaker: lowest `access_count`
4. Evict LRU item
5. Store new image

### Explicit Refresh
1. User calls `POST /api/cache/images/refresh` with URL
2. Cache entry deleted
3. Next access re-downloads from origin
4. New version cached with fresh metadata

---

## Use Cases

### View Most Used Images
```bash
curl http://localhost:8888/api/cache/images
```

Shows which images are accessed most frequently, sorted by `access_count`.

### Clear Old Unused Image
```bash
curl -X DELETE "http://localhost:8888/api/cache/images?url=https://old-domain.com/unused.gif"
```

### Force Refresh Stale Image
```bash
curl -X POST http://localhost:8888/api/cache/images/refresh \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/updated.gif", "force": true}'
```

### Clear Entire Cache (Fresh Start)
```bash
curl -X DELETE http://localhost:8888/api/cache/images
```

---

## Benefits

- **Performance**: Instant access to frequently used images
- **Bandwidth**: No redundant downloads
- **Reliability**: Works offline once cached
- **Control**: Manual management of cache contents
- **Persistence**: Cache survives LedFx restarts
