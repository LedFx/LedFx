"""Catalog fixtures and reports must produce repeatable, distinct workloads."""

import numpy as np
import pytest

from tools.effect_profile_report import summarize_stacks
from tools.pixel_bench import parse_args, scenario_key
from tools.pixel_bench_fixtures import audio_signal, matrix_rows


def test_synthetic_pcm_is_repeatable_bounded_and_pulsed() -> None:
    signal = audio_signal()
    np.testing.assert_array_equal(signal, audio_signal())
    assert signal.dtype == np.float32
    assert len(signal) == 30000 * 8
    assert np.isfinite(signal).all()
    assert np.max(np.abs(signal)) <= 1
    # Beat attacks carry more power than the tail of the half-second beat.
    beats = signal.reshape(-1, 15000)
    assert np.mean(beats[:, :1500] ** 2) > np.mean(beats[:, 12000:] ** 2)


@pytest.mark.parametrize("pixels,rows", [(500000, 625), (1024, 32), (81, 9), (17, 1)])
def test_matrix_layout_keeps_every_pixel(pixels: int, rows: int) -> None:
    assert matrix_rows(pixels) == rows
    assert pixels % rows == 0


@pytest.mark.parametrize(
    "options",
    [
        ["--rows", "3", "--pixels", "10"],
        ["--effect-config", "[]"],
        ["--effect-config", "bad"],
        ["--case-timeout", "nan"],
    ],
)
def test_invalid_catalog_arguments(options: list[str]) -> None:
    with pytest.raises(SystemExit):
        parse_args(options)


def test_profiles_exclude_startup_and_count_recursive_frames_once() -> None:
    report = summarize_stacks(
        [
            "tid:1;importlib.py:import_module:1 100",
            "tid:2;virtuals.py:Virtual.thread_function:1;effect.py:render:1;effect.py:render:2 20",
            "tid:3;audio.py:_audio_sample_callback:1;audio.py:fft:2 10",
        ]
    )
    assert report["all_samples"] == 130
    assert report["active_samples"] == 30
    assert report["top_self"][0]["frame"] == "effect.py:render"
    assert report["top_self"][0]["samples"] == 20
    assert (
        next(r for r in report["top_inclusive"] if r["frame"] == "effect.py:render")[
            "samples"
        ]
        == 20
    )


def test_baseline_distinguishes_effect_audio_geometry_and_overrides() -> None:
    row = {
        "platform": "linux",
        "python": "3.15",
        "loop": "standard",
        "device": "ddp",
        "pixels": 500000,
        "refresh_rate": 60,
        "preview_fps": 60,
        "effect_speed": 6,
        "stream": "full",
        "profiled": False,
    }
    original = scenario_key(row)
    for changed in (
        {"effect_id": "noise2d"},
        {"rows": 625},
        {"synthetic_audio": True},
        {"fixtures": True},
        {"config_overrides": {"speed": 2}},
    ):
        assert scenario_key(row | changed) != original
    assert scenario_key(
        row | {"config_overrides": {"speed": 2, "blur": 0}}
    ) == scenario_key(row | {"config_overrides": {"blur": 0, "speed": 2}})
