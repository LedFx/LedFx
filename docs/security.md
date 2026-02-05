# Security

## TL;DR

Use [Assets Workflow](settings/asset_workflow.md) for graphical assets management.

LedFx previously allowed some endpoints to load media using either a URL or a local file path. While convenient, accepting arbitrary paths and URLs can lead to well-known security issues such as path traversal (reading files outside the intended directory) and SSRF (forcing the server to fetch unintended network resources).

We’ve tightened these APIs so LedFx can only access files from approved LedFx-managed directories, only process expected file types, and only fetch from sanitized, validated URLs (typically http/https), following OWASP guidance. The goal is to keep common “LAN app” deployments safe even when LedFx is proxied, integrated into other systems, or accidentally exposed.

### What it means to a user

If you previously had image assets on your local drive they will no longer be accessible.

- This could be for:
  - Matrix effects:
    - keybeat
    - gif player
    - image
  - Button images
    - Scenes
    - Playlists

They will have to be updated manually using the new asset manager workflow, that explicitly places assets in an assets folder under .Ledfx directory.

Please see the documentation at: [Assets Workflow](settings/asset_workflow.md)

It's a drag-and-drop experience and offers many advantages for the future, security being the critical need, but we also get ease of use, caching and thumbnail performance.

Unfortunately it's not possible for LedFx to automatically copy over your historical assets, such an implementation would only persist the security risk, and we must draw a line under that.

## Security details

### Why we had to add this security?...

LedFx exposes a local web UI and a set of REST/WebSocket APIs. A few of those APIs historically accepted either a URL or a local file path as input (for example, the image/GIF helper endpoints).
The new API docs explicitly describe the modified "URL or local file path" behavior in

- [Assets API](apis/assets.md)
- [Cache API](apis/cache.md)

That design is convenient, but it creates two common web-app risk patterns:

### Path traversal / arbitrary file read
If an endpoint accepts a user-provided file path, a malicious (or simply curious) client can try absolute paths or ../ tricks to reach files outside the intended folder (configs, keys, system files, source code, etc.). This is the classic Path Traversal issue.
[OWASP Foundation Path Traversal](https://owasp.org/www-community/attacks/Path_Traversal?utm_source=chatgpt.com)

### SSRF / dangerous URL schemes
If an endpoint fetches remote content from a user-provided URL, that can be abused to make LedFx fetch things it should never fetch (internal network services, router admin pages, cloud metadata endpoints, etc.). This is Server-Side Request Forgery (SSRF). OWASP specifically calls out sanitizing/validating client-supplied URLs and enforcing allow-lists.
[OWASP Foundation SSRF](https://owasp.org/Top10/2021/A10_2021-Server-Side_Request_Forgery_%28SSRF%29/?utm_source=chatgpt.com)

Even though LedFx is usually run on a trusted LAN, users may:

- Run LedFx headless,
- Put Ledfx behind reverse proxies,
- Integrate LedFx with Home Assistant,
- Accidentally expose ports.

So we’re now treating the API boundary as untrusted by default.


### What Changed

#### 1) File Access is Now Constrained ("No Arbitrary Paths")

When an API needs to read a local file (images, gifs, assets, etc.), LedFx now restricts access to approved directories (for example: LedFx-managed asset/cache/config locations) and blocks:

- Absolute paths outside the allowed roots
- Any `../` traversal attempts (including encoded variants)
- Other "escape the sandbox" path tricks

#### 2) File Types are Allow-Listed ("No Arbitrary File Types")

Endpoints that return or process files now only allow a small set of expected extensions/MIME types (e.g., image formats for image endpoints). Unknown/unexpected types are rejected rather than “best-effort” handled.

**Extension Validation:**
- **Local files**: Must have a valid image extension (`.png`, `.jpg`, `.gif`, `.webp`, etc.)
- **Remote URLs (http/https)**: May omit file extensions (e.g., CDN URLs like `https://cdn.example.com/image/abc123`)
  - Content is validated after download via Content-Type header and PIL format detection
  - URLs with explicit invalid extensions (`.txt`, `.pdf`, etc.) are still rejected
  - This allows API endpoints and CDN URLs that serve images without file extensions in the path

#### 3) URLs are Sanitized and Validated ("Safe URLs Only")

For endpoints that accept a URL:

- Only expected schemes are allowed (typically http/https)
- Malformed/ambiguous URLs are rejected
- URL handling follows the "validate + allow-list" approach recommended by OWASP to reduce SSRF risk

#### 4) Consistent, Predictable Failures

Instead of “trying to open whatever you gave me,” the API fails fast with a clear error when input is outside policy (wrong folder, wrong type, disallowed URL, etc.).

### User Impact (What Users May Notice)

- If you previously called image/GIF helper APIs with an absolute local path (like `/home/user/...` or `C:\...`) and that path is not inside LedFx's allowed directories, it will now be rejected. This is intentional, because the older behavior could be used for arbitrary file access.
- If you previously used "creative" URLs (non-http schemes, odd encodings, etc.), those may now be rejected as unsafe.
- The recommended pattern is: put user-provided media into LedFx's managed asset location and use the assets workflow and reference it through the API in the supported way, rather than pointing LedFx at arbitrary places on disk.

## What was I supposed to do now?

see [Assets Workflow](settings/asset_workflow.md)

