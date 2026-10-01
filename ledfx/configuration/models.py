"""pydantic models for LedFx configuration."""

from typing import Annotated, Literal, TypeVar

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    JsonValue,
    SerializerFunctionWrapHandler,
    model_serializer,
    model_validator,
)
from pydantic.fields import ComputedFieldInfo, FieldInfo
from pydantic.json_schema import JsonDict, SkipJsonSchema

from ledfx.configuration.fields import (
    RUNTIME_CONTEXT,
    X_LEGACY,
    X_OMIT_DEFAULT,
    X_READONLY,
    X_REQUIRED,
    X_RESTART,
    AudioDeviceIndex,
    CoercedFloat,
    CoercedInt,
    DeviceId,
    IPv4,
    OneOf,
    PlaylistId,
    SceneId,
    VirtualId,
    coerce,
)
from ledfx.utils import generate_title

# JSON Schema readOnly: the UI shows the value but must not edit it. What the API
# accepts is ledfx.api.utils.PERMITTED_KEYS, per /api/config section.
_RO: JsonDict = {X_READONLY: True}


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
# legacy dict site (virtuals) reads values as untyped, as it did voluptuous
# output. Typing it needs that site to read typed models instead.
def validate_dict(model: type[BaseModel], data: object, *, runtime: bool = False):
    """Validate data (any mapping; anything else is a ValidationError) and
    return a plain dict shaped like voluptuous output."""
    context = RUNTIME_CONTEXT if runtime else None
    return model.model_validate(data, context=context).model_dump()


M = TypeVar("M", bound=BaseModel)


def replace_model(model: M, **changes: object) -> M:
    """A validated copy of model with changes applied: how a frozen model
    changes. Callers swap the copy in whole, so readers never see half of it."""
    return model.model_validate({**model.model_dump(), **changes})


def _transition_modes() -> list[str]:
    from ledfx.transitions import Transitions

    return list(Transitions)


class AudioInputConfig(LedFxModel):
    model_config = ConfigDict(extra="allow")

    sample_rate: int = Field(60, json_schema_extra=_RO)
    mic_rate: int = Field(44100, json_schema_extra=_RO)
    fft_size: int = Field(4096, json_schema_extra=_RO)
    min_volume: CoercedFloat = Field(0.2, ge=0.0, le=1.0)
    audio_device: AudioDeviceIndex = None
    audio_device_name: str = Field("", json_schema_extra=_RO)
    delay_ms: CoercedInt = Field(
        0,
        ge=0,
        le=5000,
        description="Add a delay to LedFx's output to sync with your audio. Useful for Bluetooth devices which typically have a short audio lag.",
    )


class AudioAnalysisConfig(LedFxModel):
    model_config = ConfigDict(extra="allow")

    # aubio's mcomb and fcomb pitch methods crash the process; never offer them.
    pitch_method: Literal["yinfft", "yin", "yinfast", "schmitt", "specacf"] = Field(
        "yinfft", description="Method to detect pitch"
    )
    # Hidden from every schema, as the legacy /api/schema always did: the UI would
    # offer free text, and a bad value crashes aubio.tempo() on audio restart.
    tempo_method: SkipJsonSchema[str] = "default"
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


# Frozen: LedFxConfig and the live audio/melbank objects share these instances,
# so a change must replace the model (replace_model), never write into it.
class AudioConfig(AudioInputConfig, AudioAnalysisConfig):
    """Persisted audio section: input and analysis settings together."""

    model_config = ConfigDict(extra="allow", frozen=True)


