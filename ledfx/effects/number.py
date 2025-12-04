import logging
import numpy as np
import voluptuous as vol
from PIL import ImageFont
from datetime import datetime
from ledfx.effects.texter2d import Texter2d
from ledfx.effects.utils.words import FONT_MAPPINGS, Sentence
from ledfx.utils import Teleplot

_LOGGER = logging.getLogger(__name__)


class Number(Texter2d):
    """
    Display a numeric value at maximum text size on a matrix for diagnostic purposes.

    This effect inherits from Texter2d and automatically formats and displays a numeric
    value at the largest possible size that fits on the matrix. The text updates every
    render frame to show real-time diagnostic information.

    The display value can be set externally by modifying self.display_value.
    """

    NAME = "Number"
    CATEGORY = "Diagnostic"

    # Mapping of display value options to their respective update methods
    VALUE_SOURCE_MAPPING = {
        "BPM": "update_bpm",
        "BPM Confidence": "update_bpm_confidence",
        "Time (HH:MM)": "update_time_hhmm",
        "Time (HH:MM:SS)": "update_time_hhmmss",
    }

    # Hide parent effect-specific options that don't apply to numeric display
    HIDDEN_KEYS = Texter2d.HIDDEN_KEYS + [
        "text",
        "text_effect",
        "option_1",
        "option_2",
        "value_option_1",
        "speed_option_1",
        "alpha",
        "use_gradient",
        "impulse_decay",
        "multiplier",
        "gradient_roll",
        "height_percent",
        "gradient",
    ]

    ADVANCED_KEYS = Texter2d.ADVANCED_KEYS + [
        "resize_method",
        "font",
        "text_color",
        "background_brightness",
        "background_mode",
        "background_color",
    ]

    CONFIG_SCHEMA = vol.Schema(
        {
            **Texter2d.CONFIG_SCHEMA.schema,  # Inherit parent schema
            vol.Optional(
                "value_source",
                description="Source of the value to display",
                default=list(VALUE_SOURCE_MAPPING.keys())[0],
            ): vol.In(list(VALUE_SOURCE_MAPPING.keys())),
            vol.Optional(
                "whole_digits",
                description="Number of digits to reserve before decimal point (for stable text size)",
                default=3,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
            vol.Optional(
                "decimal_digits",
                description="Number of digits to display after decimal point (for stable text size)",
                default=2,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=6)),
            vol.Optional(
                "negative",
                description="Support negative values (include negative sign in sizing)",
                default=False,
            ): bool,
        },
    )

    def __init__(self, ledfx, config):
        # Initialize display value that can be set externally
        self.display_value = 0.0
        # Force speed_option_1 to 0 for centered display
        config["speed_option_1"] = 0
        super().__init__(ledfx, config)

    def config_updated(self, config):
        """Update configuration and regenerate sentence with formatted number."""
        super().config_updated(config)

        self.digits_before = self._config.get("whole_digits", 3)
        self.digits_after = self._config.get("decimal_digits", 2)
        self.negative = self._config.get("negative", False)

        self.value_update_method = self.VALUE_SOURCE_MAPPING[
            self._config["value_source"]
        ]
        self.is_time_hhmm = self._config["value_source"] == "Time (HH:MM)"
        self.is_time_hhmmss = self._config["value_source"] == "Time (HH:MM:SS)"
        
    def update_time_hhmm(self, data=None):
        """Update display value with current time as HH:MM string."""
        self.display_value = datetime.now().strftime("%H:%M")

    def update_time_hhmmss(self, data=None):
        """Update display value with current time as HH:MM:SS string."""
        self.display_value = datetime.now().strftime("%H:%M:%S")


    def audio_data_updated(self, data):
        """
        Update display value based on audio data.

        Calls the configured value update method to populate self.display_value.
        """
        # Call the selected update method to populate display_value
        getattr(self, self.value_update_method)(data)

    def update_bpm(self, data):
        """Update display value with current BPM."""
        self.display_value = data._tempo.get_bpm()
        Teleplot.send(f"BPM:{self.display_value}")

    def update_bpm_confidence(self, data):
        """Update display value with BPM detection confidence."""
        self.display_value = data._tempo.get_confidence()
        if not np.isnan(self.display_value):
            Teleplot.send(f"BPM_Conf:{self.display_value:.3f}")
        else:
            _LOGGER.error("BPM Confidence: NaN")

    def _format_number(self, value, digits_before, digits_after):
        """
        Format a number or time string for display.
        Handles negative sign and overflow pattern.
        """
        if self.is_time_hhmm:
            return value if isinstance(value, str) else str(value)
        if self.is_time_hhmmss:
            return value if isinstance(value, str) else str(value)

        negative = value < 0
        if self.negative and negative:
            # Reserve space for sign
            format_str = self._number_format_string(digits_before - 1, digits_after)
            try:
                formatted = format_str.format(abs(value))
            except (ValueError, OverflowError):
                if digits_after > 0:
                    formatted = "#" * (digits_before - 1 + 1 + digits_after)
                else:
                    formatted = "#" * (digits_before - 1)
            # Prepend '-' unless overflow pattern
            if formatted and formatted[0] == '#':
                formatted = '-' + formatted
            else:
                formatted = '-' + formatted
        else:
            format_str = self._number_format_string(digits_before, digits_after)
            try:
                formatted = format_str.format(abs(value))
            except (ValueError, OverflowError):
                if digits_after > 0:
                    formatted = "#" * (digits_before + 1 + digits_after)
                else:
                    formatted = "#" * digits_before
        return formatted

    @staticmethod
    def _number_format_string(digits_before, digits_after):
        """
        Return a format string for a number with the given digit configuration.
        """
        if digits_after > 0:
            total_width = (
                digits_before + 1 + digits_after
            )  # +1 for decimal point
            return f"{{:0{total_width}.{digits_after}f}}"
        else:
            return f"{{:0{digits_before}.0f}}"

    def _calculate_font_size(self):
        """
        Calculate optimal font size for either number or time string.
        """
        if self.is_time_hhmm:
            template_text = "88:88"  # Widest possible HH:MM
        elif self.is_time_hhmmss:
            template_text = "88:88:88"  # Widest possible HH:MM:SS
        else:
            if self.digits_after > 0:
                template_value = float(
                    "9" * self.digits_before + "." + "9" * self.digits_after
                )
            else:
                template_value = float("9" * self.digits_before)
            template_text = self._number_format_string(
                self.digits_before, self.digits_after
            ).format(template_value)
            if self.negative:
                template_text = "-" + template_text

        target_height = round(
            self.r_height * self._config["height_percent"] / 100
        )
        min_size = 4
        max_size = target_height
        best_size = min_size
        font_path = FONT_MAPPINGS[self._config["font"]]
        for size in range(max_size, min_size - 1, -1):
            try:
                font = ImageFont.truetype(font_path, size)
                bbox = font.getbbox(template_text)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                if text_width <= self.r_width and text_height <= self.r_height:
                    best_size = size
                    break
            except Exception:
                continue
        return best_size

    def do_once(self):
        """Initialize the sentence object with initial formatted number."""
        # Update text before sentence creation
        self._config["text"] = self._format_number(
            self.display_value, self.digits_before, self.digits_after
        )
        # Call parent do_once which creates the sentence
        super().do_once()
        # Calculate and store the optimal font size for the configured digits
        self._font_size = self._calculate_font_size()
        # Recreate the sentence with the optimal font size
        self.sentence = Sentence(
            self._config["text"],
            self._config["font"],
            self._font_size,
            (self.r_width, self.r_height),
        )
        # Re-initialize positioning for centered display
        self.side_scroll_init()

    def draw(self):
        """
        Draw the numeric display. Updates the text and sentence if the value changed.
        Also updates time value every frame if time mode is selected.
        """
        # Update time value every frame if time mode is selected
        if self.is_time_hhmm:
            self.update_time_hhmm()
        elif self.is_time_hhmmss:
            self.update_time_hhmmss()

        new_text = self._format_number(
            self.display_value, self.digits_before, self.digits_after
        )
        if new_text != self._config["text"]:
            self._config["text"] = new_text
            self.sentence = Sentence(
                self._config["text"],
                self._config["font"],
                self._font_size,
                (self.r_width, self.r_height),
            )
            self.side_scroll_init()
        super().draw()


# Example of how to use this effect with custom values:
#
# To display a custom diagnostic value:
# 1. Get a reference to the effect instance
# 2. Set effect.display_value to your diagnostic value
# 3. The value will be displayed on the next render frame
#
# Example:
#   effect = virtual.active_effect
#   if isinstance(effect, Number):
#       effect.display_value = my_diagnostic_value
