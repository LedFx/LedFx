import inspect
import logging

import aiohttp_cors
from aiohttp import web

from ledfx.utils import BaseRegistry, RegistryLoader

_LOGGER = logging.getLogger(__name__)


@BaseRegistry.no_registration
class RestEndpoint(BaseRegistry):
    def __init__(self, ledfx):
        self._ledfx = ledfx

    async def handler(self, request: web.Request):
        method = getattr(self, request.method.lower(), None)
        if not method:
            raise web.HTTPMethodNotAllowed("")

        wanted_args = list(inspect.signature(method).parameters.keys())
        available_args = request.match_info.copy()
        available_args.update({"request": request})

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
            # finally:
            #     if self._ledfx.dev_enabled():
            #         raise


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
            # cors.add(
            #     resource.add_route(
            #         "*",
            #         endpoint.handler,
            #     )
            # )
            for method in methods:
                cors.add(resource.add_route(method, endpoint.handler))
