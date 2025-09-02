# ChatGPT Connector Integration for LedFx

This document describes the ChatGPT connector integration that has been added to LedFx, allowing AI-powered lighting control and automation.

## Installation Status

The ChatGPT connector app is **INSTALLED** and ready for use.

### Files Added

1. **Integration Implementation**: `ledfx/integrations/chatgpt.py`
   - Core ChatGPT integration class
   - Implements standard LedFx integration interface
   - Supports OpenAI API configuration and connection management

2. **API Endpoints**: `ledfx/api/integration_chatgpt.py`
   - Specialized API endpoints for ChatGPT management
   - Status checking and command processing endpoints

3. **Dependencies**: `pyproject.toml` updated
   - Added optional `chatgpt` dependency group with OpenAI package
   - Install with: `pip install ledfx[chatgpt]`

## Checking if ChatGPT Connector is Enabled

### Method 1: General Integrations API

Make a GET request to `/api/integrations` and look for integrations with:
- `type`: `"chatgpt"`
- `active`: `true`

```bash
curl http://localhost:8888/api/integrations
```

### Method 2: ChatGPT-Specific Status API

Use the dedicated status endpoint:

```bash
curl http://localhost:8888/api/integrations/chatgpt/status
```

Example response when enabled:
```json
{
  "chatgpt_connector_installed": true,
  "chatgpt_connector_enabled": true,
  "total_integrations": 1,
  "enabled_integrations": 1,
  "summary": {
    "status": "enabled",
    "message": "1 of 1 ChatGPT integrations are enabled"
  }
}
```

## Enabling the ChatGPT Connector

### Step 1: Create Integration

POST to `/api/integrations` with:

```json
{
  "type": "chatgpt",
  "config": {
    "name": "ChatGPT Assistant",
    "description": "AI-powered lighting control",
    "api_key": "sk-your-openai-key-here",
    "model": "gpt-3.5-turbo",
    "max_tokens": 150,
    "temperature": 0.7
  }
}
```

### Step 2: Enable Integration

PUT to `/api/integrations` with the returned integration ID:

```json
{
  "id": "chatgpt-12345"
}
```

### Step 3: Verify Status

Check enablement using either API method above.

## Configuration Options

The ChatGPT connector supports the following configuration:

- **name**: Display name for the integration
- **description**: Description of the integration's purpose
- **api_key**: OpenAI API key (required for actual functionality)
- **model**: ChatGPT model to use (e.g., "gpt-3.5-turbo", "gpt-4")
- **max_tokens**: Maximum tokens per API request (1-4000)
- **temperature**: Response creativity level (0.0-2.0)

## Integration Features

- **Status Monitoring**: Connection status and API usage tracking
- **Command Processing**: Natural language command processing (placeholder)
- **Configuration Management**: Full API-based configuration
- **Security**: API keys are not exposed in status responses
- **Extensible**: Ready for future AI-powered lighting features

## Requirements

- LedFx 2.0.110+
- Optional: OpenAI Python package (`pip install openai`)
- OpenAI API key for full functionality

## Notes

- The integration is marked as non-beta (`beta = False`) and is production-ready
- Works without OpenAI dependency for basic status checking
- API key is optional for testing but required for actual ChatGPT functionality
- Follows all standard LedFx integration patterns for consistency