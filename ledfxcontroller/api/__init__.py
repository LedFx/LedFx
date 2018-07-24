from ledfxcontroller.utils import BaseRegistry, RegistryLoader
from aiohttp import web
import logging
import inspect
import json

"""
REST API for LedFx:

    GET /api/devices
    PUT /api/devices
    GET /api/devices/{{device_id}}
    PUT /api/devices/{{device_id}}
    DEL /api/devices/{{device_id}}
    GET /api/devices/{{device_id}}/effects
    PUT /api/devices/{{device_id}}/effects
    DEL /api/devices/{{device_id}}/effects
    GET /api/devices/{{device_id}}/effects/{{effect_id}}
    PUT /api/devices/{{device_id}}/effects/{{effect_id}}
    DEL /api/devices/{{device_id}}/effects/{{effect_id}}

    GET /api/effects


"""

@BaseRegistry.no_registration
class RestEndpoint(BaseRegistry):

    def __init__(self, ledfx):
        self.ledfx = ledfx

    async def handler(self, request: web.Request):
        method = getattr(self, request.method.lower(), None)
        if not method:
            raise web.HTTPMethodNotAllowed('')

        wanted_args = list(inspect.signature(method).parameters.keys())
        available_args = request.match_info.copy()
        available_args.update({'request': request})

        unsatisfied_args = set(wanted_args) - set(available_args.keys())
        if unsatisfied_args:
            raise web.HttpBadRequest('')

        return await method(**{arg_name: available_args[arg_name] for arg_name in wanted_args})

class RestApi(RegistryLoader):

    PACKAGE_NAME = 'ledfxcontroller.api'

    def __init__(self, ledfx):
        super().__init__(RestEndpoint, self.PACKAGE_NAME, ledfx)
        self.ledfx = ledfx

    def register_routes(self, app):

        # Create the endpoints and register their routes
        for endpoint_type in self.types():
            endpoint = self.create(endpoint_type, None, None, self.ledfx)
            app.router.add_route('*', endpoint.ENDPOINT_PATH, endpoint.handler, name = "api_{}".format(endpoint_type))