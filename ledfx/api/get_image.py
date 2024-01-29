import io
import logging
from json import JSONDecodeError

import pybase64
from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.utils import open_image

_LOGGER = logging.getLogger(__name__)


class GetImageEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/get_image"

    async def post(self, request: web.Request) -> web.Response:
        """Open image and return as base64 encoded string

        Args:
            request (web.Request): The request object containing the `path_url` to open.

        Returns:
            web.Response: The HTTP response object containing the base64 encoded image.
        """
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        path_url = data.get("path_url")

        if path_url is None:
            return await self.invalid_request(
                'Required attribute "path_url" was not provided'
            )

        image = open_image(path_url)

        if not image:
            return await self.invalid_request(
                f"Failed to open image from: {path_url}"
            )

        with io.BytesIO() as output:
            # we don't care about a bit of loss, so encode to JPEG
            # in example test 5x+ data saving 600kb - > 112 kb
            image.convert("RGB").save(
                output, format="JPEG"
            )  # Convert frame to JPEG
            encoded_frame = pybase64.b64encode(output.getvalue()).decode(
                "utf-8"
            )

        response = {"status": "success", "image": encoded_frame}

        return await self.bare_request_success(response)
