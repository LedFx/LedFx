"""The API describing itself: the OpenAPI document and its offline docs page."""

from pathlib import Path

from aiohttp import hdrs, web

from ledfx.api.v2.core.app import OPENAPI_DIGEST_KEY, OPENAPI_JSON_KEY, V2_PREFIX
from ledfx.api.v2.core.problem import ProblemError
from ledfx.api.v2.core.router import Binary, Router

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
CSP = (
    "default-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
    "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)
NOSNIFF = {"X-Content-Type-Options": "nosniff"}

router = Router(tag="meta")


def _bundled(name: str) -> Path:
    """A docs file, or a Problem. FileResponse stats its file after the error
    middleware has returned, so a missing file would be an empty 404."""
    path = DOCS_DIR / name
    if not path.is_file():
        raise ProblemError(
            500, "internal", "Internal error", "the API reference is not installed"
        )
    return path


@router.get(
    "/openapi.json",
    responses={200: Binary("application/json"), 304: Binary("application/json")},
)
async def get_openapi(request: web.Request) -> web.Response:
    """The OpenAPI 3.1 document for this API.

    The ETag is the sha256 of the body. Send it back in If-None-Match to get
    a 304 while the API is unchanged.
    """
    body = request.app[OPENAPI_JSON_KEY]
    digest = request.app[OPENAPI_DIGEST_KEY]
    # RFC 9110 13.1.2: "*" matches any current representation.
    if any(tag.value in (digest, "*") for tag in request.if_none_match or ()):
        response = web.Response(status=304)
    else:
        response = web.Response(body=body, content_type="application/json")
    response.etag = digest
    return response


# The page and its bundle are served, not part of the contract: renaming them
# is not an API break, so they stay out of the OpenAPI document.
@router.get(
    "/docs",
    responses={200: Binary("text/html"), 304: Binary("text/html")},
    in_schema=False,
)
async def get_docs() -> web.FileResponse:
    """The interactive API reference (Scalar), served without outside requests."""
    return web.FileResponse(
        _bundled("docs.html"),
        headers={
            hdrs.CONTENT_TYPE: "text/html; charset=utf-8",
            hdrs.CACHE_CONTROL: "no-cache",  # the ETag makes revalidating cheap
            "Content-Security-Policy": CSP,
            **NOSNIFF,
        },
    )


@router.get(
    "/docs/scalar.standalone.js",
    responses={200: Binary("text/javascript"), 304: Binary("text/javascript")},
    in_schema=False,
)
async def get_docs_script() -> web.FileResponse:
    """The vendored Scalar bundle the docs page loads."""
    return web.FileResponse(
        _bundled("scalar.standalone.js"),
        headers={
            hdrs.CONTENT_TYPE: "text/javascript; charset=utf-8",
            hdrs.CACHE_CONTROL: "public, max-age=31536000, immutable",
            **NOSNIFF,
        },
    )


@router.get("/docs/", status=308, responses={308: Binary("text/html")}, in_schema=False)
async def get_docs_slash() -> web.StreamResponse:
    """The page's relative URLs only work without the trailing slash."""
    return web.HTTPPermanentRedirect(V2_PREFIX + "/docs")
