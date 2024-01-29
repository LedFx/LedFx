import io
import logging
from json import JSONDecodeError

import PIL.ImageSequence as ImageSequence
import pybase64
from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.utils import open_gif

_LOGGER = logging.getLogger(__name__)


class GetGifFramesEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/get_gif_frames"

    async def post(self, request: web.Request) -> web.Response:
        """Open GIF resource and return frames

        Args:
            request (web.Request): The request object containing the `path_url` to open.

        Returns:
            web.Response: The HTTP response object containing the frames of the GIF.
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

        gif_image = open_gif(path_url)

        if not gif_image:
            return await self.invalid_request(
                f"Failed to open GIF image from: {path_url}"
            )

        frames = []
        for frame in ImageSequence.Iterator(gif_image):
            with io.BytesIO() as output:
                # we don't care about a bit of loss, so encode to JPEG
                # in example test 5x+ data saving 600kb - > 112 kb
                frame.convert("RGB").save(
                    output, format="JPEG"
                )  # Convert frame to JPEG
                encoded_frame = pybase64.b64encode(output.getvalue()).decode(
                    "utf-8"
                )
                frames.append(encoded_frame)

        response = {
            "status": "success",
            "frame_count": len(frames),
            "frames": frames,
        }

        return await self.bare_request_success(response)
