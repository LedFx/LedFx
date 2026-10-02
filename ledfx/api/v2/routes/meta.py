"""The API describing itself: the OpenAPI document."""

from aiohttp import web

from ledfx.api.v2.core.app import OPENAPI_DIGEST_KEY, OPENAPI_JSON_KEY
from ledfx.api.v2.core.router import Binary, Router

router = Router(tag="meta")


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
