import inspect
import json
import logging
import uuid
from json import JSONDecodeError
from typing import ClassVar

from aiohttp import web
from pydantic import ValidationError

from ledfx.api.jsonutil import dumps
from ledfx.errors import LedFxError
from ledfx.utils import BaseRegistry, RegistryLoader

_LOGGER = logging.getLogger(__name__)

SNACKBAR_OPTIONS = ["success", "info", "warning", "error"]


@BaseRegistry.no_registration
class RestEndpoint(BaseRegistry):
    # Methods whose JSON body must be an object. GET bodies may name keys as
    # a string or list; an endpoint that takes another shape overrides this.
    ENDPOINT_PATH: ClassVar[str]
    OBJECT_BODY_METHODS: tuple[str, ...] = ("PUT", "POST", "DELETE")

    def __init__(self, ledfx):
        self._ledfx = ledfx

    async def handler(self, request: web.Request):
        short_uuid = str(uuid.uuid4())[:4]
        _LOGGER.debug(
            "LedFx API Request %s: %s %s",
            short_uuid,
            request.method,
            request.path,
        )
        body = None
        body_is_json = False
        # Skip body parsing for multipart requests - they need to use request.multipart()
        content_type = request.headers.get("Content-Type", "")
        if request.has_body and not content_type.startswith("multipart/"):
            try:
                body = await request.json()
                body_is_json = True
            except JSONDecodeError:
                body = await request.text()
            finally:
                if isinstance(body, dict):
                    body_summary = {"keys": sorted(body.keys())}
                elif isinstance(body, list):
                    body_summary = {"items": len(body)}
                elif body is None:
                    body_summary = None
                else:
                    body_summary = {"length": len(str(body))}
                _LOGGER.debug(
                    "LedFx API Request %s payload summary: %s",
                    short_uuid,
                    body_summary,
                )

        method = getattr(self, request.method.lower(), None)
        if not method:
            allowed_methods = [
                meth.upper()
                for meth in ["get", "post", "put", "delete"]
                if hasattr(self, meth)
            ]
            raise web.HTTPMethodNotAllowed("", allowed_methods=allowed_methods)

        wanted_args = list(inspect.signature(method).parameters.keys())
        available_args = request.match_info.copy()
        available_args.update({"request": request, "body": body})

        unsatisfied_args = set(wanted_args) - set(available_args.keys())
        if unsatisfied_args:
            raise web.HTTPBadRequest()

        if (
            request.method in self.OBJECT_BODY_METHODS
            and body_is_json
            and not isinstance(body, dict)
        ):
            return await self.invalid_request("Request body must be a JSON object")

        try:
            return await method(
                **{arg_name: available_args[arg_name] for arg_name in wanted_args}
            )
        except ValidationError as e:
            return await self.validation_error(e)
        except LedFxError as err:
            # v1 keeps its default failure shape (HTTP 200) for every domain
            # error, internal ones included; handlers whose legacy status
            # differs catch the error themselves. Server-side failures are
            # logged because the response hides them.
            if err.status >= 500:
                _LOGGER.error("%s: %s", type(err).__name__, err)
            return await self.invalid_request(str(err))
        except web.HTTPException:
            raise
        except Exception as e:  # noqa: BLE001
            # _LOGGER.exception(e)
            reason = getattr(e, "args", None)
            if reason:
                reason = str(reason[0])
            else:
                reason = str(e)

            response = {
                "status": "failed",
                "payload": {
                    "type": "error",
                    "reason": reason,
                },
            }
            return web.json_response(data=response, status=202, dumps=dumps)

    async def json_decode_error(self) -> web.Response:
        """
        Handle messaging for JSON Decoding errors.

        Returns:
            A web response with a JSON payload containing the error and a 400 status.
        """
        response = {
            "status": "failed",
            "reason": "JSON decoding failed",
            "payload": {"type": "error", "reason": "Request body is not valid JSON"},
        }
        return web.json_response(data=response, status=400, dumps=dumps)

    async def internal_error(
        self, message="Internal error", type="error"
    ) -> web.Response:
        """
        Handle messaging for internal errors.
        Default a type of error.

        Returns:
            A web response with a JSON payload containing the error and a 500 status.
        """
        if type not in SNACKBAR_OPTIONS:
            raise ValueError(
                "Snackbar type must be one of 'success', 'info', 'warning', 'error'."
            )
        response = {
            "status": "failed",
            "payload": {"type": type, "reason": message},
        }
        return web.json_response(data=response, status=500, dumps=dumps)

    async def invalid_request(
        self, message="Invalid request", type="error", resp_code=200
    ) -> web.Response:
        """
        Returns a JSON response indicating an invalid request.

        Args:
            reason (str): The reason for the invalid request. Defaults to 'Invalid request'.
            type (str): The type of error. Defaults to 'error'.
            resp_code (int): The response code to be returned. Defaults to 200 so that snackbar works.

        Returns:
            web.Response: A JSON response with the status and reason for the invalid request.
        """
        if type not in SNACKBAR_OPTIONS:
            raise ValueError(
                "Snackbar type must be one of 'success', 'info', 'warning', 'error'."
            )
        response = {
            "status": "failed",
            "payload": {
                "type": type,
                "reason": message,
            },
        }
        return web.json_response(data=response, status=resp_code, dumps=dumps)

    async def validation_error(self, err: ValidationError) -> web.Response:
        # err.json() stringifies inputs that plain JSON can't encode.
        errors = json.loads(err.json(include_url=False, include_context=False))
        response = {
            "status": "failed",
            "payload": {"type": "error", "reason": f"{len(errors)} invalid value(s)"},
            "errors": errors,
        }
        return web.json_response(data=response, status=400, dumps=dumps)

    async def request_success(
        self, type=None, message=None, data=None, resp_code=200
    ) -> web.Response:
        """
        Returns a JSON response indicating a successful request.
        Optionally include a snackbar type and message to return to the user.

        Args:
            type (str): The type of snackbar to display. Defaults to None.
            message (str): The message to display in the snackbar. Defaults to None.
            resp_code (int): The response code to be returned. Defaults to 200.

        Returns:
            web.Response: A JSON response with the status and payload for the successful request.
        """
        response = {
            "status": "success",
        }
        if type and message is not None:
            if type not in SNACKBAR_OPTIONS:
                raise ValueError(
                    "Snackbar type must be one of 'success', 'info', 'warning', 'error'"
                )
            response["payload"] = {
                "type": type,
                "reason": message,
            }
        if data:
            response["data"] = data
        return web.json_response(data=response, status=resp_code, dumps=dumps)

    async def bare_request_success(self, payload) -> web.Response:
        """
        Returns a "bare" JSON response indicating a successful request - only a payload and a 200 code.

        Args:
            payload (dict): The payload to be returned.
            resp_code (int): The response code to be returned. Defaults to 200.

        Returns:
            web.Response: A JSON response with the status and payload for the successful request.
        """
        if payload is None:
            raise ValueError(
                "Payload must be provided to the bare request_success method."
            )
        return web.json_response(data=payload, status=200, dumps=dumps)


class RestApi(RegistryLoader):
    PACKAGE_NAME = "ledfx.api"

    def __init__(self, ledfx):
        super().__init__(ledfx, RestEndpoint, self.PACKAGE_NAME)
        self._ledfx = ledfx

    def register_routes(self, app):
        # Create the endpoints and register their routes
        for endpoint_type in self.types():
            endpoint = self.create(type=endpoint_type, ledfx=self._ledfx)
            resource = app.router.add_resource(
                endpoint.ENDPOINT_PATH, name=f"api_{endpoint_type}"
            )
            for method in ["GET", "PUT", "POST", "DELETE"]:
                resource.add_route(method, endpoint.handler)
