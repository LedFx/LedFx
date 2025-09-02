"""API endpoint for ChatGPT integration management and status checking"""

import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class ChatGPTEndpoint(RestEndpoint):
    """REST endpoint for querying and managing ChatGPT integrations"""

    ENDPOINT_PATH = "/api/integrations/chatgpt/{integration_id}"

    async def get(self, integration_id) -> web.Response:
        """
        Get ChatGPT integration status and configuration
        
        Args:
            integration_id (str): The ID of the ChatGPT integration
            
        Returns:
            web.Response: The response containing ChatGPT integration status
        """
        if integration_id is None:
            return await self.invalid_request(
                'Required attribute "integration_id" was not provided'
            )
            
        integration = self._ledfx.integrations.get(integration_id)
        if (integration is None) or (integration.type != "chatgpt"):
            return await self.invalid_request(
                f"ChatGPT integration with ID '{integration_id}' was not found"
            )

        # Get detailed status from the integration
        try:
            status = integration.get_status()
            response = {
                "integration_id": integration_id,
                "name": integration.name,
                "description": integration.description,
                "type": "chatgpt",
                "active": integration.active,
                "status": integration.status,
                "installed": True,
                "enabled": integration.active,
                "details": status,
                "config": {
                    "name": integration._config.get("name"),
                    "description": integration._config.get("description"),
                    "model": integration._config.get("model"),
                    "max_tokens": integration._config.get("max_tokens"),
                    # Don't expose API key in response for security
                    "api_key_configured": bool(integration._config.get("api_key", "").strip()),
                    "temperature": integration._config.get("temperature"),
                }
            }
            return await self.bare_request_success(response)
            
        except Exception as e:
            _LOGGER.error(f"Error getting ChatGPT integration status: {e}")
            return await self.internal_error(f"Failed to get integration status: {e}")

    async def post(self, integration_id, request) -> web.Response:
        """
        Send a command to the ChatGPT integration
        
        Args:
            integration_id (str): The ID of the ChatGPT integration
            request (web.Request): The request object containing the command
            
        Returns:
            web.Response: The response from ChatGPT processing
        """
        if integration_id is None:
            return await self.invalid_request(
                'Required attribute "integration_id" was not provided'
            )
            
        integration = self._ledfx.integrations.get(integration_id)
        if (integration is None) or (integration.type != "chatgpt"):
            return await self.invalid_request(
                f"ChatGPT integration with ID '{integration_id}' was not found"
            )
            
        if not integration.active:
            return await self.invalid_request(
                f"ChatGPT integration '{integration_id}' is not active"
            )

        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()
            
        command = data.get("command")
        if not command:
            return await self.invalid_request(
                'Required attribute "command" was not provided'
            )

        try:
            result = await integration.process_command(command)
            return await self.bare_request_success(result)
            
        except Exception as e:
            _LOGGER.error(f"Error processing ChatGPT command: {e}")
            return await self.internal_error(f"Failed to process command: {e}")


class ChatGPTStatusEndpoint(RestEndpoint):
    """REST endpoint for checking ChatGPT integration installation and enablement status"""

    ENDPOINT_PATH = "/api/integrations/chatgpt/status"

    async def get(self, request=None) -> web.Response:
        """
        Check if ChatGPT connector is installed and enabled
        
        Returns:
            web.Response: Status of all ChatGPT integrations
        """
        # Find all ChatGPT integrations
        chatgpt_integrations = {}
        
        for integration_id, integration in self._ledfx.integrations.items():
            if integration.type == "chatgpt":
                try:
                    status = integration.get_status() if hasattr(integration, 'get_status') else {}
                    chatgpt_integrations[integration_id] = {
                        "id": integration_id,
                        "name": integration.name,
                        "description": integration.description,
                        "installed": True,
                        "enabled": integration.active,
                        "status": integration.status,
                        "details": status,
                    }
                except Exception as e:
                    _LOGGER.error(f"Error getting status for ChatGPT integration {integration_id}: {e}")
                    chatgpt_integrations[integration_id] = {
                        "id": integration_id,
                        "installed": True,
                        "enabled": integration.active,
                        "status": "error",
                        "error": str(e),
                    }

        # Calculate overall status
        total_count = len(chatgpt_integrations)
        enabled_count = sum(1 for integ in chatgpt_integrations.values() if integ.get("enabled", False))
        
        response = {
            "chatgpt_connector_installed": total_count > 0,
            "chatgpt_connector_enabled": enabled_count > 0,
            "total_integrations": total_count,
            "enabled_integrations": enabled_count,
            "integrations": chatgpt_integrations,
            "summary": {
                "status": "enabled" if enabled_count > 0 else ("installed" if total_count > 0 else "not_installed"),
                "message": (
                    f"{enabled_count} of {total_count} ChatGPT integrations are enabled"
                    if total_count > 0
                    else "No ChatGPT integrations found"
                ),
            }
        }
        
        return await self.bare_request_success(response)