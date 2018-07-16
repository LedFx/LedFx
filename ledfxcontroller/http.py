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
        return { 
            'devices': self.ledfx.devices.values()
        }

    @aiohttp_jinja2.template('dev_tools.html')
    async def dev_tools(self, request):
        return { }

    @aiohttp_jinja2.template('device.html')
    async def device(self, request):
        device_id = request.match_info['device_id']
        device = self.ledfx.devices.get_device(device_id)
        
        if device is None:
            return web.json_response({'error_message': 'Invalid device id'})

        return {
            'devices': self.ledfx.devices.values(),
            'effects': self.ledfx.effects.classes(),
            'device': device
        }

    async def websocket_handler(self, request):
        device_id = request.match_info['device_id']
        device = self.ledfx.devices.get_device(device_id)

        ws = web.WebSocketResponse()
        await ws.prepare(request)

        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                if msg.data == 'get_pixels':
                    rgb_x = np.arange(0, device.pixel_count).tolist()
                    if device.latest_frame is not None:
                        pixels = np.copy(device.latest_frame).T
                        await ws.send_json({"action": "update_pixels", "rgb_x": rgb_x, "r": pixels[0].tolist(), "g": pixels[1].tolist(), "b": pixels[2].tolist()})
                    else:
                        pixels = np.zeros((device.pixel_count, 3))
                        await ws.send_json({"action": "update_pixels", "rgb_x": rgb_x, "r": pixels[0].tolist(), "g": pixels[1].tolist(), "b": pixels[2].tolist()})
                if msg.data == 'close':
                    await ws.close()
            elif msg.type == aiohttp.WSMsgType.ERROR:
                _LOGGER.error(('Client websocket exception: {}').format(ws.exception()))

        return ws

    async def set_effect(self, request):
        device_id = request.match_info['device_id']
        device = self.ledfx.devices.get_device(device_id)

        data = await request.post()
        try:
            name = data['effect']
            config = json.loads(data['effect_config'])
        except (KeyError, TypeError, ValueError) as e:
            raise web.HTTPBadRequest(
                text='You have not specified effect value') from e
        
        if name == "" or name is None:
            device.clear_effect()
        else:
            effect = self.ledfx.effects.create(name = name, config = config)
            device.set_effect(effect)

        return web.HTTPOk()

    def register_routes(self):
        self.app.router.add_get('/', self.index, name='index')
        self.app.router.add_get('/device/{device_id}', self.device, name='device')
        self.app.router.add_post('/device/{device_id}/effect', self.set_effect, name='set_effect')
        self.app.add_routes([web.get('/device/{device_id}/ws', self.websocket_handler)])

        
        self.app.router.add_get('/dev_tools', self.dev_tools, name='dev_tools')

        self.app.router.add_static('/static/',
                        path=PROJECT_ROOT / 'frontend',
                        name='static')

        self.api.register_routes(self.app)

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