"""
API endpoints for mood detection and management.

Provides REST API endpoints for:
- Getting current mood and structure information
- Configuring mood detection settings
- Enabling/disabling mood-based adjustments
"""

import logging
from json import JSONDecodeError
from typing import Any, Dict, Optional

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config

_LOGGER = logging.getLogger(__name__)


class MoodEndpoint(RestEndpoint):
    """
    REST API endpoint for mood detection information.
    
    GET /api/mood - Get current mood and structure information
    PUT /api/mood - Configure mood detection settings
    """

    ENDPOINT_PATH = "/api/mood"

    async def get(self, request: web.Request) -> web.Response:
        """
        Get current mood and structure information.
        
        Returns:
            {
                "status": "success",
                "mood": {
                    "enabled": bool,
                    "available": bool,
                    "current_mood": {
                        "energy": float,
                        "valence": float,
                        "intensity": float,
                        "brightness": float,
                        "beat_strength": float,
                        "spectral_warmth": float,
                        ...
                    },
                    "mood_category": str,
                    "structure": {
                        "section": str,
                        "duration": float,
                        "last_event": str,
                        "energy_trend": float,
                        "is_transitional": bool
                    }
                }
            }
        """
        try:
            # Check if mood manager integration exists
            mood_manager = self._get_mood_manager()
            
            if mood_manager is None:
                return await self.bare_request_success({
                    "enabled": False,
                    "available": False,
                    "message": "Mood manager not available"
                })
            
            # Get current mood and structure
            current_mood = mood_manager.get_current_mood()
            current_structure = mood_manager.get_current_structure()
            
            enabled = mood_manager._config.get("enabled", False)
            
            response: Dict[str, Any] = {
                "enabled": enabled,
                "available": True,
            }
            
            if current_mood:
                # Create a safe copy for frontend compatibility
                safe_mood = {}
                for key, value in current_mood.items():
                    # Ensure all values are JSON-serializable and safe
                    if value is None:
                        continue  # Skip None values to avoid frontend issues
                    elif isinstance(value, (str, int, float, bool)):
                        safe_mood[key] = value
                    elif isinstance(value, dict):
                        # Keep dicts (like music_styles) but ensure they're valid
                        safe_mood[key] = value
                    elif hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
                        # Convert arrays/lists to lists
                        try:
                            safe_mood[key] = list(value)
                        except (TypeError, ValueError):
                            continue  # Skip if can't convert
                    else:
                        # Try to convert to string for safety
                        try:
                            safe_mood[key] = str(value)
                        except (TypeError, ValueError):
                            continue  # Skip if can't convert
                
                response["current_mood"] = safe_mood
                if mood_manager._mood_detector:
                    try:
                        # Get mood category - ensure it's always a string and never None
                        category = mood_manager._mood_detector.get_mood_category()
                        if category and isinstance(category, str) and len(category) > 0:
                            response["mood_category"] = category
                        else:
                            response["mood_category"] = "unknown"
                    except Exception as e:
                        _LOGGER.debug(f"Error getting mood category: {e}")
                        response["mood_category"] = "unknown"
                else:
                    # Fallback if detector not available
                    response["mood_category"] = "unknown"
            else:
                # Ensure mood_category exists even if no mood data
                response["mood_category"] = "unknown"
            
            if current_structure:
                response["structure"] = current_structure
            
            return await self.bare_request_success(response)
            
        except Exception as e:
            _LOGGER.error(f"Error getting mood information: {e}", exc_info=True)
            return await self.internal_error(str(e))
    
    def _get_mood_manager(self) -> Optional[Any]:
        """
        Helper method to get mood manager integration.
        
        Returns:
            MoodManager instance or None if not found
        """
        if not hasattr(self._ledfx, "integrations"):
            return None
        
        # Try to get by ID first
        mood_manager = self._ledfx.integrations.get("mood_manager")
        if mood_manager is not None:
            return mood_manager
        
        # Find by type
        for integration in self._ledfx.integrations.values():
            if hasattr(integration, "type") and integration.type == "mood_manager":
                return integration
            if hasattr(integration, "NAME") and integration.NAME == "mood_manager":
                return integration
        
        return None

    async def put(self, request: web.Request) -> web.Response:
        """
        Configure mood detection settings.
        
        Request body:
            {
                "enabled": bool,  # Enable/disable mood detection
                "config": {  # Optional configuration updates
                    "adjust_colors": bool,
                    "adjust_effects": bool,
                    "switch_scenes": bool,
                    "react_to_events": bool,
                    "intensity": float,
                    "mood_scenes": dict,
                    "event_scenes": dict,
                    "target_virtuals": list
                }
            }
        
        Returns:
            {
                "status": "success",
                "message": "Mood detection configured"
            }
        """
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()
        
        try:
            # Check if mood manager exists
            mood_manager = self._get_mood_manager()
            
            if mood_manager is None:
                return await self.invalid_request(
                    "Mood manager integration not available"
                )
            
            # Update enabled state if provided
            if "enabled" in data:
                enabled = bool(data["enabled"])
                await mood_manager.set_enabled(enabled)
            
            # Update configuration if provided
            if "config" in data:
                config_updates = data["config"]
                
                # Check if librosa config changed (requires reconnect)
                librosa_config_changed = any(
                    key in config_updates 
                    for key in ["use_librosa", "librosa_buffer_duration", "librosa_update_interval"]
                )
                
                # Validate and update config
                for key, value in config_updates.items():
                    if key in mood_manager._config:
                        mood_manager._config[key] = value
                
                # Save configuration - integrations is a list, not a dict
                if "integrations" not in self._ledfx.config:
                    self._ledfx.config["integrations"] = []
                
                # Find existing mood_manager integration in the list
                mood_manager_config = None
                for integration in self._ledfx.config["integrations"]:
                    if integration.get("type") == "mood_manager" or integration.get("id") == "mood_manager":
                        mood_manager_config = integration
                        break
                
                # Update or create the integration config entry
                if mood_manager_config:
                    mood_manager_config["config"].update(mood_manager._config)
                    mood_manager_config["active"] = mood_manager._active
                else:
                    # Create new integration entry
                    self._ledfx.config["integrations"].append({
                        "id": mood_manager.id,
                        "type": mood_manager.type,
                        "active": mood_manager._active,
                        "data": mood_manager._data,
                        "config": mood_manager._config.copy(),
                    })
                
                save_config(
                    config=self._ledfx.config,
                    config_dir=self._ledfx.config_dir,
                )
                
                # Reconnect if librosa config changed (to recreate MoodDetector with new config)
                if librosa_config_changed and mood_manager._mood_detector is not None:
                    _LOGGER.info("Librosa config changed, reconnecting mood manager...")
                    await mood_manager.disconnect()
                    await mood_manager.connect()
            
            return await self.request_success(
                "success",
                "Mood detection configured successfully"
            )
            
        except Exception as e:
            _LOGGER.error(f"Error configuring mood detection: {e}")
            return await self.internal_error(str(e))



