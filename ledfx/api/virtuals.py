import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config
from ledfx.utils import generate_id

_LOGGER = logging.getLogger(__name__)


class VirtualsEndpoint(RestEndpoint):
    """REST end-point for querying and managing virtuals"""

    ENDPOINT_PATH = "/api/virtuals"

    async def get(self) -> web.Response:
        """
        Get info of all virtuals
        """
        response = {"status": "success", "virtuals": {}}
        response["paused"] = self._ledfx.virtuals._paused
        for virtual in self._ledfx.virtuals.values():
            response["virtuals"][virtual.id] = {
                "config": virtual.config,
                "id": virtual.id,
                "is_device": virtual.is_device,
                "auto_generated": virtual.auto_generated,
                "segments": virtual.segments,
                "pixel_count": virtual.pixel_count,
                "active": virtual.active,
                "effect": {},
            }
            if virtual.active_effect:
                effect_response = {}
                effect_response["config"] = virtual.active_effect.config
                effect_response["name"] = virtual.active_effect.name
                effect_response["type"] = virtual.active_effect.type
                response["virtuals"][virtual.id]["effect"] = effect_response

        return web.json_response(data=response, status=200)

    async def put(self) -> web.Response:
        """
        Toggle "paused" state of all virtuals
        """
        self._ledfx.virtuals.pause_all()

        response = {
            "status": "success",
            "paused": self._ledfx.virtuals._paused,
        }

        return web.json_response(data=response, status=200)

    async def post(self, request) -> web.Response:
        """
        Create a new virtual or update config of an existing one
        """
        try:
            data = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=400)

        virtual_config = data.get("config")
        if virtual_config is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "config" was not provided',
            }
            return web.json_response(data=response, status=400)

        virtual_id = data.get("id")

        # Update virtual config if id exists
        if virtual_id is not None:
            virtual = self._ledfx.virtuals.get(virtual_id)
            if virtual is None:
                response = {
                    "status": "failed",
                    "reason": f"Virtual with ID {virtual_id} not found",
                }
                return web.json_response(data=response, status=404)
            # Update the virtual's configuration
            virtual.config = virtual_config
            _LOGGER.info(
                f"Updated virtual {virtual.id} config to {virtual_config}"
            )
            # Update ledfx's config
            for idx, item in enumerate(self._ledfx.config["virtuals"]):
                if item["id"] == virtual.id:
                    item["config"] = virtual.config
                    self._ledfx.config["virtuals"][idx] = item
                    break
            response = {
                "status": "success",
                "payload": {
                    "type": "success",
                    "reason": f"Updated Virtual {virtual.id}",
                },
                "virtual": {
                    "config": virtual.config,
                    "id": virtual.id,
                    "is_device": virtual.is_device,
                    "auto_generated": virtual.auto_generated,
                },
            }
        # Or, create new virtual if id does not exist
        else:
            virtual_id = generate_id(virtual_config.get("name"))

            # Create the virtual
            _LOGGER.info(f"Creating virtual with config {virtual_config}")

            virtual = self._ledfx.virtuals.create(
                id=virtual_id,
                is_device=False,
                config=virtual_config,
                ledfx=self._ledfx,
            )

            # Update the configuration
            self._ledfx.config["virtuals"].append(
                {
                    "id": virtual.id,
                    "config": virtual.config,
                    "is_device": virtual.is_device,
                    "auto_generated": virtual.auto_generated,
                }
            )

            response = {
                "status": "success",
                "payload": {
                    "type": "success",
                    "reason": f"Created Virtual {virtual_id}",
                },
                "virtual": {
                    "config": virtual.config,
                    "id": virtual.id,
                    "is_device": virtual.is_device,
                    "auto_generated": virtual.auto_generated,
                },
            }

        # Save config
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        return web.json_response(data=response, status=200)
