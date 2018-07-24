import logging
import jinja2
import aiohttp_jinja2
from aiohttp import web
import aiohttp
from ledfxcontroller.consts import PROJECT_ROOT
from ledfxcontroller.api import RestApi
import numpy as np
import json

_LOGGER = logging.getLogger(__name__)

class LedFxControllerHTTP(object):
    def __init__(self, ledfx, host, port):
        """Initialize the HTTP server"""

        self.app = web.Application(loop=ledfx.loop)
        self.api = RestApi(ledfx)
        aiohttp_jinja2.setup(
            self.app, loader=jinja2.PackageLoader('ledfxcontroller', 'frontend'))
        self.register_routes()

        self.ledfx = ledfx
        self.host = host
        self.port = port

    @aiohttp_jinja2.template('index.html')
    async def index(self, request):
        return { }

    def register_routes(self):
        self.api.register_routes(self.app)
        self.app.router.add_static('/static',
                        path=PROJECT_ROOT / 'frontend_dist',
                        name='static')

        self.app.router.add_route('get', '/', self.index)
        self.app.router.add_route('get', '/{extra:.+}', self.index)

    async def start(self):
        self.handler = self.app.make_handler(loop=self.ledfx.loop)

        try:
            self.server = await self.ledfx.loop.create_server(
                self.handler, self.host, self.port)
        except OSError as error:
            _LOGGER.error("Failed to create HTTP server at port %d: %s",
                          self.port, error)
        
        self.base_url = ('http://{}:{}').format(self.host, self.port)
        print(('Started webinterface at {}').format(self.base_url))

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        await self.app.shutdown()
        if self.handler:
            await self.handler.shutdown(10)
        await self.app.cleanup()