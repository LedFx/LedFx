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
    """
    REST end-point for requesting GIF frames from path_url in request data
    """

    ENDPOINT_PATH = "/api/get_gif_frames"

    async def get(self, request) -> web.Response:
        """Open GIF resource and return frames"""
        try:
            data = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=400)

        path_url = data.get("path_url")

        if path_url is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "path_urk" was not provided',
            }
            return web.json_response(data=response, status=400)

        _LOGGER.info(f"GetGifFramesEndpoint from {path_url}")

        gif_image = open_gif(path_url)

        if not gif_image:
            response = {
                "status": "failed",
                "reason": "Failed to open GIF image",
            }
            return web.json_response(data=response, status=404)

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

        response = {"frame_count": len(frames), "frames": frames}

        return web.json_response(data=response, status=200)
