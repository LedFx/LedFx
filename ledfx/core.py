import asyncio
import logging
import sys
import time
import warnings
import webbrowser
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pybase64

from ledfx.color import (
    LEDFX_COLORS,
    LEDFX_GRADIENTS,
    parse_color,
    parse_gradient,
    validate_color,
    validate_gradient,
)
from ledfx.config import (
    VISUALISATION_CONFIG_KEYS,
    Transmission,
    create_backup,
    get_ssl_certs,
    load_config,
    remove_virtuals_active_effects,
    save_config,
)
from ledfx.devices import Devices
from ledfx.effects import Effects
from ledfx.effects.math import interpolate_pixels
from ledfx.events import (
    Event,
    Events,
    LedFxShutdownEvent,
    VisualisationUpdateEvent,
)
from ledfx.http_manager import HttpServer
from ledfx.integrations import Integrations
from ledfx.mdns_manager import ZeroConfRunner
from ledfx.presets import ledfx_presets
from ledfx.scenes import Scenes
from ledfx.utils import (
    RollingQueueHandler,
    UserDefaultCollection,
    async_fire_and_forget,
    currently_frozen,
)
from ledfx.virtuals import Virtuals

_LOGGER = logging.getLogger(__name__)

if currently_frozen():
    warnings.filterwarnings("ignore")


