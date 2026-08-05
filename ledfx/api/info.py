import logging
import os
import sys

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.consts import PROJECT_VERSION
from ledfx.sendspin import SENDSPIN_AVAILABLE

# Platforms with a Now Playing provider. Elsewhere the switch would be an
# offer LedFx cannot keep, so clients can hide it instead.
_NOW_PLAYING_PLATFORMS = ("win32", "linux")

_LOGGER = logging.getLogger(__name__)


class InfoEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/info"

    async def get(self) -> web.Response:
        """
        Get information about the LedFx Controller.

        Returns:
            web.Response: The response containing the controller information.
        """
        response = {
            "url": self._ledfx.http.base_url,
            "name": "LedFx Controller",
            "version": PROJECT_VERSION,
            "github_sha": os.getenv("GITHUB_SHA", "unknown"),
            "is_release": os.getenv("IS_RELEASE", "false").lower(),
            "developer_mode": self._ledfx.config["dev_mode"],
            "features": {
                "sendspin": SENDSPIN_AVAILABLE,
                # Supported here, and opted into. Both matter: the switch is
                # only worth showing on a platform that has a provider, and
                # clients must not assume the feature is running.
                "now_playing": sys.platform in _NOW_PLAYING_PLATFORMS,
                "now_playing_enabled": bool(
                    self._ledfx.config.get("now_playing_enabled", False)
                ),
            },
        }
        return await self.bare_request_success(response)
