import logging

from numpy import zeros
from pydantic import Field

import ledfx.devices.launchpad_lib as launchpad
from ledfx.configuration.fields import X_REQUIRED
from ledfx.configuration.plugin import TypedConfig
from ledfx.devices import MidiDevice

# import timeit


_LOGGER = logging.getLogger(__name__)

launchpads = [
    {
        "name": "Launchpad Mk2",
        "search": "mk2",
        "number": 0,
        "class": launchpad.LaunchpadMk2(),
    },
    {
        "name": "Launchpad Mini Mk3",
        "search": "minimk3",
        "number": 1,
        "class": launchpad.LaunchpadMiniMk3(),
    },
    {
        "name": "Launchpad Pro Mk3",
        "search": "promk3",
        "number": 0,
        "class": launchpad.LaunchpadProMk3(),
    },
    {
        "name": "Launchpad Pro",
        "search": "pad pro",
        "number": 0,
        "class": launchpad.LaunchpadPro(),
    },
    {
        "name": "Launchpad X",
        "search": "launchpad X",
        "number": 1,
        "class": launchpad.LaunchpadLPX(),
    },
    {
        "name": "Launchpad X",
        "search": "LPX",
        "number": 1,
        "class": launchpad.LaunchpadLPX(),
    },
    {
        "name": "Launchpad S",
        "search": "Launchpad S",
        "number": 0,
        "class": launchpad.LaunchpadS(),
    },
]


def find_launchpad() -> dict:
    lp = launchpad.LaunchpadBase()
    for pad in launchpads:
        _LOGGER.info(
            "Searching for %s on %s with %s",
            pad["name"],
            pad["number"],
            pad["search"],
        )
        if lp.Check(pad["number"], pad["search"]):
            lp = pad["class"]
            result = lp.layout
            result["name"] = pad["name"]
            result["segments"] = lp.segments
            return result
    return None


def dump_methods(instance):
    # List the class's methods
    _LOGGER.debug(" - Available methods:")
    for mName in sorted(dir(instance)):
        if mName.find("__") >= 0:
            continue

        if callable(getattr(instance, mName)):
            _LOGGER.debug("     %s()", mName)


class LaunchpadDevice(MidiDevice):
    """Launchpad device support"""

    class Config(MidiDevice.Config):
        pixel_count: int = Field(
            81,
            description="Number of individual pixels",
            ge=1,
            json_schema_extra={X_REQUIRED: True},
        )
        rows: int = Field(
            9,
            description="Number of individual rows",
            ge=1,
            json_schema_extra={X_REQUIRED: True},
        )
        icon_name: str = Field("launchpad", description="Icon for the device*")
        create_segments: bool = Field(
            False, description="Auto-Generate a virtual for each segments"
        )
        alpha_options: bool = Field(
            False, description="Dark and dangerous features of the damned"
        )
        diag: bool = Field(False, description="enable timing diagnostics in logger")

    config = TypedConfig(Config)

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.lp = None
        self.lp_name = "unknown"
        self._device_type = "Launchpad"
        _LOGGER.info("Launchpad device created")

    def flush(self, data):
        success = self.lp.flush(data, self.config.alpha_options, self.config.diag)
        if not success:
            _LOGGER.warning(
                "Error in Launchpad %s flush, setting offline", self.lp_name
            )
            self.set_offline()

    def activate(self):
        with self._output_lock:
            self.set_class()
            if self.lp is not None:
                if self.lp.supported:
                    self._online = True
                    super().activate()
                else:
                    _LOGGER.warning("Launchpad variant not supported or not connected")
                    self.set_offline()
            else:
                self.set_offline()

    def set_class(self):
        self.lp = launchpad.Launchpad()
        self.lp_name = self.validate_launchpad()

        if self.lp_name is None:
            _LOGGER.warning(
                "Launchpad validation failed class: %s",
                self.lp.__class__.__name__,
            )
            self.lp = None
        else:
            _LOGGER.info(
                "Launchpad %s device class: %s",
                self.lp_name,
                self.lp.__class__.__name__,
            )

    def deactivate(self):
        with self._output_lock:
            _LOGGER.info("Deactivating Launchpad")
            if self.lp is not None:
                self.lp.flush(
                    zeros((self.pixel_count, 3)),
                    self.config.alpha_options,
                    self.config.diag,
                )
                _LOGGER.info("Closing Launchpad")
                self.lp.Close()
                self.lp = None
            super().deactivate()

    async def add_postamble(self):
        _LOGGER.info("Doing post creation things")
        if self.config.create_segments:
            if self.lp is None:
                self.set_class()
            if self.lp is None:
                _LOGGER.warning("No Launchpad available, not creating segments")
            elif len(self.lp.segments) == 0:
                _LOGGER.warning("No segments defined in %s", self.lp.__class__.__name__)
            else:
                for segment in self.lp.segments:
                    self.sub_v(segment[0], segment[1], segment[2], segment[3])

    def validate_launchpad(self) -> str:
        for pad in launchpads:
            _LOGGER.info(
                "Validating %s on %s with %s",
                pad["name"],
                pad["number"],
                pad["search"],
            )

            if self.lp.Check(pad["number"], pad["search"]):
                self.lp = pad["class"]
                if self.lp.Open(pad["number"], pad["search"]):
                    _LOGGER.info(" - %s: OK", pad["name"])
                    return pad["name"]
                else:
                    _LOGGER.error(" - %s: ERROR", pad["name"])
                    return None
        _LOGGER.warning(" validate - No Launchpad available")
        return None
