"""pydantic models for LedFx configuration."""

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    model_serializer,
    model_validator,
)
from pydantic.fields import ComputedFieldInfo, FieldInfo

from ledfx.configuration.fields import (
    RUNTIME_CONTEXT,
    X_OMIT_DEFAULT,
    X_REQUIRED,
    AudioDeviceIndex,
    CoercedFloat,
    CoercedInt,
    OneOf,
    coerce,
)
from ledfx.utils import generate_title


def _field_title(name: str, _info: FieldInfo | ComputedFieldInfo) -> str:
    return generate_title(name)


def omits_default(info: FieldInfo) -> bool:
    """True for fields that were voluptuous Optional keys without a default."""
    extra = info.json_schema_extra
    return isinstance(extra, dict) and bool(extra.get(X_OMIT_DEFAULT))


class LedFxModel(BaseModel):
    """Base for every config model. Subclasses may override ``extra``."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        validate_default=True,
        field_title_generator=_field_title,
    )

    @model_serializer(mode="wrap")
    def _drop_unset_optionals(self, handler: SerializerFunctionWrapHandler) -> object:
        data = handler(self)
        if isinstance(data, dict):
            for name, info in type(self).model_fields.items():
                if omits_default(info) and data.get(name, 0) is None:
                    del data[name]
        return data


# No return annotation on purpose: pydantic's model_dump() type is kept, so the
# legacy dict sites (audio, melbank, virtual) read values as untyped, as they did
# voluptuous output. Layer 8 replaces those sites with typed models.
def validate_dict(model: type[BaseModel], data: object, *, runtime: bool = False):
    """Validate data (any mapping; anything else is a ValidationError) and
    return a plain dict shaped like voluptuous output."""
    context = RUNTIME_CONTEXT if runtime else None
    return model.model_validate(data, context=context).model_dump()


def _transition_modes() -> list[str]:
    from ledfx.transitions import Transitions

    return list(Transitions)


class AudioInputConfig(LedFxModel):
    model_config = ConfigDict(extra="allow")

    sample_rate: int = 60
    mic_rate: int = 44100
    fft_size: int = 4096
    min_volume: CoercedFloat = Field(0.2, ge=0.0, le=1.0)
    audio_device: AudioDeviceIndex = None
    audio_device_name: str = ""
    delay_ms: CoercedInt = Field(
        0,
        ge=0,
        le=5000,
        description="Add a delay to LedFx's output to sync with your audio. Useful for Bluetooth devices which typically have a short audio lag.",
    )


class AudioAnalysisConfig(LedFxModel):
    model_config = ConfigDict(extra="allow")

    pitch_method: Literal["yinfft", "yin", "yinfast", "schmitt", "specacf"] = Field(
        "yinfft", description="Method to detect pitch"
    )
    tempo_method: str = "default"
    onset_method: Literal[
        "energy",
        "hfc",
        "complex",
        "phase",
        "wphase",
        "specdiff",
        "kl",
        "mkl",
        "specflux",
    ] = Field("hfc", description="Method used to detect onsets")
    pitch_tolerance: CoercedFloat = Field(
        0.8, ge=0.0, le=2, description="Pitch detection tolerance"
    )


class AudioConfig(AudioInputConfig, AudioAnalysisConfig):
    """Persisted audio section: input and analysis settings together."""

    model_config = ConfigDict(extra="allow")


class MelbankConfig(LedFxModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = Field(None, json_schema_extra={X_OMIT_DEFAULT: True})
    min_frequency: CoercedInt = Field(20, ge=20, le=15000)
    max_frequency: CoercedInt = Field(15000, ge=20, le=15000)


class MelbanksConfig(LedFxModel):
    model_config = ConfigDict(extra="allow")

    samples: CoercedInt = Field(24, ge=0, le=100)
    peak_isolation: float = 0.4
    coeffs_type: Literal[
        "matt_mel", "triangle", "bark", "mel", "htk", "scott", "scott_mel"
    ] = "matt_mel"
    max_frequencies: list[Annotated[int, Field(ge=0, le=15000), coerce(int)]] = [
        350,
        2000,
        15000,
    ]
    min_frequency: CoercedInt = Field(20, ge=0, le=15000)


class _WledSetting(LedFxModel):
    """Either key may be omitted, but not sent as null (voluptuous rejected it)."""

    @model_validator(mode="before")
    @classmethod
    def _reject_null(cls, data: object) -> object:
        if isinstance(data, dict) and None in data.values():
            raise ValueError("setting and user_enabled may be omitted, not null")
        return data


class WledStrSetting(_WledSetting):
    setting: str | None = Field(None, json_schema_extra={X_OMIT_DEFAULT: True})
    user_enabled: bool | None = Field(None, json_schema_extra={X_OMIT_DEFAULT: True})


class WledBoolSetting(_WledSetting):
    setting: bool | None = Field(None, json_schema_extra={X_OMIT_DEFAULT: True})
    user_enabled: bool | None = Field(None, json_schema_extra={X_OMIT_DEFAULT: True})


class WledIntSetting(_WledSetting):
    setting: int | None = Field(None, json_schema_extra={X_OMIT_DEFAULT: True})
    user_enabled: bool | None = Field(None, json_schema_extra={X_OMIT_DEFAULT: True})


class WledPreferences(LedFxModel):
    wled_preferred_mode: WledStrSetting = WledStrSetting(
        setting="UDP", user_enabled=False
    )
    realtime_gamma_enabled: WledBoolSetting = WledBoolSetting(
        setting=False, user_enabled=False
    )
    force_max_brightness: WledBoolSetting = WledBoolSetting(
        setting=False, user_enabled=False
    )
    realtime_dmx_mode: WledStrSetting = WledStrSetting(
        setting="MultiRGB", user_enabled=False
    )
    start_universe_setting: WledIntSetting = WledIntSetting(
        setting=1, user_enabled=False
    )
    dmx_address_start: WledIntSetting = WledIntSetting(setting=1, user_enabled=False)
    inactivity_timeout: WledIntSetting = WledIntSetting(setting=1, user_enabled=False)


class VirtualConfig(LedFxModel):
    name: str = Field(description="Friendly name for the device")
    mapping: Literal["span", "copy"] = Field(
        "span",
        description="Span: Effect spans all segments. Copy: Effect copied on each segment",
        json_schema_extra={X_REQUIRED: True},
    )
    complex_segments: bool = Field(
        False, description="Use complex segment mapping mode for performance"
    )
    grouping: int = Field(
        1,
        ge=0,
        description="Number of physical pixels to combine into larger virtual pixel groups",
        json_schema_extra={X_REQUIRED: True},
    )
    icon_name: str = Field("mdi:led-strip-variant", description="Icon for the device*")
    max_brightness: CoercedFloat = Field(
        1.0, ge=0, le=1, description="Max brightness for the device"
    )
    center_offset: int = Field(
        0, description="Number of pixels from the perceived center of the device"
    )
    preview_only: bool = Field(
        False, description="Preview the pixels without updating the devices"
    )
    transition_time: CoercedFloat = Field(
        0.4, ge=0, le=5, description="Length of transition between effects"
    )
    transition_mode: Annotated[str, OneOf(_transition_modes)] = Field(
        "Add", description="Type of transition between effects"
    )
    frequency_min: CoercedInt = Field(
        20,
        ge=20,
        le=15000,
        description="Lowest frequency for this virtual's audio reactive effects",
    )
    frequency_max: CoercedInt = Field(
        15000,
        ge=20,
        le=15000,
        description="Highest frequency for this virtual's audio reactive effects",
    )
    rows: int = Field(1, description="Amount of rows. > 1 if this virtual is a matrix")
    rotate: CoercedInt = Field(0, ge=0, le=3, description="90 Degree rotations")
