# API v2 reference

LedFx serves a typed REST API under `/api/v2`, next to the v1 API described
in the other pages of this section. v1 keeps working, and new work goes into v2.

- A running LedFx serves the contract, an OpenAPI 3.1 document, at
  `/api/v2/openapi.json`, and this reference at `/api/v2/docs` (for example
  <http://localhost:8888/api/v2/docs>).
- The repository keeps the same document at `openapi/ledfx-v2.json`, and the
  reference below renders that copy. Its `info.version` is the contract
  version, not the LedFx release, and changes only when the API does (minor
  for additions, major for a break).
- Requests are strict, and responses may gain fields: ignore response fields
  you do not know.
- Errors are RFC 9457 problems (`application/problem+json`) with a stable
  `type` such as `urn:ledfx:problem:not-found`.

<iframe src="_static/api-v2/index.html" title="LedFx API v2 reference"
        style="width: 100%; height: 80vh; border: 0;"></iframe>
