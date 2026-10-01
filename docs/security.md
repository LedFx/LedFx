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

#### 5) Browser Requests Are Checked by Origin

Browsers add an `Origin` header naming the site a request comes from. LedFx uses it to decide which web pages may drive the API. It applies to `POST`, `PUT`, `PATCH` and `DELETE` requests, to every WebSocket connection (`/api/websocket`, `/api/log`), and to the `GET` routes that change state or reach out to other hosts: `/api/find_devices`, `/api/find_lifx`, `/api/virtuals/{virtual_id}/fallback`, `/api/sendspin/discover`, `/api/find_openrgb` and `/api/ping/{device_id}`. These are accepted when:

| Origin | Accepted |
|---|---|
| No `Origin` header (scripts, `curl`, Home Assistant integrations, Node-RED) | yes |
| The LedFx server itself (same host and port, `http` or `https`) | yes |
| A local host, any port: `localhost`, a loopback, private (`10.x`, `172.16-31.x`, `192.168.x`), CGNAT (`100.64.x`) or link-local IP address, an IPv6 loopback, unique-local (`fd..`) or link-local (`fe80::`) address, a name without dots (`raspberrypi`), or a name ending in `.local`, `.localhost`, `.home.arpa`, `.internal`, `.lan`, `.home`, `.localdomain` or `.fritz.box` | yes |
| The hosted LedFx frontends `https://ledfx.stream` and `https://yeonv.github.io` | yes |
| `file://` (the LedFx desktop client) | yes |
| Listed in `allowed_origins` | yes |
| `null` | only when `allow_null_origin` is `true` |
| Anything else | no: `403` with `Origin not allowed: <origin>` |

Browsers send no `Origin` when an image, link or form on another site requests one of those `GET` routes; such requests (`Sec-Fetch-Site: cross-site` or `same-site` without `Sec-Fetch-Mode: cors`) are refused too. Other `GET` requests are always served. The API sends CORS headers (`Access-Control-Allow-Origin`) only to accepted origins, so other web pages cannot read the responses. CORS responses never allow credentials; LedFx does not use cookies or HTTP authentication.

**Allowing another origin.** Add the exact origin, scheme and host plus the port when it is not the default, to `allowed_origins` in the core config, for example:

```json
{
    "allowed_origins": ["https://ledfx.example.com", "http://dashboard.example.net:8080"]
}
```

or send it with `PUT /api/config`. Changes apply to the next request; no restart is needed. You need this for:

- a reverse proxy that rewrites the `Host` header (the page origin then no longer matches the host LedFx sees), or a public DNS name that points at LedFx from another host,
- LAN names under other domains (for example `ledfx.example.net`) when one LedFx UI controls another LedFx,
- a third-party web dashboard.

`"*"` accepts every origin and restores the behaviour of earlier releases. Home Assistant ingress needs no `allowed_origins` entry: Home Assistant forwards the browser's `Host` header, so the UI counts as the same origin (see `allowed_hosts` below for remote access).

`allow_null_origin` accepts pages whose origin is `null`: files opened directly in a browser and sandboxed frames. Sandboxed frames can be embedded by any website, so leave it off unless a client needs it.

#### 6) Clients Must Use a Known Host Name

A web page served from a name that the page's owner controls can make that name resolve to LedFx's address, and its requests then look like they come from LedFx itself. Over plain HTTP such a page's reads carry no browser headers, so LedFx cannot tell them from a script. To prevent this, every request must address LedFx by a name it knows. The `Host` header may be:

- any IP address (IPv4 or IPv6),
- `localhost`, a name without dots (`raspberrypi`), or a name ending in `.local`, `.localhost`, `.home.arpa`, `.internal`, `.lan`, `.home`, `.localdomain` or `.fritz.box`,
- this machine's host name (as reported by the operating system, short and fully qualified),
- the `host` LedFx is configured to listen on,
- a name listed in `allowed_hosts`.

Other names get `403` with `Host not allowed: <name>. Add it to allowed_hosts in the LedFx config.` This applies to scripts, `curl`, Home Assistant integrations and Node-RED as well: if one reaches LedFx through a DNS name that is not local, add that name.

Add the host names you use to reach LedFx, without scheme or port:

```json
{
    "allowed_hosts": ["ledfx.example.com"]
}
```

or send them with `PUT /api/config`; changes apply to the next request. `"*"` turns the check off. Typical cases:

- a reverse proxy or DNS name such as `ledfx.example.com`, whether opened in a browser or set in an integration,
- Home Assistant ingress opened through a remote address: Nabu Casa (`xxxx.ui.nabu.casa`) or your own domain. Ingress through `homeassistant.local` or the Home Assistant IP address needs nothing. Open LedFx once through the local address (or edit `config.json` in the add-on's config folder) to add the remote name.

A name in `allowed_hosts` also counts as LedFx's own origin, so a page opened through it needs no `allowed_origins` entry.

### User Impact (What Users May Notice)

- If you previously called image/GIF helper APIs with an absolute local path (like `/home/user/...` or `C:\...`) and that path is not inside LedFx's allowed directories, it will now be rejected. This is intentional, because the older behavior could be used for arbitrary file access.
- If you previously used "creative" URLs (non-http schemes, odd encodings, etc.), those may now be rejected as unsafe.
- A browser page served from an origin that is not listed above can no longer change settings or open the WebSocket. Add its origin to `allowed_origins`.
- Reaching LedFx through a DNS name that is not local (for example `ledfx.example.com`), from a browser or from an integration, returns `Host not allowed`. Add the name to `allowed_hosts`. IP addresses and local names keep working.
- The recommended pattern is: put user-provided media into LedFx's managed asset location and use the assets workflow and reference it through the API in the supported way, rather than pointing LedFx at arbitrary places on disk.

## What was I supposed to do now?

see [Assets Workflow](settings/asset_workflow.md)

