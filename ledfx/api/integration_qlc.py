import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config
from ledfx.events import Event

_LOGGER = logging.getLogger(__name__)


class QLCEndpoint(RestEndpoint):
    """REST end-point for querying and managing a QLC integration"""

    ENDPOINT_PATH = "/api/integrations/qlc/{integration_id}"

    async def get(self, integration_id) -> web.Response:
        """
        Get info from QLC+ integration.

        Args:
            integration_id (str): The ID of the QLC+ integration.

        Returns:
            web.Response: The response containing the QLC+ integration information.
        """
        if integration_id is None:
            return await self.invalid_request(
                'Required attribute "integration_id" was not provided'
            )
        integration = self._ledfx.integrations.get(integration_id)
        if (integration is None) or (integration.type != "qlc"):
            return await self.invalid_request(
                f"{integration} was not found or was not type qlc"
            )

        response = {}

        # generate dict of {effect_id: effect_name}
        effect_names = []
        for effect_type, effect in self._ledfx.effects.classes().items():
            effect_names.append(effect.NAME)

        scene_ids = []
        for scene in self._ledfx.config["scenes"]:
            scene_ids.append(self._ledfx.config["scenes"][scene]["name"])

        response["event_types"] = {
            Event.EFFECT_SET: {
                "event_name": "Effect Set",
                "event_filters": {"effect_name": effect_names},
            },
            Event.EFFECT_CLEARED: {
                "event_name": "Effect Cleared",
                "event_filters": {},
            },
            Event.SCENE_ACTIVATED: {
                "event_name": "Scene Set",
                "event_filters": {"scene_id": scene_ids},
            },
        }

        response["qlc_widgets"] = await integration.get_widgets()

        response["qlc_listeners"] = integration.data
        return await self.request_success(response)

    async def put(self, integration_id, request) -> web.Response:
        """Toggle a QLC event listener

        Args:
            integration_id (str): The ID of the integration.
            request (web.Request): The request object containing `event_type` and `event_filter`.

        Returns:
            web.Response: The response object.

        Raises:
            JSONDecodeError: If there is an error decoding the JSON data.
        """
        integration = self._ledfx.integrations.get(integration_id)
        if (integration is None) or (integration.type != "qlc"):
            return await self.invalid_request(
                f"{integration} was not found or was not type qlc"
            )

        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()
        event_type = data.get("event_type")
        event_filter = data.get("event_filter")

        missing_attributes = []
        if event_type is None:
            missing_attributes.append("event_type")
        if event_filter is None:
            missing_attributes.append("event_filter")
        if missing_attributes:
            return await self.invalid_request(
                f'Required attributes {", ".join(missing_attributes)} were not provided'
            )

        if type(event_filter) is not dict:
            return await self.invalid_request(
                f'Invalid filter "{event_filter}", should be dictionary eg. {{ "scene_id" : "my scene" }} '
            )

        # toggle the event listener
        if not integration.toggle_event(event_type, event_filter):
            return await self.invalid_request(
                f"Could not find event with type {event_type} and filter {event_filter}"
            )

        # Save the configuration (integration will handle modifying "data")
        for _integration in self._ledfx.config["integrations"]:
            if _integration["id"] == integration_id:
                _integration["data"] = integration.data
                break
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )
        return await self.request_success()

    async def post(self, integration_id, request) -> web.Response:
        """
        Add a new QLC event listener or update an existing one.

        Args:
            integration_id (str): The ID of the integration.
            request (web.Request): The request object containing `event_type`, `event_filter` and `qlc_payload`.

        Returns:
            web.Response: The response object.
        """
        integration = self._ledfx.integrations.get(integration_id)
        if (integration is None) or (integration.type != "qlc"):
            return await self.invalid_request(
                f"{integration} was not found or was not type qlc"
            )

        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()
        event_type = data.get("event_type")
        event_filter = data.get("event_filter")
        qlc_payload = data.get("qlc_payload")
        missing_attributes = []
        if event_type is None:
            missing_attributes.append("event_type")
        if event_filter is None:
            missing_attributes.append("event_filter")
        if qlc_payload is None:
            missing_attributes.append("qlc_payload")
        if missing_attributes:
            return await self.invalid_request(
                f'Required attributes {", ".join(missing_attributes)} were not provided'
            )

        if type(event_filter) is not dict:
            return await self.invalid_request(
                f'Invalid filter "{event_filter}", should be dictionary eg. {{ "scene_id" : "my scene" }} '
            )

        # Create a link between ledfx event and sending the payload
        integration.create_event(event_type, event_filter, True, qlc_payload)

        # Update and save the configuration
        for _integration in self._ledfx.config["integrations"]:
            if _integration["id"] == integration_id:
                _integration["data"] = integration.data
                break
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )
        return await self.request_success()

    async def delete(self, integration_id, request) -> web.Response:
        """
        Delete a QLC event listener.

        Args:
            integration_id (str): The ID of the integration.
            request (web.Request): The request object containing `event_type` and `event_filter`.

        Returns:
            web.Response: The response object.
        """
        integration = self._ledfx.integrations.get(integration_id)
        if (integration is None) or (integration.type != "qlc"):
            return await self.invalid_request(
                f"{integration} was not found or was not type qlc"
            )

        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()
        event_type = data.get("event_type")
        event_filter = data.get("event_filter")
        missing_attributes = []
        if event_type is None:
            missing_attributes.append("event_type")
        if event_filter is None:
            missing_attributes.append("event_filter")
        if missing_attributes:
            return await self.invalid_request(
                f'Required attributes {", ".join(missing_attributes)} were not provided'
            )

        if type(event_filter) is not dict:
            return await self.invalid_request(
                f'Invalid filter "{event_filter}", should be dictionary eg. {{ "scene_id" : "my scene" }} '
            )

        # Delete the listener and event from data
        integration.delete_event(event_type, event_filter)

        # Save the configuration (integration will handle modifying "data")
        for _integration in self._ledfx.config["integrations"]:
            if _integration["id"] == integration_id:
                _integration["data"] = integration.data
                break
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )
        return await self.request_success()
