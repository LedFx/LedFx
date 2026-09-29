import timeit
from typing import ClassVar

import numpy as np
from pydantic import Field

from ledfx.color import parse_color
from ledfx.configuration.fields import CoercedFloat, CoercedInt, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.utils import Graph

try:
    import bokeh  # noqa: F401

    bokeh_available = True
except ImportError:
    bokeh_available = False

try:
    import psutil

    psutil_available = True
except ImportError:
    psutil_available = False

# Metro intent is to flash a pattern on led strips so end users can look for
# sync between separate light strips due to protocol, wifi conditions or other
# Best configured as a copy virtual across mutliple devices, however uses a
# common derived time base and step count so that seperate devices / virtuals
# with common configurations will be in sync


class MetroEffect(AudioReactiveEffect):
    NAME = "Metro"
    CATEGORY = "Diagnostic"
    HIDDEN_KEYS: ClassVar[list[str]] = ["background_brightness", "blur", "mirror"]
    if not bokeh_available or not psutil_available:
        HIDDEN_KEYS.append("capture")

    start_time = timeit.default_timer()

    class Config(AudioReactiveEffect.Config):
        pulse_period: CoercedInt = Field(
            1, description="Time between flash in seconds", ge=1, le=10
        )
        pulse_ratio: CoercedFloat = Field(
            0.3, description="Flash to blank ratio", ge=0.1, le=0.9
        )
        steps: CoercedInt = Field(
            4, description="Steps of pattern division to loop", ge=1, le=6
        )
        background_color: Color = Field("#000000", description="Background color")
        flash_color: Color = Field("#FFFFFF", description="Flash color")
        capture: bool = Field(
            True, description="graph capture, on to start, off to dump"
        )
        cpu_secs: CoercedFloat = Field(
            1.0, description="Window over which to measure CPU usage", ge=0.1, le=1.0
        )

    config = TypedConfig(Config)

    def __init__(self, ledfx, config):
        self.was_flash = False
        self.graph_callbacks = None
        self.graph_cpu = None
        self.cores = 0
        self.last_cpu = 0.0
        super().__init__(ledfx, config.with_values(capture=False))

    def on_activate(self, pixel_count):
        pass

    def config_updated(self, config):
        self.background_color = np.array(
            parse_color(self.config.background_color), dtype=float
        )
        self.flash_color = np.array(parse_color(self.config.flash_color), dtype=float)

        self.cycle_threshold = self.config.pulse_period * (self.config.pulse_ratio)
        if self.config.capture and self.graph_callbacks is None:
            # start a capture sequence, generate base graphs
            self.graph_callbacks = Graph(
                "Metro Callback Timing", ["Audio", "Render"], points=5000
            )
            self.cores = psutil.cpu_count()
            # zero the local timer and prime cpu measurement
            self.last_cpu = timeit.default_timer()
            psutil.cpu_percent(percpu=True)
            cpu_keys = [f"CPU {i}" for i in range(self.cores)]
            self.graph_cpu = Graph(
                "Metro CPU Usage",
                cpu_keys,
                points=1000,
                y_title="CPU %",
                y_axis_max=100.0,
            )
        elif not self.config.capture and self.graph_callbacks is not None:
            self.graph_callbacks.dump_graph(only_jitter=True)
            with self.lock:
                if self.graph_cpu:
                    self.graph_cpu.dump_graph(
                        jitter=True,
                        sub_title=f"{self.config.cpu_secs} secs",
                    )
            self.graph_callbacks = None
            self.graph_cpu = None

        if self.graph_callbacks:
            # Y value does not matter as we are only looking at jitter
            self.graph_callbacks.append_tag("Config Update", 10.0)

    def audio_data_updated(self, data):
        if self.graph_callbacks is not None:
            # value does not matter as we are only looking at jitter
            self.graph_callbacks.append_by_key("Audio", 1.0)

    def render(self):
        now = timeit.default_timer()
        if self.graph_callbacks is not None:
            # value does not matter as we are only looking at jitter
            self.graph_callbacks.append_by_key("Render", 1.0)

        pass_time = now - self.start_time
        cycle_time = pass_time % self.config.pulse_period

        if cycle_time > self.cycle_threshold:
            if self.was_flash:
                self.pixels[0 : self.pixel_count] = self.background_color
                self.was_flash = False
        else:
            if not self.was_flash:
                step_count = (
                    int(pass_time / self.config.pulse_period) % self.config.steps
                )
                if step_count == 0:
                    self.pixels[0 : self.pixel_count] = self.flash_color
                else:
                    step_div = pow(2, step_count - 1)
                    chunk = int(self.pixel_count / (step_div))
                    for blocks in range(step_div):
                        start_pixel = blocks * chunk
                        end_pixel = start_pixel + int(chunk / 2)
                        self.pixels[start_pixel : end_pixel - 1] = self.flash_color
                self.was_flash = True

        if self.graph_cpu is not None and now - self.last_cpu > self.config.cpu_secs:
            cpu = psutil.cpu_percent(percpu=True)
            for i in range(self.cores):
                self.graph_cpu.append_by_key(f"CPU {i}", cpu[i])
            self.last_cpu = now
