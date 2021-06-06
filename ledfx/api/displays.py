import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config
from ledfx.utils import generate_id

_LOGGER = logging.getLogger(__name__)


class DisplaysEndpoint(RestEndpoint):
    """REST end-point for querying and managing displays"""

    ENDPOINT_PATH = "/api/displays"

    async def get(self) -> web.Response:
        """
        Get info of all displays
        """
        response = {"status": "success", "displays": {}}
        response["paused"] = self._ledfx.displays._paused
        for display in self._ledfx.displays.values():
            response["displays"][display.id] = {
                "config": display.config,
                "id": display.id,
                "is_device": display.is_device,
                "segments": display.segments,
                "pixel_count": display.pixel_count,
                "active": display.active,
                "effect": {},
            }
            if display.active_effect:
                effect_response = {}
                effect_response["config"] = display.active_effect.config
                effect_response["name"] = display.active_effect.name
                effect_response["type"] = display.active_effect.type
                response["displays"][display.id]["effect"] = effect_response

        return web.json_response(data=response, status=200)

    async def put(self) -> web.Response:
        """
        Toggle "paused" state of all displays
        """
        self._ledfx.displays.pause_all()

        response = {
            "status": "success",
            "paused": self._ledfx.displays._paused,
        }

        return web.json_response(data=response, status=200)

    async def post(self, request) -> web.Response:
        """
        Create a new display or update config of an existing one
        """
        try:
            data = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=400)

        display_config = data.get("config")
        if display_config is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "config" was not provided',
            }
            return web.json_response(data=response, status=400)

        display_id = data.get("id")

        # Update display config if id exists
        if display_id is not None:
            display = self._ledfx.displays.get(display_id)
            if display is None:
                response = {
                    "status": "failed",
                    "reason": f"Display with ID {display_id} not found",
                }
                return web.json_response(data=response, status=404)
            # Update the display's configuration
            display.config = display_config
            _LOGGER.info(
                f"Updated display {display.id} config to {display_config}"
            )
            # Update ledfx's config
            for idx, item in enumerate(self._ledfx.config["displays"]):
                if item["id"] == display.id:
                    item["config"] = display.config
                    self._ledfx.config["displays"][idx] = item
                    break
        # Or, create new display if id does not exist
        else:
            display_id = generate_id(display_config.get("name"))

            # Create the display
            _LOGGER.info(f"Creating display with config {display_config}")

            display = self._ledfx.displays.create(
                id=display_id,
                is_device=False,
                config=display_config,
                ledfx=self._ledfx,
            )

            # Update the configuration
            self._ledfx.config["displays"].append(
                {
                    "id": display.id,
                    "config": display.config,
                    "is_device": display.is_device,
                }
            )

        # Save config
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        response = {
            "status": "success",
            "display": {
                "config": display.config,
                "id": display.id,
                "is_device": display.is_device,
            },
        }
        return web.json_response(data=response, status=200)
