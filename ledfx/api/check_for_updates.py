import logging
import os

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.utils import UpdateChecker

_LOGGER = logging.getLogger(__name__)


class CheckLedFxUpdatesEndPoint(RestEndpoint):
    ENDPOINT_PATH = "/api/check_for_updates"

    async def get(self) -> web.Response:
        """
        Handle GET request for update check.

        Returns:
            web.Response: The response containing update information.
        """
        is_release = os.getenv("IS_RELEASE", "false").lower()
        if is_release == "false":
            return await self.request_success(
                type="info",
                message="This instance of LedFx is not an official release - happy developing!",
            )
        _LOGGER.info("Checking for updates...")
        if UpdateChecker.get_release_information():
            latest_version = UpdateChecker.get_latest_version()
            release_age = UpdateChecker.get_release_age()
            release_url = UpdateChecker.get_release_url()
            if UpdateChecker.update_available():
                msg = "New LedFx version is available"
                _LOGGER.warning(f"{msg}.")
                return await self.request_success(
                    type="warning",
                    message=msg,
                    data={
                        "latest_version": latest_version,
                        "release_age": release_age,
                        "release_url": release_url,
                    },
                )
            else:
                msg = "LedFx is up to date"
                _LOGGER.info(f"{msg}.")

                return await self.request_success(type="success", message=msg)
        else:
            msg = "Unable to check for updates"
            _LOGGER.warning(f"{msg}.")
            return await self.request_success(type="info", message=msg)
