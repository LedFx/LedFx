"""ChatGPT Connector Integration for LedFx"""

import logging

import voluptuous as vol

from ledfx.integrations import Integration

_LOGGER = logging.getLogger(__name__)


class ChatGPT(Integration):
    """ChatGPT Connector Integration"""

    beta = False  # Set to False to make it generally available

    NAME = "ChatGPT"
    DESCRIPTION = "ChatGPT connector for AI-powered lighting control and automation"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "name",
                description="Name of this integration instance and associated settings",
                default="ChatGPT Connector",
            ): str,
            vol.Required(
                "description",
                description="Description of this integration",
                default="AI-powered lighting control via ChatGPT",
            ): str,
            vol.Optional(
                "api_key",
                description="OpenAI API key for ChatGPT access",
                default="",
            ): str,
            vol.Optional(
                "model",
                description="ChatGPT model to use",
                default="gpt-3.5-turbo",
            ): str,
            vol.Optional(
                "max_tokens",
                description="Maximum tokens per request",
                default=150,
            ): vol.All(int, vol.Range(min=1, max=4000)),
            vol.Optional(
                "temperature",
                description="Response creativity (0.0-2.0)",
                default=0.7,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
        }
    )

    def __init__(self, ledfx, config, active, data):
        super().__init__(ledfx, config, active, data)

        self._ledfx = ledfx
        self._config = config
        self._data = data or {}
        self._client = None

        # Initialize data structure if not present
        if not self._data:
            self._data = {
                "connection_status": "disconnected",
                "last_request": None,
                "total_requests": 0,
                "commands_processed": 0,
            }

    async def connect(self, msg=None):
        """
        Establish connection to ChatGPT API.
        
        This method initializes the OpenAI client and tests connectivity.
        For now, we'll simulate connection since we want to keep dependencies minimal.
        """
        _LOGGER.info(f"Connecting to ChatGPT API for integration '{self.name}'")
        
        try:
            # Check if API key is provided
            api_key = self._config.get("api_key", "")
            if not api_key.strip():
                _LOGGER.warning(
                    f"No API key provided for ChatGPT integration '{self.name}'. "
                    "Connection established but API calls will not work."
                )
            else:
                _LOGGER.info(f"API key configured for ChatGPT integration '{self.name}'")

            # Update connection status
            self._data["connection_status"] = "connected"
            
            await super().connect(f"ChatGPT integration '{self.name}' connected successfully")
            
        except Exception as e:
            _LOGGER.error(f"Failed to connect ChatGPT integration '{self.name}': {e}")
            self._data["connection_status"] = "error"
            raise

    async def disconnect(self, msg=None):
        """
        Disconnect from ChatGPT API.
        """
        _LOGGER.info(f"Disconnecting ChatGPT integration '{self.name}'")
        
        try:
            # Clean up any resources
            self._client = None
            self._data["connection_status"] = "disconnected"
            
            await super().disconnect(f"ChatGPT integration '{self.name}' disconnected")
            
        except Exception as e:
            _LOGGER.error(f"Error during ChatGPT integration disconnect: {e}")
            raise

    def get_status(self):
        """Get the current status of the ChatGPT integration"""
        return {
            "connection_status": self._data.get("connection_status", "disconnected"),
            "api_key_configured": bool(self._config.get("api_key", "").strip()),
            "model": self._config.get("model", "gpt-3.5-turbo"),
            "total_requests": self._data.get("total_requests", 0),
            "commands_processed": self._data.get("commands_processed", 0),
            "last_request": self._data.get("last_request"),
        }

    async def process_command(self, command_text):
        """
        Process a natural language command through ChatGPT.
        
        This is a placeholder method for future implementation.
        """
        _LOGGER.info(f"Processing command: {command_text}")
        
        # Update request counter
        self._data["total_requests"] = self._data.get("total_requests", 0) + 1
        self._data["last_request"] = command_text
        
        # For now, return a placeholder response
        return {
            "status": "processed",
            "command": command_text,
            "response": "ChatGPT integration is installed and ready (placeholder response)",
            "actions_taken": [],
        }

    @property
    def data(self):
        """Return integration data"""
        return self._data

    @property 
    def config(self):
        """Return integration configuration"""
        return self._config