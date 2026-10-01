"""GET /api/schemas/{kind}: one exported JSON Schema kind."""

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.api.schemas import build_schemas


class SchemasKindEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/schemas/{kind}"

    async def get(self, request: web.Request) -> web.Response:
        schemas = build_schemas(self._ledfx)
        kind = request.match_info["kind"]
        if kind not in schemas:
            return await self.invalid_request(f"Unknown schema kind: {kind}")
        return web.json_response(data={kind: schemas[kind]}, status=200)
