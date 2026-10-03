"""Experimental comparisons must stay paired and reject broken controls."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.performance_experiments import (
    design,
    paired_comparisons,
    validate_observation,
)


def test_design_is_reproducible_balanced_and_paired() -> None:
    args = SimpleNamespace(seed=2058, repeats=3, suite="all")
    trials = design(args)
    assert trials == design(args)
    assert len(trials) == 108
    for repeat in range(3):
        selected = [trial for trial in trials if trial["repeat"] == repeat]
        assert len(selected) == 36
        assert {
            trial["seed"] for trial in selected if trial["suite"] == "temporal"
        } == {2058 + repeat}
        assert {trial["seed"] for trial in selected if trial["suite"] == "e131"} == {
            2058
        }
        for effect in (
            "fade",
            "rainbow",
            "singleColor",
            "pixels",
            "random_flash",
            "gradient",
        ):
            assert {
                trial["treatment"] for trial in selected if trial["workload"] == effect
            } == {"threaded-max", "render-max", "threaded-cadence", "render-cadence"}
    assert trials != design(SimpleNamespace(seed=2059, repeats=3, suite="all"))


def test_cadence_control_rejects_unpaced_results(tmp_path: Path) -> None:
    path = tmp_path / "trial.jsonl"
    trial = {
        "output": str(path),
        "suite": "temporal",
        "workload": "fade",
        "treatment": "threaded-cadence",
    }
    row = {"ddp_invalid_packets": 0, "effect": {"fps": 4000}, "seconds": 8}
    path.write_text(json.dumps(row))
    with pytest.raises(ValueError, match="Cadence"):
        validate_observation(trial)
    row["effect"] = {"fps": 5}
    path.write_text(json.dumps(row))
    validate_observation(trial)


def test_ratios_pair_within_repeats_and_skip_failed_trials(tmp_path: Path) -> None:
    trials = []
    for repeat, values in enumerate(((10, 20), (100, 100), (1, 999))):
        for treatment, fps in zip(("stock", "bytes"), values, strict=True):
            path = tmp_path / f"{repeat}-{treatment}.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "flush_fps": fps,
                        "sender_cpu_pct": 100,
                        "cpu_ms_per_flush": 1000 / fps,
                    }
                )
            )
            trials.append(
                {
                    "output": str(path),
                    "suite": "e131",
                    "workload": "dense-encode",
                    "repeat": repeat,
                    "treatment": treatment,
                    "returncode": 1 if repeat == 2 else 0,
                }
            )
    comparison = next(
        row for row in paired_comparisons(trials) if row["metric"] == "flush_fps"
    )
    assert comparison["paired_ratios"] == [2.0, 1.0]
    assert comparison["median_ratio"] == 1.5  # Not ratio of the pooled medians.


def test_encoding_only_null_receive_rates_are_not_aggregated(tmp_path: Path) -> None:
    from tools.performance_experiments import summarize

    trials = []
    for repeat in range(2):
        path = tmp_path / f"{repeat}.jsonl"
        path.write_text(json.dumps({"flush_fps": 100, "received_complete_fps": None}))
        trials.append(
            {
                "output": str(path),
                "suite": "e131",
                "workload": "static-encode",
                "treatment": "stock",
                "returncode": 0,
            }
        )
    report = summarize(trials)
    assert report[0]["metrics"]["flush_fps"]["median"] == 100
    assert "received_complete_fps" not in report[0]["metrics"]


def test_resume_preserves_completed_observations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.performance_experiments import main

    path = tmp_path / "done.jsonl"
    original = json.dumps({"flush_fps": 100})
    path.write_text(original)
    manifest = [
        {
            "output": str(path),
            "suite": "e131",
            "workload": "dense-encode",
            "treatment": "stock",
            "repeat": 0,
            "returncode": 0,
            "command": ["must-not-run"],
        }
    ]
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(
        "sys.argv", ["experiments", "--output", str(tmp_path), "--resume"]
    )
    main()
    assert path.read_text() == original
    assert json.loads((tmp_path / "manifest.json").read_text()) == manifest


def test_resume_refuses_partial_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.performance_experiments import main

    path = tmp_path / "partial.jsonl"
    path.write_text("preserve diagnostic")
    (tmp_path / "manifest.json").write_text(json.dumps([{"output": str(path)}]))
    monkeypatch.setattr(
        "sys.argv", ["experiments", "--output", str(tmp_path), "--resume"]
    )
    with pytest.raises(SystemExit):
        main()
    assert path.read_text() == "preserve diagnostic"
