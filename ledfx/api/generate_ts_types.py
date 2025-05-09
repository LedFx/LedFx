import logging

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.tools.ts_generator import generate_typescript_types

_LOGGER = logging.getLogger(__name__)


class GenerateTypesEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/generate_ts_types"

    async def get(self) -> web.Response:

        _LOGGER.info("Received request to generate TypeScript types.")

        try:
            ts_code = generate_typescript_types()

            headers = {
                "Content-Disposition": 'attachment; filename="ledfx.types.ts"'
            }
            _LOGGER.info(
                "TypeScript generation processing successful. Returning code."
            )
            return web.Response(
                text=ts_code,
                content_type="application/typescript",
                charset="utf-8",
                headers=headers,
            )

        except Exception as e:
            _LOGGER.exception(
                "CRITICAL Error occurred during TypeScript generation via API."
            )
            return web.Response(
                text="An internal error occurred while generating TypeScript types. Please contact the administrator.",
                content_type="text/plain",
                status=500,
            )
