import logging
import os
from json import JSONDecodeError

from aiohttp import web
from pydantic import ValidationError

from ledfx.api import RestEndpoint
from ledfx.api.utils import PERMITTED_KEYS
from ledfx.configuration.lenient import lenient_validate
from ledfx.configuration.migrations import (
    CURRENT_SCHEMA_VERSION,
    run_migrations,
    schema_version_of,
)
from ledfx.configuration.migrations.v2 import strip_envelope
from ledfx.configuration.models import (
    RESTART_FIELDS,
    AudioConfig,
    LedFxConfig,
    MelbanksConfig,
    WledPreferences,
    validate_dict,
)
from ledfx.consts import LEGACY_CONFIGURATION_VERSION
from ledfx.effects.audio import AudioInputSource
from ledfx.events import BaseConfigUpdateEvent
from ledfx.presets import ledfx_presets

_LOGGER = logging.getLogger(__name__)

RUNTIME_KEYS = ("hosts", "ledfx_presets", "configuration_version")
CONFIG_KEYS = frozenset(LedFxConfig.model_fields) | frozenset(RUNTIME_KEYS)
BACKUP_FAILED = "Could not back up config.json; nothing was changed."
WRITE_FAILED = "Could not write config.json; nothing was changed."


def _object(value: object, node: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise KeyError(f"{node} must be a JSON object")
    return value


def _check_keys(section: dict[str, object], node: str) -> None:
    for key in section:
        if key not in PERMITTED_KEYS[node]:
            raise KeyError(f"Unknown/forbidden {node} config key: '{key}'")


class ConfigEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/config"
    # POST (import) explains a non-object file itself.
    OBJECT_BODY_METHODS = ("PUT", "DELETE")

    def _runtime_value(self, key: str) -> object:
        if key == "hosts":
            return self._ledfx.hosts
        if key == "ledfx_presets":
            return ledfx_presets
        return LEGACY_CONFIGURATION_VERSION

    async def get(self, request: web.Request) -> web.Response:
        """Get the config; the body may name a key or a list of keys."""
        keys: set[str] = set()
        if request.can_read_body:
            try:
                wanted = await request.json()
            except JSONDecodeError:
                return await self.json_decode_error()
            if isinstance(wanted, list):
                keys.update(wanted)
            elif isinstance(wanted, str):
                keys.add(wanted)
            keys &= CONFIG_KEYS
        if not keys:
            keys = set(CONFIG_KEYS)
        dumped = self._ledfx.config.model_dump(mode="json")
        # GET has always shown the resolved audio device (the old schema resolved it).
        dumped["audio"] = validate_dict(AudioConfig, dumped["audio"], runtime=True)
        response = {
            key: (self._runtime_value(key) if key in RUNTIME_KEYS else dumped[key])
            for key in keys
        }
        return await self.bare_request_success(response)

    async def delete(self) -> web.Response:
        """Reset config to defaults and restart LedFx."""
        store = self._ledfx.config_store
        # An unreadable config.json can't be copied (load already tried); reset
        # and import are how safe mode recovers from it, so go ahead.
        if (
            os.path.exists(store.path)
            and store.backup("DELETE") is None
            and not store.unreadable
        ):
            return await self.internal_error(BACKUP_FAILED)
        if not await store.replace(LedFxConfig()):
            return await self.internal_error(WRITE_FAILED)
        self._ledfx.loop.call_soon_threadsafe(self._ledfx.stop, 4)
        return await self.request_success(
            "success", "Config reset to default values, LedFx restarting."
        )

    async def post(self, request: web.Request) -> web.Response:
        """Import a complete config (leniently) and restart LedFx."""
        try:
            raw = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()
        if not isinstance(raw, dict):
            return await self.invalid_request("Imported config is not a LedFx config.")
        # Lenient validation would drop a newer release's fields yet report success.
        if schema_version_of(raw) > CURRENT_SCHEMA_VERSION:
            return await self.invalid_request(
                "This config is from a newer version of LedFx; update LedFx to import it."
            )
        try:
            raw = run_migrations(raw)
        except Exception as e:
            msg = f"Failed to migrate import config to the new standard: {e}"
            _LOGGER.exception(msg)
            return await self.internal_error(msg, "error")
        strip_envelope(raw)
        store = self._ledfx.config_store
        config = lenient_validate(LedFxConfig, raw, "import", store.quarantine)
        if config is None:
            return await self.invalid_request("Imported config is not a LedFx config.")
        if (
            os.path.exists(store.path)
            and store.backup("IMPORT") is None
            and not store.unreadable
        ):
            return await self.internal_error(BACKUP_FAILED)
        if not await store.replace(config):
            return await self.internal_error(WRITE_FAILED)
        self._ledfx.loop.call_soon_threadsafe(self._ledfx.stop, 4)
        return await self.request_success()

    async def put(self, request: web.Request) -> web.Response:
        """Update the config; restarts only if a restart field changed."""
        try:
            patch = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()
        except Exception as e:  # noqa: BLE001 - body read failures are a 500, as before
            return await self.internal_error(str(e))
        try:
            changed = self.apply_patch(patch)
        except KeyError as e:
            return await self.invalid_request(f"Error updating config: {e}")
        except ValidationError as err:
            return await self.validation_error(err)
        except Exception as e:  # noqa: BLE001 - as before: never a bare traceback
            return await self.internal_error(str(e))
        self._ledfx.config_store.request_save()
        if changed & RESTART_FIELDS:
            try:
                return await self.request_success(
                    type="success",
                    message="LedFx is restarting to apply the new configuration",
                )
            finally:
                self._ledfx.loop.call_soon_threadsafe(self._ledfx.stop, 4)
        return await self.request_success(
            type="success", message="Configuration Updated"
        )

    def apply_patch(self, patch: dict[str, object]) -> set[str]:
        """Validate the whole patch first, then apply it. Returns changed fields."""
        cfg = self._ledfx.config
        audio = _object(patch.pop("audio", {}), "audio")
        wled = _object(patch.pop("wled_preferences", {}), "wled_preferences")
        melbanks = _object(patch.pop("melbanks", {}), "melbanks")
        _check_keys(audio, "audio")
        _check_keys(wled, "wled_preferences")
        _check_keys(melbanks, "melbanks")
        for key in patch:
            if key not in PERMITTED_KEYS["core"] and key != "user_presets":
                raise KeyError(f"Unknown/forbidden core config key: '{key}'")

        candidate = cfg.model_copy(deep=True)
        for key, value in patch.items():
            setattr(candidate, key, value)
        if audio:
            if "audio_device" in audio:
                device = audio["audio_device"]
                names = AudioInputSource.input_devices()
                audio["audio_device_name"] = (
                    names.get(device, "") if isinstance(device, int) else ""
                )
            candidate.audio = AudioConfig.model_validate(
                {**cfg.audio.model_dump(), **audio}
            )
        if wled:
            current = cfg.wled_preferences.model_dump()
            candidate.wled_preferences = WledPreferences.model_validate(
                {
                    **current,
                    **{
                        k: {**current.get(k, {}), **_object(v, k)}
                        for k, v in wled.items()
                    },
                }
            )
        if melbanks:
            candidate.melbanks = MelbanksConfig.model_validate(
                {**cfg.melbanks.model_dump(), **melbanks}
            )

        changed = {
            name
            for name in LedFxConfig.model_fields
            if getattr(candidate, name) != getattr(cfg, name)
        }
        previous = {name: getattr(cfg, name) for name in changed}
        for name in changed:
            setattr(cfg, name, getattr(candidate, name))

        try:
            if audio:
                if getattr(self._ledfx, "audio", None) is not None:
                    self._ledfx.audio.update_config(candidate.audio.model_dump())
                # Also with no audio running: a Sendspin device may need an eager start.
                if hasattr(self._ledfx, "reconcile_sendspin_always_on_runtime"):
                    self._ledfx.reconcile_sendspin_always_on_runtime(
                        "audio_config_updated"
                    )
                if hasattr(self._ledfx, "reconcile_snapcast_always_on_runtime"):
                    self._ledfx.reconcile_snapcast_always_on_runtime(
                        "audio_config_updated"
                    )
            if melbanks and getattr(self._ledfx, "audio", None) is not None:
                self._ledfx.audio.melbanks.update_config(cfg.melbanks.model_dump())
            self._ledfx.events.fire_event(
                BaseConfigUpdateEvent({**patch, **({"audio": audio} if audio else {})})
            )
        except Exception:
            # The request fails, so none of the patch may stay (audio writes too).
            for name, value in previous.items():
                setattr(cfg, name, value)
            raise
        return changed
