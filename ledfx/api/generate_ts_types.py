import logging
import traceback

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
            error_body = f"// Generation Error!\n// {type(e).__name__}: {e}\n// Traceback:\n"
            error_body += "\n".join(
                [f"// {line}" for line in traceback.format_exc().splitlines()]
            )
            return web.Response(
                text=error_body, content_type="text/plain", status=500
            )
