# Log API

## POST /api/log

Allows the frontend to post a line of text to the backend log. The message is sanitized, rate-limited, and logged at INFO level.

### Request
- **Method:** POST
- **Endpoint:** `/api/log`
- **Content-Type:** `application/json`
- **Body:**
  ```json
  {
    "text": "Your log message here"
  }
  ```

### Behavior
- Only ASCII characters are accepted; non-ASCII are stripped.
- Maximum length: 200 characters (longer input is truncated).
- Leading/trailing whitespace is removed.
- Requests are rate-limited to 1 per 1 second per client IP.
- The sanitized message is logged via `_LOGGER.info` on the backend.

### Responses
- **200 OK** (success):
  ```json
  {
    "status": "success"
  }
  ```
- **200 OK** (rate limit or invalid input):
  ```json
  {
    "status": "failed",
    "payload": {
      "type": "rate-limit",
      "reason": "Too many requests. Try again in 10 seconds."
    }
  }
  ```
- **200 OK** (invalid input):
  ```json
  {
    "status": "failed",
    "payload": {
      "type": "invalid-input",
      "reason": "Missing required field 'text'."
    }
  }
  ```

### Example
```bash
curl -X POST http://localhost:8888/api/log \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello from frontend!"}'
```

---


## GET /api/log

Establishes a WebSocket connection to stream backend log messages in real time.

### Request
- **Method:** GET
- **Endpoint:** `/api/log`
- **Upgrade:** WebSocket

### Behavior
- On connection, the backend sends recent log history (up to 30 messages).
- As new log messages are generated, they are pushed to the client in real time.
- The client may send messages, but these are ignored by the backend.
- The connection is closed on server shutdown or client disconnect.

### Message Format
Each log message is sent as a JSON object, typically matching the backend's log record structure. Example:

```text
{
  "level": "INFO",
  "message": "System started",
  "timestamp": "2025-11-24T12:34:56.789Z"
  // other fields...
}
```

### Use Case
- This endpoint is intended for real-time log monitoring in the frontend or admin tools.
- No authentication is required by default.

