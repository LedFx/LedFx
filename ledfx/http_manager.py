import logging
import os
import sys
import time

from aiohttp import web

import ledfx_frontend
from ledfx.api import RestApi

try:
    base_path = sys._MEIPASS
except BaseException:
    base_path = os.path.abspath(".")

_LOGGER = logging.getLogger(__name__)


class HttpServer:
    def __init__(self, ledfx, host, port):
        """Initialize the HTTP server"""

        self.app = web.Application()
        self.api = RestApi(ledfx)

        self.register_routes()

        self._ledfx = ledfx
        self.host = host
        self.port = port

    def register_routes(self):

        self.api.register_routes(self.app)
        self.app.router.add_route("get", "/favicon.ico", self.favicon)
        self.app.router.add_route("get", "/manifest.json", self.manifest)
        self.app.router.add_static(
            "/static",
            path=ledfx_frontend.where() + "/static",
            name="static",
        )

        self.app.router.add_route("get", "/", self.index)
        self.app.router.add_route("get", "/{extra:.+}", self.index)

    async def index(self, response):

        return web.FileResponse(
            path=ledfx_frontend.where() + "/index.html", status=200
        )

    async def favicon(self, response):

        return web.FileResponse(
            path=ledfx_frontend.where() + "/favicon.ico", status=200
        )

    async def manifest(self, response):
        return web.FileResponse(
            path=ledfx_frontend.where() + "/manifest.json", status=200
        )

    async def start(self):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        try:
            site = web.TCPSite(self.runner, self.host, self.port)
            await site.start()
            self.base_url = ("http://{}:{}").format(self.host, self.port)
            if self.host == "0.0.0.0":
                self.base_url = ("http://localhost:{}").format(self.port)
            print(("Started webinterface at {}").format(self.base_url))
        except OSError as error:
            _LOGGER.error(
                "Shutting down - Failed to create HTTP server at port %d: %s.",
                self.port,
                error,
            )
            _LOGGER.error(
                "Is LedFx Already Running? If not, try a different port."
            )
            if self._ledfx.icon is not None:
                if self._ledfx.icon.HAS_NOTIFICATION:
                    self._ledfx.icon.notify(
                        f"Failed to start: something is running on port {self.port}\nIs LedFx already running?"
                    )
            time.sleep(2)
            self._ledfx.stop(1)

    async def stop(self):
        await self.app.shutdown()
        if self.runner:
            await self.runner.cleanup()
        await self.app.cleanup()
