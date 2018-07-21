import asyncio
import logging
import sys
import json
import yaml
import threading
from pathlib import Path
import voluptuous as vol
from concurrent.futures import ThreadPoolExecutor
from ledfxcontroller.utils import async_fire_and_forget
from ledfxcontroller.http import LedFxControllerHTTP
from ledfxcontroller.devices import Devices
from ledfxcontroller.effects import Effects
from ledfxcontroller.config import load_config, save_config

_LOGGER = logging.getLogger(__name__)

class LedFxController(object):

    def __init__(self, config_dir):
        self.config_dir = config_dir
        self.config = load_config(config_dir)

        if sys.platform == 'win32':
            self.loop = asyncio.ProactorEventLoop()
        else:
            self.loop = asyncio.get_event_loop()
        executor_opts = {'max_workers': self.config.get('max_workers')}

        self.executor = ThreadPoolExecutor(**executor_opts)
        self.loop.set_default_executor(self.executor)
        self.loop.set_exception_handler(self.loop_exception_handler)

        self.http = LedFxControllerHTTP(ledfx = self,
            host = self.config['host'], 
            port = self.config['port'])
        self.exit_code = None


    def loop_exception_handler(self, loop, context):
        kwargs = {}
        exception = context.get('exception')
        if exception:
            kwargs['exc_info'] = (type(exception), exception,
                                exception.__traceback__)

        _LOGGER.error('Exception in core event loop: {}'.format(
            context['message']), **kwargs)

    async def flush_loop(self):
        await asyncio.sleep(0, loop=self.loop)

    def start(self, open_ui = False):
        async_fire_and_forget(
            self.async_start(open_ui = open_ui), self.loop)

        try:
            self.loop.run_forever()
        except KeyboardInterrupt:
            self.loop.call_soon_threadsafe(
                self.loop.create_task, self.async_stop())
            self.loop.run_forever()
        finally:
            self.loop.close()
        return self.exit_code

    async def async_start(self, open_ui = False):
        _LOGGER.info("Starting LedFxController")
        await self.http.start()

        self.devices = Devices(self)
        self.devices.create_from_config(self.config['devices'])
        self.effects = Effects(self)

        if open_ui:
            import webbrowser
            webbrowser.open(self.http.base_url)

        await self.flush_loop()

    def stop(self, exit_code=0):
        async_fire_and_forget(self.async_stop(exit_code), self.loop)

    async def async_stop(self, exit_code=0):
        print('Stopping LedFxController.')
        await self.http.stop()
        self.devices.clear_all_effects()

        # Save the configuration before shutting down
        save_config(config = self.config, config_dir = self.config_dir)

        await self.flush_loop()
        self.executor.shutdown()
        self.exit_code = exit_code
        self.loop.stop()