class MelbankConfig(LedFxModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    name: str | None = Field(None, json_schema_extra={X_OMIT_DEFAULT: True})
    min_frequency: CoercedInt = Field(20, ge=20, le=15000)
    max_frequency: CoercedInt = Field(15000, ge=20, le=15000)


class MelbanksConfig(LedFxModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    samples: CoercedInt = Field(24, ge=0, le=100)
    # 1 is infinite power (melbank.py), below 0 the response inverts.
    peak_isolation: CoercedFloat = Field(0.4, ge=0.0, le=0.99)
    coeffs_type: Literal[
        "matt_mel", "triangle", "bark", "mel", "htk", "scott", "scott_mel"
    ] = "matt_mel"
    # A tuple, so the frozen, shared model can't be changed in place either.
    max_frequencies: tuple[Annotated[int, Field(ge=0, le=15000), coerce(int)], ...] = (
        350,
        2000,
        15000,
    )
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
    rows: int = Field(
        1, ge=1, description="Amount of rows. > 1 if this virtual is a matrix"
    )
    rotate: CoercedInt = Field(0, ge=0, le=3, description="90 Degree rotations")


# Optional-without-default: absent from config.json when None (never "null").
_UNSET: JsonDict = {X_OMIT_DEFAULT: True}


def _legacy_type(legacy_type: str, default: JsonValue) -> JsonDict:
    """Collections were untyped list/dict in the pre-overhaul core schema."""
    return {X_LEGACY: {"type": legacy_type, "default": default}}


def _empty_to_none(value: object) -> object:
    return None if value == {} else value


class EffectEntry(LedFxModel):
    type: str
    config: dict[str, object] = {}


class DeviceEntry(LedFxModel):
    id: str
    type: str
    config: dict[str, object]


class VirtualEntry(LedFxModel):
    id: str
    config: VirtualConfig
    segments: list[list[object]] = []
    is_device: DeviceId | Literal[False] = False
    auto_generated: bool = False
    # None (never toggled) is not written, so a save never pauses virtuals.
    active: bool | None = Field(None, json_schema_extra=_UNSET)
    effect: Annotated[EffectEntry | None, BeforeValidator(_empty_to_none)] = Field(
        None, json_schema_extra=_UNSET
    )
    effects: dict[str, EffectEntry] = {}
    last_effect: str | None = Field(None, json_schema_extra=_UNSET)
    # DMX Input device-level mute; None (never toggled) is not written.
    dmx_paused: bool | None = Field(None, json_schema_extra=_UNSET)


class IntegrationEntry(LedFxModel):
    id: str
    type: str
    active: bool = False
    # qlc/mqtt/mqtt_hass keep a list here; other integrations a dict.
    data: list[object] | dict[str, object] = {}
    config: dict[str, object] = {}


class SceneVirtual(LedFxModel):
    type: str | None = Field(None, json_schema_extra=_UNSET)
    # None (absent) differs from {}: a legacy entry without config is skipped.
    config: dict[str, object] | None = Field(None, json_schema_extra=_UNSET)
    action: str | None = Field(None, json_schema_extra=_UNSET)
    preset: str | None = Field(None, json_schema_extra=_UNSET)


class Scene(LedFxModel):
    name: str
    scene_image: str = "Wallpaper"
    scene_tags: str | None = Field(None, json_schema_extra=_UNSET)
    scene_puturl: str | None = Field(None, json_schema_extra=_UNSET)
    scene_payload: str | None = Field(None, json_schema_extra=_UNSET)
    scene_midiactivate: str | None = Field(None, json_schema_extra=_UNSET)
    virtuals: dict[VirtualId, SceneVirtual] = {}


class PlaylistItem(LedFxModel):
    scene_id: SceneId
    duration_ms: int | None = Field(None, ge=500, json_schema_extra=_UNSET)


class Jitter(LedFxModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool = False
    # inf would overflow the int() of the sampled duration.
    factor_min: CoercedFloat = Field(1.0, ge=0.0, allow_inf_nan=False)
    factor_max: CoercedFloat = Field(1.0, ge=0.0, allow_inf_nan=False)

    @model_validator(mode="after")
    def _bounds(self) -> "Jitter":
        if self.factor_max < self.factor_min:
            raise ValueError("jitter.factor_max must be >= factor_min")
        return self


class PlaylistTiming(LedFxModel):
    model_config = ConfigDict(extra="allow")

    jitter: Jitter = Jitter()


class Playlist(LedFxModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    items: list[PlaylistItem]
    default_duration_ms: int = Field(500, ge=500)
    mode: Literal["sequence", "shuffle"] = "sequence"
    timing: PlaylistTiming = PlaylistTiming()
    tags: list[object] = []
    image: str | None = "Wallpaper"


class Preset(LedFxModel):
    name: str
    config: dict[str, object] = {}


class MelbankCollectionEntry(LedFxModel):
    id: str
    config: MelbankConfig


class SendspinServerConfig(LedFxModel):
    # Literals (not imported): ledfx.sendspin pulls optional deps. Pinned by a test.
    server_url: str = "ws://192.168.1.12:8927/sendspin"
    client_name: str = "LedFx"


class NowPlayingGradient(LedFxModel):
    enabled: bool = False
    variant: Literal["led_safe", "led_punchy", "led_max"] = "led_punchy"
    virtual_ids: list[VirtualId] = []


class NowPlayingTrackText(LedFxModel):
    enabled: bool = True
    duration: CoercedInt = Field(60, ge=0, le=60)
    virtual_ids: list[VirtualId] = []
    preset: str = ""


class NowPlayingAlbumArt(LedFxModel):
    enabled: bool = True
    duration: CoercedInt = Field(10, ge=0, le=60)
    virtual_ids: list[VirtualId] = []


class NowPlayingConfig(LedFxModel):
    gradient: NowPlayingGradient = NowPlayingGradient()
    track_text: NowPlayingTrackText = NowPlayingTrackText()
    album_art: NowPlayingAlbumArt = NowPlayingAlbumArt()


class VenuePad(LedFxModel):
    """A color-override pad: a solid color or a gradient string."""

    color: str | None = Field(None, json_schema_extra=_UNSET)
    gradient: str | None = Field(None, json_schema_extra=_UNSET)


# The frontend's pad-grid editor caps each axis at 16. The bound also stops a
# huge grid from allocating rows*cols pads (see VenueManager.create/update).
VENUE_GRID_MAX = 16


class VenueColorPads(LedFxModel):
    rows: int = Field(4, ge=1, le=VENUE_GRID_MAX)
    cols: int = Field(4, ge=1, le=VENUE_GRID_MAX)
    pads: list[VenuePad] = []  # row-major


class Venue(LedFxModel):
    name: str
    virtual_ids: list[VirtualId] = []
    paused: bool = False  # mutes DMX Input takeover for this venue
    color_pads: VenueColorPads = VenueColorPads()


class ImageCacheConfig(LedFxModel):
    model_config = ConfigDict(extra="allow")

    max_size_mb: int = 500
    max_items: int = 500


class LedFxConfig(LedFxModel):
    """The persisted config.json (minus schema_version/configuration_version)."""

    host: str = Field("0.0.0.0", json_schema_extra={X_RESTART: True})
    port: int = Field(8888, json_schema_extra={X_RESTART: True})
    port_s: int = Field(8443, json_schema_extra={X_RESTART: True})
    dev_mode: bool = Field(False, json_schema_extra={X_RESTART: True})
    devices: list[DeviceEntry] = Field(
        list[DeviceEntry](), json_schema_extra=_legacy_type("array", [])
    )
    virtuals: list[VirtualEntry] = Field(
        list[VirtualEntry](), json_schema_extra=_legacy_type("array", [])
    )
    audio: AudioConfig = Field(
        AudioConfig(), json_schema_extra=_legacy_type("dict", {})
    )
    melbank_collection: list[MelbankCollectionEntry] = Field(
        list[MelbankCollectionEntry](),
        json_schema_extra={X_RESTART: True, **_legacy_type("array", [])},
    )
    melbanks: MelbanksConfig = Field(
        MelbanksConfig(), json_schema_extra=_legacy_type("dict", {})
    )
    user_presets: dict[str, dict[str, Preset]] = Field(
        dict[str, dict[str, Preset]](),
        json_schema_extra=_legacy_type("dict", {}),
    )
    scenes: dict[str, Scene] = Field(
        dict[str, Scene](), json_schema_extra=_legacy_type("dict", {})
    )
    playlists: dict[str, Playlist] = Field(
        dict[str, Playlist](), json_schema_extra=_legacy_type("dict", {})
    )
    integrations: list[IntegrationEntry] = Field(
        list[IntegrationEntry](), json_schema_extra=_legacy_type("array", [])
    )
    transmission_mode: Literal["compressed", "uncompressed"] = Field(
        "compressed", json_schema_extra={X_RESTART: True}
    )
    visualisation_fps: int = Field(30, ge=1, le=60)
    visualisation_maxlen: int = Field(81, ge=5, le=65536)
    global_transitions: bool = Field(
        True,
        description="Changes to any virtual's transitions apply to all other virtuals",
        json_schema_extra={X_RESTART: True},
    )
    user_colors: dict[str, str] = Field(
        dict[str, str](), json_schema_extra=_legacy_type("dict", {})
    )
    user_gradients: dict[str, str] = Field(
        dict[str, str](), json_schema_extra=_legacy_type("dict", {})
    )
    scan_on_startup: bool = False
    create_segments: bool = False
    flush_on_deactivate: bool = False
    wled_preferences: WledPreferences = Field(
        WledPreferences(), json_schema_extra=_legacy_type("dict", {})
    )
    global_brightness: CoercedFloat = Field(1.0, ge=0, le=1.0)
    ui_brightness_boost: CoercedFloat = Field(0.0, ge=0, le=1.0)
    startup_scene_id: SceneId = ""
    startup_playlist_id: PlaylistId = ""
    lifx_broadcast_address: IPv4 = "255.255.255.255"
    lifx_discovery_timeout: int = Field(30, ge=1, le=120)
    instance_id: str = Field("", json_schema_extra=_RO)
    sendspin_servers: dict[str, SendspinServerConfig] = Field(
        dict[str, SendspinServerConfig](),
        json_schema_extra=_legacy_type("dict", {}),
    )
    sendspin_always_on: bool = True
    now_playing: NowPlayingConfig = Field(
        NowPlayingConfig(), json_schema_extra=_legacy_type("dict", {})
    )
    venues: dict[str, Venue] = Field(
        dict[str, Venue](), json_schema_extra=_legacy_type("dict", {})
    )
    allowed_origins: list[str] = Field(
        list[str](),
        description='Extra web origins (e.g. "https://ledfx.example.com") allowed to use the API from a browser. "*" allows every origin',
    )
    allowed_hosts: list[str] = Field(
        list[str](),
        description='Extra host names (e.g. "ledfx.example.com") that browsers may use to reach LedFx. "*" allows every name',
    )
    allow_null_origin: bool = Field(
        False, description='Accept browser requests whose Origin is "null"'
    )
    # Keys older builds only tolerated via ALLOW_EXTRA; not in the legacy schema.
    debug_asyncio: bool = Field(
        False, json_schema_extra={**_RO, X_LEGACY: {"omit": True}}
    )
    image_cache: ImageCacheConfig = Field(
        ImageCacheConfig(), json_schema_extra={X_LEGACY: {"omit": True}}
    )


def _marked(key: str) -> frozenset[str]:
    return frozenset(
        name
        for name, info in LedFxConfig.model_fields.items()
        if isinstance(info.json_schema_extra, dict) and info.json_schema_extra.get(key)
    )


RESTART_FIELDS = _marked(X_RESTART)
