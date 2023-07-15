import logging

import voluptuous as vol
from numpy import zeros

import ledfx.devices.launchpad_lib as launchpad
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
        "name": "Launchpad Pro",
        "search": "pad pro",
        "number": 0,
        "class": launchpad.LaunchpadPro(),
    },
    {
        "name": "Launchpad Pro Mk3",
        "search": "promk3",
        "number": 0,
        "class": launchpad.LaunchpadProMk3(),
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
            f"Searching for {pad['name']} on {pad['number']} with {pad['search']}"
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
            _LOGGER.debug(f"     {mName}()")


class LaunchpadDevice(MidiDevice):
    """Launchpad device support"""

    @staticmethod
    @property
    def CONFIG_SCHEMA():
        return vol.Schema(
            {
                vol.Required(
                    "pixel_count",
                    description="Number of individual pixels",
                    default=81,
                ): vol.All(int, vol.Range(min=1)),
                vol.Required(
                    "rows",
                    description="Number of individual rows",
                    default=9,
                ): vol.All(int, vol.Range(min=1)),
                vol.Optional(
                    "icon_name",
                    description="Icon for the device*",
                    default="launchpad",
                ): str,
                vol.Optional(
                    "create_segments",
                    description="Auto-Generate a virtual for each segments",
                    default=False,
                ): bool,
                vol.Optional(
                    "Alpha",
                    description="Dark and dangerous features of the damned",
                    default=False,
                ): bool,
                vol.Optional(
                    "Diagnostic",
                    description="enable timing diagnostics in logger",
                    default=False,
                ): bool,
            }
        )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.lp = None
        _LOGGER.info("Launchpad device created")

    def flush(self, data):
        self.lp.flush(data, self._config["Alpha"], self._config["Diagnostic"])

    def activate(self):
        self.set_class()
        super().activate()

    def set_class(self):
        self.lp = launchpad.Launchpad()
        self.validate_launchpad()
        _LOGGER.info(f"Launchpad device class: {self.lp.__class__.__name__}")

    def deactivate(self):
        self.lp.flush(
            zeros((self.pixel_count, 3)),
            self._config["Alpha"],
            self._config["Diagnostic"],
        )
        self.lp.Close()
        self.lp = None
        super().deactivate()

    async def add_postamble(self):
        _LOGGER.info("Doing post creation things")
        if self.config["create_segments"]:
            if self.lp is None:
                self.set_class()
            if len(self.lp.segments) == 0:
                _LOGGER.warning(
                    "No segments defined in {self.lp.__class__.__name__}"
                )
            else:
                for segment in self.lp.segments:
                    self.sub_v(segment[0], segment[1], segment[2], segment[3])

    def validate_launchpad(self) -> str:
        for pad in launchpads:
            _LOGGER.info(
                f"Validating {pad['name']} on {pad['number']} with {pad['search']}"
            )

            if self.lp.Check(pad["number"], pad["search"]):
                self.lp = pad["class"]
                if self.lp.Open(pad["number"], pad["search"]):
                    _LOGGER.info(f" - {pad['name']}: OK")
                    return pad["name"]
                else:
                    _LOGGER.error(f" - {pad['name']}: ERROR")
                    return None
        _LOGGER.error(" validate - No Launchpad available")
        return None
