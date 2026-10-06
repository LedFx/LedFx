import logging
import socket
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Literal

import numpy as np
import requests
from ledfx_senders import NanoleafSender
from numpy.typing import NDArray
from pydantic import Field
from requests import ConnectTimeout, ReadTimeout
from typing_extensions import override

from ledfx.configuration.fields import X_OMIT_DEFAULT, X_REQUIRED
from ledfx.configuration.plugin import TypedConfig
from ledfx.devices import NetworkedDevice, resolve_destination

_LOGGER = logging.getLogger(__name__)

LightPanelModel = "NL22"
CanvasModel = "NL29"


class NanoleafDevice(NetworkedDevice):
    """
    Dedicated Nanoleaf device support
    This class fetches its config (px count, etc) from the Nanoleaf device
    at launch, and lets the user choose a sync mode to use.
    """

    class Config(NetworkedDevice.Config):
        ip_address: str = Field(
            description="Hostname or IP address of the device",
            json_schema_extra={X_REQUIRED: True},
        )
        port: int = Field(16021, description="port")
        udp_port: int = Field(60222, description="port")
        auth_token: str | None = Field(
            None, description="Auth token", json_schema_extra={X_OMIT_DEFAULT: True}
        )
        sync_mode: Literal["TCP", "UDP"] = Field(
            "UDP", description="Streaming protocol to Nanoleaf device"
        )

    config = TypedConfig(Config)

    status: dict[int, tuple[int, int, int]]
    _sender: NanoleafSender | None = None

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self._device_type = "Nanoleaf"
        self.status = {}
        self.device_lock = threading.RLock()
        self._generation = 0

    OUTPUT_KEYS = (
        "ip_address",
        "port",
        "auth_token",
        "sync_mode",
        "udp_port",
        "model",
        "pixel_layout",
        "pixel_count",
    )

    @contextmanager
    def _config_update_context(self, config: dict[str, object]) -> Iterator[None]:
        with (
            self._output_lock,
            self.device_lock,
            super()._config_update_context(config),
        ):
            yield

    def config_updated(self, config):
        with self._output_lock, self.device_lock:
            if self._output_changed():
                self._replace_output()
                self._built_settings = self._output_settings()
                super().activate()

    def url(self, token: str | None, destination: str | None = None) -> str:
        return f"http://{destination or self.config.ip_address}:{self.config.port}/api/v1/{token}"

    @override
    async def resolve_address(
        self, success_callback: Callable[[], object] | None = None
    ) -> None:
        with self._output_lock, self.device_lock:
            address, generation = self.config.ip_address, self._generation
        try:
            destination = await resolve_destination(
                self._ledfx.loop, self._ledfx.thread_executor, address
            )
        except ValueError as error:
            with self._output_lock, self.device_lock:
                if generation == self._generation and address == self.config.ip_address:
                    self._online = False
                    _LOGGER.warning("Device %s: %s", self.name, error)
            return
        with self._output_lock, self.device_lock:
            if generation != self._generation or address != self.config.ip_address:
                return
            if self._sender is not None or self._active:
                # Preparing the UDP/REST session may fail. Publish destination
                # and online state only after the replacement succeeds.
                self._replace_output(destination)
            self._destination = destination
            self._online = True
        if success_callback is not None:
            success_callback()

    def setup_subdevice(self):
        self.activate()

    def _replace_output(self, destination: str | None = None) -> None:
        destination = destination or socket.gethostbyname(self.config.ip_address)
        candidate = None
        if self.config.sync_mode == "UDP":
            version = 1 if getattr(self.config, "model") == LightPanelModel else 2  # noqa: B009 - stored extra
            pixel_layout = getattr(self.config, "pixel_layout")  # noqa: B009 - stored extra
            panel_ids = tuple(panel["panelId"] for panel in pixel_layout)
            candidate = NanoleafSender(
                destination=destination,
                port=self.config.udp_port,
                version=version,
                panel_ids=panel_ids,
            )
            try:
                response = requests.put(
                    self.url(self.config.auth_token, destination) + "/effects",
                    json={
                        "write": {
                            "command": "display",
                            "animType": "extControl",
                            "extControlVersion": f"v{version}",
                        }
                    },
                    timeout=2.0,
                )
                if not 200 <= response.status_code < 300:
                    raise OSError(
                        f"Nanoleaf rejected streaming activation: HTTP {response.status_code}"
                    )
            except Exception:
                candidate.close()
                raise
        old = self._sender
        self._sender = candidate
        self._destination = destination
        self._generation += 1
        self.status = {}
        if old is not None:
            old.close()

    def activate(self):
        with self._output_lock, self.device_lock:
            try:
                self._replace_output()
            except (ConnectTimeout, ReadTimeout, OSError) as error:
                _LOGGER.warning("%s activate failure: %s", self.name, error)
                if self._sender is None:
                    self.set_offline()
                return
            super().activate()

    def deactivate(self):
        with self._output_lock, self.device_lock:
            self._generation += 1
            if self._sender is not None:
                self._sender.close()
                self._sender = None
            super().deactivate()

    def write_udp(self, data: NDArray[np.generic]) -> None:
        if self._sender is not None:
            self._sender.send(data)

    def write_tcp(self):
        """Syncs the digital twin's changes to the real Nanoleaf device.

        :returns: True if success, otherwise False
        """
        anim_data = str(len(self.status))

        for key, (r, g, b) in self.status.items():
            anim_data += f" {key!s} 1 {r} {g} {b} 0 0"

        try:
            response = requests.put(
                self.url(self.config.auth_token) + "/effects",
                json={
                    "write": {
                        "command": "display",
                        "animType": "custom",
                        "loop": True,
                        "palette": [],
                        "animData": anim_data,
                    }
                },
                timeout=2.0,
            )
        except (ConnectTimeout, ReadTimeout) as e:
            _LOGGER.warning(
                "%s WriteTCP failure, Is Nanoleaf powered? %s", self.name, e
            )
            self.set_offline()
            return

        if response.status_code == 400:
            _LOGGER.warning("%s Bad Request Response", self.name)
            self.set_offline()
            return

    def flush(self, data):
        with self._output_lock, self.device_lock:
            if self.config.sync_mode == "UDP":
                self.write_udp(data)
                return
            pixel_layout = getattr(self.config, "pixel_layout")  # noqa: B009 - stored extra
            for panel, col in zip(pixel_layout, data.astype(int).clip(0, 255)):
                self.status[panel["panelId"]] = col.tolist()
            if self.config.sync_mode == "TCP":
                self.write_tcp()

    def get_token(self):
        _LOGGER.info("acquiring nanoleaf auth token...")
        response = requests.post(self.url("new"))

        if response and response.status_code == 200:
            data = response.json()
            if "auth_token" in data:
                return data["auth_token"]

        raise Exception("No token, press sync button first")  # noqa: TRY002

    async def async_initialize(self):
        await super().async_initialize()

        auth_token = self.config.auth_token

        if not auth_token:
            auth_token = self.get_token()
            self.update_config({"auth_token": auth_token})

        _LOGGER.info("fetching nanoleaf's device info...")

        nanoleaf_config = requests.get(self.url(self.config.auth_token)).json()  # noqa: ASYNC210

        _LOGGER.debug("nanoleaf config response: %s", nanoleaf_config)

        if "panelLayout" in nanoleaf_config:
            _LOGGER.info("parsing panel layout...")
            panels = [
                {"x": i["x"], "y": i["y"], "panelId": i["panelId"]}
                for i in sorted(
                    nanoleaf_config["panelLayout"]["layout"]["positionData"],
                    key=lambda panel: (panel["x"], panel["y"]),
                )
                if i["panelId"] != 0
            ]
        else:
            # Nanoleaf Matter WiFi Essentials devices (Holiday String Lights,
            # Essentials Lightstrips, Rope Lights, Floor Lamp, WiFi A19, etc.)
            # do not expose panelLayout. Fall back to the /length endpoint
            # to determine pixel count, and address LEDs by simple index.
            _LOGGER.info("no panelLayout found, falling back to /length endpoint...")
            try:
                length_response = requests.get(  # noqa: ASYNC210
                    self.url(self.config.auth_token) + "/length",
                    timeout=2.0,
                ).json()
            except (ConnectTimeout, ReadTimeout) as e:
                raise ValueError(
                    f"{self.name} could not fetch Nanoleaf LED length: {e}"
                ) from e
            num_leds = length_response["numLEDs"]
            panels = [{"x": i, "y": 0, "panelId": i} for i in range(num_leds)]

        config = {
            "name": self.config.name,
            "pixel_count": len(panels),
            "pixel_layout": panels,
            "refresh_rate": 30,  # problems with too fast udp packets
            "model": nanoleaf_config["model"],
        }

        if nanoleaf_config["model"] == LightPanelModel:
            config["udp_port"] = 60221

        self.update_config(config)

        self.setup_subdevice()
