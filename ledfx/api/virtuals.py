import logging
from json import JSONDecodeError

from aiohttp import web
from pydantic import ValidationError

from ledfx.api import RestEndpoint
from ledfx.api.jsonutil import dumps
from ledfx.api.virtual import make_virtual_response
from ledfx.configuration.fields import VirtualIdStr
from ledfx.configuration.models import VirtualConfig, replace_model
from ledfx.virtuals import repaired_frequency

_LOGGER = logging.getLogger(__name__)


class VirtualsEndpoint(RestEndpoint):
    """REST end-point for querying and managing virtuals"""

    ENDPOINT_PATH = "/api/virtuals"

    async def get(self) -> web.Response:
        """
        Get info of all virtuals

        Returns:
            web.Response: The response containing the info of all virtuals
        """
        virtuals: dict[str, object] = {}
        response: dict[str, object] = {"status": "success", "virtuals": virtuals}
        response["paused"] = self._ledfx.virtuals.paused
        for virtual in self._ledfx.virtuals.values():
            virtuals[virtual.id] = make_virtual_response(virtual)

        return web.json_response(data=response, status=200, dumps=dumps)

    async def put(self) -> web.Response:
        """
        Toggles a global pause on all virtuals

        Returns:
            web.Response: The response containing the paused virtuals.
        """
        virtuals = self._ledfx.virtuals
        paused = virtuals.set_paused(not virtuals.paused)
        return await self.bare_request_success({"status": "success", "paused": paused})

    async def post(self, request: web.Request) -> web.Response:
        """
        Create a new virtual or update config of an existing one

        Args:
            request (web.Request): The request object containing the virtual `config` dict.

        Returns:
            web.Response: The response indicating the success or failure of the creation.
        """
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        virtual_config = data.get("config")
        if virtual_config is None:
            return await self.invalid_request(
                'Required attribute "config" was not provided'
            )
        if not isinstance(virtual_config, dict):
            return await self.invalid_request('"config" must be an object')
        virtual_id = data.get("id")
        if virtual_id is not None and not isinstance(virtual_id, str):
            return await self.invalid_request('"id" must be a string')

        virtuals = self._ledfx.virtuals
        # Update virtual config if id exists
        if virtual_id is not None:
            virtual = virtuals.get(virtual_id)
            if virtual is None:
                return await self.invalid_request(
                    f"Virtual with ID {virtual_id} not found"
                )
            # The body holds only the keys to change.
            try:
                config = VirtualConfig.model_validate(
                    {**virtual.config.model_dump(), **virtual_config}
                )
            except ValidationError as err:
                return await self.validation_error(err)
            # v1-compat: the manager refuses a frequency range with min >= max
            # and a rotate on one row; v1 swapped, widened and zeroed them.
            config = repaired_frequency(config)
            if config.rows <= 1 and config.rotate != 0:
                config = replace_model(config, rotate=0)
            virtual = virtuals.set_config(VirtualIdStr(virtual_id), config)
            _LOGGER.info("Updated virtual %s config to %s", virtual.id, virtual_config)
            reason = f"Updated Virtual {virtual.name}"
        # Or, create new virtual if id does not exist
        else:
            # Validate first: the id is generated from the name.
            try:
                config = VirtualConfig.model_validate(virtual_config)
            except ValidationError as err:
                return await self.validation_error(err)
            _LOGGER.info("Creating virtual with config %s", virtual_config)
            # v1-compat: add refuses a frequency range with min >= max; v1
            # create swapped or widened it. (A rotate on one row is still
            # stored as sent: see Virtuals.add.)
            virtual = virtuals.add(repaired_frequency(config))
            reason = f"Created Virtual {virtual.id}"

        response = {
            "status": "success",
            "payload": {"type": "success", "reason": reason},
            "virtual": {
                "config": virtual.config,
                "id": virtual.id,
                "is_device": virtual.is_device,
                "auto_generated": virtual.auto_generated,
            },
        }
        return await self.bare_request_success(response)
