import logging
import os
import ssl
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
    def __init__(self, ledfx, host, port, port_s):
        """Initialize the HTTP server"""

        self.app = web.Application()
        self.api = RestApi(ledfx)

        self.register_routes()

        self._ledfx = ledfx
        self.host = host
        self.port = port
        self.port_s = port_s

    def register_routes(self):
        self.api.register_routes(self.app)
        self.app.router.add_static(
            "/favicon",
            path=ledfx_frontend.where() + "/favicon",
            name="favicon",
        )
        self.app.router.add_route("get", "/manifest.json", self.manifest)
        self.app.router.add_route(
            "get", "/serviceWorker.js", self.service_worker
        )
        self.app.router.add_route(
            "get", "/service-worker.js", self.service_worker_b
        )
        self.app.router.add_route("get", "/callback/", self.index)
        self.app.router.add_route("get", "/", self.index)

        self.app.router.add_static(
            "/static",
            path=ledfx_frontend.where() + "/static",
            name="static",
        )

    async def index(self, response):
        return web.FileResponse(
            path=ledfx_frontend.where() + "/index.html", status=200
        )

    async def manifest(self, response):
        return web.FileResponse(
            path=ledfx_frontend.where() + "/manifest.json", status=200
        )

    async def service_worker(self, response):
        return web.FileResponse(
            path=ledfx_frontend.where() + "/serviceWorker.js", status=200
        )

    async def service_worker_b(self, response):
        return web.FileResponse(
            path=ledfx_frontend.where() + "/service-worker.js", status=200
        )

    async def start(self, ssl_certs=None):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        try:
            await self.start_tcpsite()
            if ssl_certs:
                ssl_context = ssl.create_default_context(
                    ssl.Purpose.CLIENT_AUTH
                )
                ssl_context.load_cert_chain(*ssl_certs)
                await self.start_tcpsite(ssl_context)
        except OSError as error:
            self.handle_start_error(error)

    async def start_tcpsite(self, ssl_context=None):
        port = self.port_s if ssl_context else self.port
        site = web.TCPSite(
            self.runner, self.host, port, ssl_context=ssl_context
        )
        await site.start()
        self.base_url = ("http{}://{}:{}").format(
            "s" if ssl_context else "", self.host, port
        )
        if self.host == "0.0.0.0":
            self.base_url = ("http{}://localhost:{}").format(
                "s" if ssl_context else "", port
            )
        print(("Started webinterface at {}").format(self.base_url))

    def handle_start_error(self, error):
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
