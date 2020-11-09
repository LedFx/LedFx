import asyncio
import logging
import sys
import json
import yaml
import threading
from pathlib import Path
import voluptuous as vol
from concurrent.futures import ThreadPoolExecutor
from ledfx.utils import async_fire_and_forget
from ledfx.http import HttpServer
from ledfx.devices import Devices
from ledfx.effects import Effects
from ledfx.config import load_config, save_config, load_default_presets
from ledfx.events import Events, LedFxShutdownEvent

_LOGGER = logging.getLogger(__name__)


class LedFxCore(object):
    def __init__(self, config_dir, host=None, port=None):
        self.config_dir = config_dir
        self.config = load_config(config_dir)
        self.config["default_presets"] = load_default_presets()
        host = host if host else self.config['host']
        port = port if port else self.config['port']

        if sys.platform == 'win32':
            self.loop = asyncio.ProactorEventLoop()
        else:
            self.loop = asyncio.get_event_loop()
        executor_opts = {'max_workers': self.config.get('max_workers')}

        self.executor = ThreadPoolExecutor(**executor_opts)
        self.loop.set_default_executor(self.executor)
        self.loop.set_exception_handler(self.loop_exception_handler)

        self.events = Events(self)
        self.http = HttpServer(
            ledfx=self, host=host, port=port)
        self.exit_code = None

    def dev_enabled(self):
        return self.config['dev_mode'] == True

    def loop_exception_handler(self, loop, context):
        kwargs = {}
        exception = context.get('exception')
        if exception:
            kwargs['exc_info'] = (type(exception), exception,
                                  exception.__traceback__)

        _LOGGER.error(
            'Exception in core event loop: {}'.format(context['message']),
            **kwargs)

    async def flush_loop(self):
        await asyncio.sleep(0, loop=self.loop)

    def start(self, open_ui=False):
        async_fire_and_forget(self.async_start(open_ui=open_ui), self.loop)

        # Windows does not seem to handle Ctrl+C well so as a workaround
        # register a handler and manually stop the app
        if sys.platform == 'win32':
            import win32api

            def handle_win32_interrupt(sig, func=None):
                self.stop()
                return True

            win32api.SetConsoleCtrlHandler(handle_win32_interrupt, 1)

        try:
            self.loop.run_forever()
        except KeyboardInterrupt:
            self.loop.call_soon_threadsafe(self.loop.create_task,
                                           self.async_stop())
            self.loop.run_forever()
        except:
            # Catch all other exceptions and terminate the application. The loop
            # exeception handler will take care of logging the actual error and
            # LedFx will cleanly shutdown.
            self.loop.run_until_complete(self.async_stop(exit_code = -1))
            pass
        finally:
            self.loop.stop()
        return self.exit_code

    async def async_start(self, open_ui=False):
        _LOGGER.info("Starting ledfx")
        await self.http.start()

        self.devices = Devices(self)
        self.effects = Effects(self)

        # TODO: Deferr
        self.devices.create_from_config(self.config['devices'])

        # TODO: This step blocks for 1.5 secs while searching for devices. 
        # It needs a callback in 3-5 seconds to kill the zeroconf browser, which is
        # implemented using a blocking time.sleep 
        if not self.devices.values():
            _LOGGER.info("No devices saved in config.")
            async_fire_and_forget(self.devices.find_wled_devices(), self.loop)

        if open_ui:
            import webbrowser
            webbrowser.open(self.http.base_url)

        await self.flush_loop()

    def stop(self, exit_code=0):
        async_fire_and_forget(self.async_stop(exit_code), self.loop)

    async def async_stop(self, exit_code=0):
        if not self.loop:
            return

        print('Stopping LedFx.')

        # Fire a shutdown event and flush the loop
        self.events.fire_event(LedFxShutdownEvent())
        await asyncio.sleep(0, loop=self.loop)

        await self.http.stop()

        # Cancel all the remaining task and wait

        
        tasks = [task for task in asyncio.all_tasks() if task is not
             asyncio.current_task()] 
        list(map(lambda task: task.cancel(), tasks))
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Save the configuration before shutting down
        save_config(config=self.config, config_dir=self.config_dir)

        await self.flush_loop()
        self.executor.shutdown()
        self.exit_code = exit_code
        self.loop.stop()
