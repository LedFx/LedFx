import inspect
import logging
import uuid
from json import JSONDecodeError

import aiohttp_cors
from aiohttp import web

from ledfx.utils import BaseRegistry, RegistryLoader

_LOGGER = logging.getLogger(__name__)

SNACKBAR_OPTIONS = ["success", "info", "warning", "error"]


@BaseRegistry.no_registration
class RestEndpoint(BaseRegistry):
    def __init__(self, ledfx):
        self._ledfx = ledfx

    async def handler(self, request: web.Request):
        short_uuid = str(uuid.uuid4())[:4]
        _LOGGER.debug(
            f"LedFx API Request {short_uuid}: {request.method} {request.path}"
        )
        body = None
        if request.has_body:
            try:
                body = await request.json()
            except JSONDecodeError:
                body = await request.text()
            finally:
                _LOGGER.debug(
                    f"LedFx API Request {short_uuid} payload: {body}"
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
            raise web.HttpBadRequest("")

        try:
            return await method(
                **{
                    arg_name: available_args[arg_name]
                    for arg_name in wanted_args
                }
            )
        except Exception as e:
            # _LOGGER.exception(e)
            reason = getattr(e, "args", None)
            if reason:
                reason = reason[0]
            else:
                reason = repr(e)
            response = {
                "status": "failed",
                "payload": {
                    "type": "error",
                    "reason": reason,
                },
            }
            return web.json_response(data=response, status=202)

    async def json_decode_error(self) -> web.Response:
        """
        Handle messaging for JSON Decoding errors.

        Returns:
            A web response with a JSON payload containing the error and a 400 status.
        """
        response = {
            "status": "failed",
            "reason": "JSON decoding failed",
        }
        return web.json_response(data=response, status=400)

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
        return web.json_response(data=response, status=500)

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
        return web.json_response(data=response, status=resp_code)

    async def request_success(
        self, type=None, message=None, resp_code=200
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
        return web.json_response(data=response, status=resp_code)

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
        return web.json_response(data=payload, status=200)


class RestApi(RegistryLoader):
    PACKAGE_NAME = "ledfx.api"

    def __init__(self, ledfx):
        super().__init__(ledfx, RestEndpoint, self.PACKAGE_NAME)
        self._ledfx = ledfx

    def register_routes(self, app):
        methods = ["GET", "PUT", "POST", "DELETE"]
        cors = aiohttp_cors.setup(
            app,
            defaults={
                "*": aiohttp_cors.ResourceOptions(
                    allow_credentials=True,
                    expose_headers="*",
                    allow_headers="*",
                    allow_methods=methods,
                )
            },
        )
        # Create the endpoints and register their routes
        for endpoint_type in self.types():
            endpoint = self.create(type=endpoint_type, ledfx=self._ledfx)
            resource = cors.add(
                app.router.add_resource(
                    endpoint.ENDPOINT_PATH, name=f"api_{endpoint_type}"
                )
            )
            for method in methods:
                cors.add(resource.add_route(method, endpoint.handler))
