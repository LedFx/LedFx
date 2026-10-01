"""Melbank and Melbanks hold typed, frozen config models."""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from ledfx.configuration.models import AudioConfig, MelbanksConfig
from ledfx.effects.melbank import Melbank, MelbankProcessorConfig, Melbanks
from tests.test_utilities.fake_ledfx import fake_ledfx


@pytest.mark.parametrize(
    ("coeffs_type", "samples"), [("slaney", 40), ("fixed", 8), ("fixed_simple", 3)]
)
def test_melbank_coeffs_type_sets_samples(coeffs_type: str, samples: int):
    """Coefficient types with a fixed band count replace the config with the
    band count they produce."""
    melbank = Melbank(
        None,
        {"samples": 24, "peak_isolation": 0.4, "coeffs_type": coeffs_type},
    )

    assert isinstance(melbank._config, MelbankProcessorConfig)
    assert melbank._config.samples == samples
    assert len(melbank.melbank_frequencies) == samples
    with pytest.raises(ValidationError, match="frozen"):
        melbank._config.samples = 1  # pyrefly: ignore[read-only]


def _melbanks(melbanks: dict[str, object] | None = None):
    ledfx = fake_ledfx({"melbanks": melbanks or {}})
    audio = SimpleNamespace(_config=AudioConfig(min_volume=0.3))
    return ledfx, Melbanks(ledfx, audio, ledfx.config.melbanks.model_dump())


def test_melbanks_apply_global_settings_as_typed_config():
    ledfx, melbanks = _melbanks({"samples": 30, "coeffs_type": "mel"})

    assert isinstance(melbanks.melbanks_config, MelbanksConfig)
    assert ledfx.config.melbanks is melbanks.melbanks_config
    assert melbanks.mel_len == 30
    assert melbanks.minimum_volume == 0.3
    for proc in melbanks.melbank_processors:
        assert (proc._config.samples, proc._config.coeffs_type) == (30, "mel")
    # Global settings are applied per melbank but never persisted per melbank.
    assert [e.config.model_dump() for e in ledfx.config.melbank_collection] == [
        {"name": f"Melbank {i}", "min_frequency": 20, "max_frequency": f}
        for i, f in enumerate([350, 2000, 15000])
    ]


def test_shared_melbanks_config_cannot_be_written_in_place():
    """config.melbanks is the live object's model: writing into it would change
    the melbanks without rebuilding them, so it must raise. Updates go through
    update_config and reach both."""
    ledfx, melbanks = _melbanks()

    with pytest.raises(ValidationError, match="frozen"):
        ledfx.config.melbanks.samples = 10
    with pytest.raises(ValidationError, match="frozen"):
        ledfx.config.melbank_collection[0].config.max_frequency = 100
    with pytest.raises(TypeError):
        ledfx.config.melbanks.max_frequencies[0] = 100
    assert melbanks.mel_len == 24
    # Still a JSON array everywhere it leaves the model.
    assert ledfx.config.melbanks.model_dump(mode="json")["max_frequencies"] == [
        350,
        2000,
        15000,
    ]
    schema = MelbanksConfig.model_json_schema()["properties"]["max_frequencies"]
    assert schema["type"] == "array"

    melbanks.update_config({**ledfx.config.melbanks.model_dump(), "samples": 10})

    assert ledfx.config.melbanks is melbanks.melbanks_config
    assert (melbanks.melbanks_config.samples, melbanks.mel_len) == (10, 10)
    assert all(p._config.samples == 10 for p in melbanks.melbank_processors)