class LedFxCore:

    EXIT_CODES = {
        1: "LedFx encountered an error - Shutting down.",
        2: "Keyboard interrupt - Shutting down.",
        3: "Shutdown request via API - Shutting down.",
        4: "Restart request via API - Restarting.",
        5: "Shutdown request via CI testing flag - Shutting down.",
    }

    def __init__(
        self,
        config_dir,
        host=None,
        port=None,
        port_s=None,
        icon=None,
        ci_testing=False,
        clear_config=False,
        clear_effects=False,
    ):

        self.icon = icon
        self.config_dir = config_dir

        if clear_config:
            _LOGGER.warning("Clearing LedFx config.")
            create_backup(config_dir, "DELETE")

        self.config = load_config(config_dir)

        if clear_effects:
            _LOGGER.warning("Clearing active effects.")
            remove_virtuals_active_effects(self.config)

        self.config["ledfx_presets"] = ledfx_presets
        self.host = host if host else self.config["host"]
        self.port = port if port else self.config["port"]
        self.port_s = port_s if port_s else self.config["port_s"]
        self.ci_testing = ci_testing

        if sys.platform == "win32":
            self.loop = asyncio.ProactorEventLoop()
        else:
            try:
                import uvloop

                self.loop = uvloop.new_event_loop()
                _LOGGER.info("Using uvloop for asyncio loop")
            except ImportError as error:
                self.loop = asyncio.get_event_loop()
                _LOGGER.info("Reverting to asyncio loop")
        asyncio.set_event_loop(self.loop)

        # self.loop.set_debug(True)

        self.thread_executor = ThreadPoolExecutor()
        self.loop.set_default_executor(self.thread_executor)
        self.loop.set_exception_handler(self.loop_exception_handler)

        if self.icon:
            self.setup_icon_menu()

        self.setup_logqueue()
        self.events = Events(self)
        self.setup_visualisation_events()
        self.events.add_listener(
            self.handle_base_configuration_update, Event.BASE_CONFIG_UPDATE
        )
        self.http = HttpServer(
            ledfx=self, host=self.host, port=self.port, port_s=self.port_s
        )
        self.exit_code = None

    def handle_base_configuration_update(self, event):
        """
        Handles the update of the base configuration where there are specific things that need to be done.

        Currently, only visualisation configuration is handled this way, since they require the creation of new event listeners.

        Args:
            event (Event): The event that triggered the update - this will always be a BaseConfigUpdateEvent.
        """

        if any(key in self.config for key in VISUALISATION_CONFIG_KEYS):
            self.setup_visualisation_events()

    def dev_enabled(self):
        return self.config["dev_mode"]

    def loop_exception_handler(self, loop, context):
        kwargs = {}
        exception = context.get("exception")
        if exception:
            kwargs["exc_info"] = (
                type(exception),
                exception,
                exception.__traceback__,
            )

        _LOGGER.error(
            "Exception in core event loop: {}".format(context["message"]),
            **kwargs,
        )

    def open_ui(self):
        # Check if we're binding to all adaptors
        if str(self.config["host"]) == "0.0.0.0":
            url = f"http://127.0.0.1:{str(self.port)}"
        else:
            # If the user has specified an adaptor, launch its address
            url = self.http.base_url
        try:
            webbrowser.get().open(url)
        except webbrowser.Error:
            _LOGGER.warning(
                f"Failed to open default web browser. To access LedFx's web ui, open {url} in your browser."
            )

    def setup_icon_menu(self):
        import pystray

        self.icon.menu = pystray.Menu(
            pystray.MenuItem("Open", self.open_ui, default=True),
            pystray.MenuItem("Quit Ledfx", self.stop),
        )

    def setup_visualisation_events(self):
        """
        creates event listeners to fire visualisation events at
        a given rate
        """
        # Remove existing listeners if they exist
        if hasattr(self, "visualisation_update_listener"):
            self.visualisation_update_listener = None
            self.virtual_listener()
            self.device_listener()

        min_time_since = 1 / self.config["visualisation_fps"]
        time_since_last = {}
        max_len = self.config["visualisation_maxlen"]

        def handle_visualisation_update(event):
            is_device = event.event_type == Event.DEVICE_UPDATE
            time_now = time.time()

            if is_device:
                vis_id = getattr(event, "device_id")
            else:
                vis_id = getattr(event, "virtual_id")

            try:
                time_since = time_now - time_since_last[vis_id]
                if time_since < min_time_since:
                    return
            except KeyError:
                pass

            time_since_last[vis_id] = time_now

            pixels = event.pixels

            if len(pixels) > max_len:
                pixels = interpolate_pixels(pixels, max_len)

            if (
                self.config["transmission_mode"]
                == Transmission.BASE64_COMPRESSED
            ):
                b_arr = bytes(pixels.astype(np.uint8).flatten())
                pixels = pybase64.b64encode(b_arr).decode("ASCII")
            else:
                pixels = pixels.astype(np.uint8).T.tolist()

            self.events.fire_event(
                VisualisationUpdateEvent(is_device, vis_id, pixels)
            )

        self.visualisation_update_listener = handle_visualisation_update
        self.virtual_listener = self.events.add_listener(
            self.visualisation_update_listener,
            Event.VIRTUAL_UPDATE,
        )
        self.device_listener = self.events.add_listener(
            self.visualisation_update_listener,
            Event.DEVICE_UPDATE,
        )

    def setup_logqueue(self):
        def log_filter(record):
            return (record.name != "ledfx.api.log") and (record.levelno >= 20)

        self.logqueue = asyncio.Queue(maxsize=100)
        logqueue_handler = RollingQueueHandler(self.logqueue)
        logqueue_handler.addFilter(log_filter)
        root_logger = logging.getLogger()
        root_logger.addHandler(logqueue_handler)

    def start(self, open_ui=False):
        async_fire_and_forget(self.async_start(open_ui=open_ui), self.loop)

        try:
            self.loop.run_forever()
        except KeyboardInterrupt:
            self.loop.call_soon(
                self.loop.create_task, self.async_stop(exit_code=2)
            )
            self.loop.run_forever()
        except BaseException:
            # Catch all other exceptions and terminate the application. The loop
            # exception handler will take care of logging the actual error and
            # LedFx will cleanly shutdown.
            self.loop.run_until_complete(self.async_stop(exit_code=1))
            pass
        finally:
            self.loop.stop()

        return self.exit_code

    async def async_start(self, open_ui=False):
        _LOGGER.info(f"Starting LedFx, listening on {self.host}:{self.port}")

        await self.http.start(get_ssl_certs(config_dir=self.config_dir))
        if (
            self.icon is not None
            and self.icon.notify is not None
            and self.icon.HAS_NOTIFICATION
        ):
            self.icon.notify(
                "Started in background.\nUse the tray icon to open.", "LedFx"
            )
        self.devices = Devices(self)
        self.effects = Effects(self)
        self.virtuals = Virtuals(self)
        self.integrations = Integrations(self)
        self.scenes = Scenes(self)
        self.colors = UserDefaultCollection(
            self,
            "Colors",
            LEDFX_COLORS,
            "user_colors",
            validate_color,
            parse_color,
        )
        self.gradients = UserDefaultCollection(
            self,
            "Gradients",
            LEDFX_GRADIENTS,
            "user_gradients",
            validate_gradient,
            parse_gradient,
        )

        # TODO: Deferr
        self.devices.create_from_config(self.config["devices"])
        await self.devices.async_initialize_devices()

        self.zeroconf = ZeroConfRunner(ledfx=self)
        self.virtuals.create_from_config(self.config["virtuals"])
        self.integrations.create_from_config(self.config["integrations"])

        if self.config["scan_on_startup"]:
            async_fire_and_forget(
                self.zeroconf.discover_wled_devices(), self.loop
            )

        async_fire_and_forget(
            self.integrations.activate_integrations(), self.loop
        )

        if open_ui:
            self.open_ui()

        if self.ci_testing:
            await asyncio.sleep(5)
            self.stop(5)

    def stop(self, exit_code):
        async_fire_and_forget(self.async_stop(exit_code), self.loop)

    async def async_stop(self, exit_code):
        if not self.loop:
            return

        print("Stopping LedFx.")
        try:
            _LOGGER.info(self.EXIT_CODES.get(exit_code, "Unknown exit code."))
            # Fire a shutdown event
            self.events.fire_event(LedFxShutdownEvent())
            _LOGGER.info("Stopping HTTP Server...")
            await self.http.stop()

            # Cancel all the remaining task and wait
            tasks = [
                task
                for task in asyncio.all_tasks()
                if task is not asyncio.current_task()
            ]
            if tasks:
                _LOGGER.debug(
                    f"Killing {len(tasks)} tasks prior to shutdown..."
                )
                # Cancel all tasks concurrently
                group = asyncio.gather(*tasks, return_exceptions=True)
                group.cancel()
                # Wait for all tasks to be cancelled
                try:
                    await group
                except asyncio.CancelledError:
                    pass
                _LOGGER.debug("All tasks killed.")
            # Save the configuration before shutting down
            save_config(config=self.config, config_dir=self.config_dir)

        except Exception as e:
            _LOGGER.error(f"An error occurred while stopping: {e}")
            self.exit_code = 1

        finally:
            self.thread_executor.shutdown()
            # Don't overwrite error exit code
            if self.exit_code != 1:
                self.exit_code = exit_code
            self.loop.stop()
            return exit_code
