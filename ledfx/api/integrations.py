import copy
import logging
from json import JSONDecodeError

from aiohttp import web
from pydantic import ValidationError

from ledfx.api import RestEndpoint
from ledfx.configuration.models import IntegrationEntry

# from ledfx.api.websocket import WebsocketConnection
from ledfx.utils import generate_id

_LOGGER = logging.getLogger(__name__)


class IntegrationsEndpoint(RestEndpoint):
    """REST end-point for querying and managing integrations"""

    ENDPOINT_PATH = "/api/integrations"

    async def get(self, request=None) -> web.Response:
        """
        Get info of all integrations.

        Returns:
            web.Response: The response containing the info of all integrations. Optionally filtered by info attribute passed in the request body.
        """
        response = {"status": "success", "integrations": {}}
        for integration in self._ledfx.integrations.values():
            response["integrations"][integration.id] = {
                "id": integration.id,
                "type": integration.type,
                "active": integration.active,
                "status": integration.status,
                "beta": integration.beta,
                "data": integration.data,
                "config": integration.config,
            }

        if request.body_exists:
            try:
                data = await request.json()
            except JSONDecodeError:
                return await self.json_decode_error()
            info = data.get("info")
            for integration in self._ledfx.integrations.values():
                if info not in response["integrations"][integration.id]:
                    return await self.invalid_request(
                        f"info attribute {info} not found"
                    )
                response["integrations"][integration.id] = {
                    info: response["integrations"][integration.id][info]
                }
        return await self.bare_request_success(response)

    async def put(self, request: web.Request) -> web.Response:
        """Toggle an integration on or off.

        Args:
            request (web.Request): The request object with the integration `id` to toggle.

        Returns:
            A web.Response object.
        """
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()
        integration_id = data.get("id")
        if integration_id is None:
            return await self.invalid_request(
                "Required attribute 'id' was not provided"
            )

        integration = self._ledfx.integrations.get(integration_id)

        if integration is None:
            return await self.invalid_request(
                "Required attribute 'integration_id' was not provided"
            )

        # Toggle the integration
        active = integration.active

        if not active:
            await integration.activate()
        else:
            await integration.deactivate()

        # Update and save the configuration
        for _integration in self._ledfx.config.integrations:
            if _integration.id == integration.id:
                _integration.active = not active
                break
        self._ledfx.config_store.request_save()
        return await self.request_success()

    async def delete(self, request: web.Request) -> web.Response:
        """
        Delete an integration, erasing all its configuration
        NOTE: THIS DOES NOT TURN OFF THE INTEGRATION, IT DELETES IT!
        USE PUT TO TOGGLE!

        Args:
            request (web.Request): The request object containing the integration `id` to be deleted.

        Returns:
            A web.Response indicating the success or failure of the deletion.
        """
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()
        integration_id = data.get("id")
        if integration_id is None:
            return await self.invalid_request(
                "Required attribute 'id' was not provided"
            )

        integration = self._ledfx.integrations.get(integration_id)
        if integration is None:
            return await self.invalid_request(
                "Required attribute 'integration_id' was not provided"
            )

        if hasattr(integration, "on_delete"):
            await integration.on_delete()

        self._ledfx.integrations.destroy(integration_id)

        self._ledfx.config.integrations = [
            integration
            for integration in self._ledfx.config.integrations
            if integration.id != integration_id
        ]

        # Save the config
        self._ledfx.config_store.request_save()
        return await self.request_success()

    async def post(self, request: web.Request) -> web.Response:
        """Create a new integration, or update an existing one"""
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        integration_config = data.get("config")

        if integration_config is None:
            return await self.invalid_request(
                'Required attribute "config" was not provided'
            )

        integration_type = data.get("type")
        if integration_type is None:
            return await self.invalid_request(
                'Required attribute "type" was not provided'
            )
        # Validate before an update destroys the running integration.
        try:
            integration_class = self._ledfx.integrations.get_class(integration_type)
        except KeyError:
            return await self.invalid_request(
                f"Unknown integration type: {integration_type}"
            )
        try:
            integration_config = (
                integration_class.config_model()
                .model_validate(integration_config)
                .as_dict()
            )
        except ValidationError as err:
            return await self.validation_error(err)

        # Allow for id be None for new integrations
        integration_id = data.get("id")

        new = not bool(integration_id)
        if integration_id is None:
            # Create new integration if no id is given
            integration_id = generate_id(integration_config.get("name"))
            _LOGGER.info(
                "Creating %s integration",
                integration_type,
            )
        else:
            # Update existing integration if valid id is given
            existing_integration = self._ledfx.integrations.get(integration_id)

            if existing_integration is None:
                return await self.invalid_request(
                    f"Integration with id {integration_id} not found"
                )

            _LOGGER.info(
                "Updating %s integration '%s'",
                integration_type,
                integration_id,
            )

            self._ledfx.integrations.destroy(integration_id)

        # An update keeps the stored data (QLC events, Spotify triggers).
        stored = next(
            (e for e in self._ledfx.config.integrations if e.id == integration_id),
            None,
        )
        integration = self._ledfx.integrations.create(
            id=integration_id,
            type=integration_type,
            active=False,
            config=integration_config,
            data=None if new or stored is None else copy.deepcopy(stored.data),
            ledfx=self._ledfx,
        )

        # Update and save the configuration
        if new:
            entry = {
                "id": integration.id,
                "type": integration.type,
                "active": integration.active,
                "config": integration.config.as_dict(),
            }
            if integration.stored_data is not None:
                entry["data"] = integration.stored_data
            self._ledfx.config.integrations.append(
                IntegrationEntry.model_validate(entry)
            )
        else:
            for integration in self._ledfx.config.integrations:
                if integration.id == integration_id:
                    integration.config = integration_config
                    break
                    # Update and save the configuration

        self._ledfx.config_store.request_save()
        return await self.request_success()
