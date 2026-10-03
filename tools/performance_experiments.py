"""Run sequential, randomized paired trials of benchmark-only experiments.

Example (Python 3.15 environment with LedFx installed):
  python tools/performance_experiments.py --output /tmp/experiments

Each repeat shuffles treatments within workload blocks and shuffles the blocks.
Seeds match within each block. No CPU workloads run concurrently. The manifest
records every command, order, return code and log, including failed trials.
Summaries include individual observations and paired ratios, not just best FPS.
Full raw metrics and environment metadata remain beside each trial.
"""

import argparse
import json
import math
import random
import statistics
import subprocess
import sys
from pathlib import Path

TEMPORAL_EFFECTS = (
    "fade",
    "rainbow",
    "singleColor",
    "pixels",
    "random_flash",
    "gradient",
)
DYNAMIC_CASES = {
    "singleColor-sine": (
        "singleColor",
        {"modulate": True, "modulation_effect": "sine"},
    ),
    "singleColor-breath": (
        "singleColor",
        {"modulate": True, "modulation_effect": "breath"},
    ),
    "gradient-roll": ("gradient", {"gradient_roll": 1}),
    "random_flash-probability": ("random_flash", {"hit_probability_per_sec": 0.5}),
}
TREATMENTS = {
    "threaded-max": [],
    "render-max": ["--temporal-render"],
    "threaded-cadence": ["--temporal-cadence"],
    "render-cadence": ["--temporal-render", "--temporal-cadence"],
}


def design(args):
    rng = random.Random(args.seed)
    trials = []
    for repeat in range(args.repeats):
        blocks = []
        if args.suite in ("all", "temporal"):
            for effect in TEMPORAL_EFFECTS:
                blocks.append(("temporal", effect, list(TREATMENTS)))
        if args.suite == "dynamic":
            for workload in DYNAMIC_CASES:
                blocks.append(
                    ("temporal", workload, ["threaded-cadence", "render-cadence"])
                )
        if args.suite in ("all", "e131"):
            for pattern in ("dense", "sparse", "static"):
                for mode in ("encode", "loopback"):
                    blocks.append(("e131", f"{pattern}-{mode}", ["stock", "bytes"]))
        rng.shuffle(blocks)
        for suite, workload, treatments in blocks:
            rng.shuffle(treatments)
            for treatment in treatments:
                trials.append(
                    {
                        "suite": suite,
                        "workload": workload,
                        "treatment": treatment,
                        "repeat": repeat,
                        "seed": args.seed + repeat,
                    }
                )
    for trial in trials:
        if trial["workload"] in DYNAMIC_CASES:
            trial["effect"], trial["config"] = DYNAMIC_CASES[trial["workload"]]
    return trials


def command(args, trial, path):
    common = [
        "--pixels",
        str(args.pixels),
        "--seconds",
        str(args.seconds),
        "--repeats",
        "1",
        "--bind",
        args.bind,
        "--output",
        str(path),
    ]
    if trial["suite"] == "temporal":
        return [
            sys.executable,
            "tools/pixel_bench.py",
            *common,
            "--effects",
            trial.get("effect", trial["workload"]),
            "--effect-config",
            json.dumps(trial.get("config", {})),
            "--streams",
            "full",
            "--loops",
            "standard",
            "--fixtures",
            "--synthetic-audio",
            "--unpaced",
            "--unpaced-preview",
            "--warmup",
            str(args.warmup),
            "--seed",
            str(trial["seed"]),
            *TREATMENTS[trial["treatment"]],
        ]
    pattern, mode = trial["workload"].split("-")
    return [
        sys.executable,
        "tools/sender_bench.py",
        *common,
        "--senders",
        "e131",
        "--patterns",
        pattern,
        "--modes",
        mode,
        "--max-packets",
        "150000",
        *(["--e131-bytes-prototype"] if trial["treatment"] == "bytes" else []),
    ]


def summarize(trials):
    groups = {}
    for trial in trials:
        if trial.get("returncode") != 0:
            continue
        rows = [
            json.loads(line) for line in Path(trial["output"]).read_text().splitlines()
        ]
        if len(rows) != 1:
            raise ValueError(f"Expected one observation: {trial['output']}")
        row = rows[0]
        key = (trial["suite"], trial["workload"], trial["treatment"])
        metrics = groups.setdefault(key, {})
        for name in (
            "ddp_complete_fps",
            "ws_changed_fps",
            "server_cpu_pct",
            "rss_mb",
            "ddp_invalid_packets",
            "ddp_push_fps",
            "flush_fps",
            "sender_cpu_pct",
            "received_complete_fps",
            "cpu_ms_per_flush",
            "application_MB_s",
            "flush_mean_ms",
        ):
            if row.get(name) is not None:
                metrics.setdefault(name, []).append(row[name])
        for name in ("effect", "assemble", "flush", "loop_lag"):
            if name in row:
                for statistic in ("fps", "p95_ms"):
                    metrics.setdefault(f"{name}_{statistic}", []).append(
                        row[name][statistic]
                    )
    return [
        {
            "suite": key[0],
            "workload": key[1],
            "treatment": key[2],
            "metrics": {
                name: {
                    "median": statistics.median(values),
                    "minimum": min(values),
                    "maximum": max(values),
                    "observations": values,
                }
                for name, values in metrics.items()
            },
        }
        for key, metrics in sorted(groups.items())
    ]


def paired_comparisons(trials):
    """Pair within repeat/workload; report dispersion without assuming normality."""
    rows = {}
    for trial in trials:
        if trial.get("returncode") != 0:
            continue
        row = json.loads(Path(trial["output"]).read_text().strip())
        rows[
            (trial["suite"], trial["workload"], trial["repeat"], trial["treatment"])
        ] = row
    groups = {}
    for (suite, workload, repeat, treatment), row in rows.items():
        baseline = {
            "render-max": "threaded-max",
            "render-cadence": "threaded-cadence",
            "bytes": "stock",
        }.get(treatment)
        if baseline is None:
            continue
        other = rows.get((suite, workload, repeat, baseline))
        if other is None:
            continue
        metrics = (
            ("ddp_complete_fps", "ws_changed_fps", "server_cpu_pct", "rss_mb")
            if suite == "temporal"
            else ("flush_fps", "sender_cpu_pct", "cpu_ms_per_flush")
        )
        for metric in metrics:
            if other[metric] == 0:
                continue
            groups.setdefault(
                (suite, workload, treatment, baseline, metric), []
            ).append(row[metric] / other[metric])
    return [
        {
            "suite": key[0],
            "workload": key[1],
            "treatment": key[2],
            "baseline": key[3],
            "metric": key[4],
            "paired_ratios": values,
            "median_ratio": statistics.median(values),
            "minimum_ratio": min(values),
            "maximum_ratio": max(values),
        }
        for key, values in sorted(groups.items())
    ]


def validate_observation(trial):
    rows = [json.loads(line) for line in Path(trial["output"]).read_text().splitlines()]
    if len(rows) != 1:
        raise ValueError("Each trial must produce exactly one observation")
    row = rows[0]
    if trial["suite"] == "temporal":
        if row["ddp_invalid_packets"]:
            raise ValueError("Malformed DDP packets")
        if trial["treatment"].endswith("cadence"):
            # All six current effect_loop implementations return None.
            expected = {
                "fade": 5,
                "rainbow": 60,
                "singleColor": 10,
                "pixels": 200,
                "random_flash": 50,
                "gradient": 10,
            }[trial.get("effect", trial["workload"])]
            if row["effect"]["fps"] > expected * 1.1 + 2 / row["seconds"]:
                raise ValueError("Cadence control exceeded its configured tick rate")
    elif row["status"] != "ok":
        raise ValueError("Sender failed payload validation")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--summarize",
        action="store_true",
        help="Recompute reports from an existing manifest, including relocated artifacts",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume unfinished manifest trials; completed trials are retained",
    )
    parser.add_argument(
        "--suite", choices=("all", "temporal", "e131", "dynamic"), default="all"
    )
    parser.add_argument("--pixels", type=int, default=50000)
    parser.add_argument("--seconds", type=float, default=8)
    parser.add_argument("--warmup", type=float, default=2)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--seed", type=int, default=2058)
    parser.add_argument("--bind", default="127.0.0.2")
    args = parser.parse_args()
    if (
        not math.isfinite(args.seconds)
        or not math.isfinite(args.warmup)
        or args.seconds <= 0
        or args.warmup < 0
        or args.repeats < 1
        or args.pixels < 1
    ):
        parser.error("Require positive seconds/repeats/pixels and nonnegative warmup")
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = args.output / "manifest.json"
    if args.summarize:
        trials = json.loads(manifest.read_text())
        for trial in trials:
            trial["output"] = str(args.output / Path(trial["output"]).name)
        (args.output / "summary.json").write_text(
            json.dumps(summarize(trials), indent=2)
        )
        (args.output / "paired.json").write_text(
            json.dumps(paired_comparisons(trials), indent=2)
        )
        return
    if args.resume:
        trials = json.loads(manifest.read_text())
        for trial in trials:
            if "returncode" not in trial and Path(trial["output"]).exists():
                parser.error(
                    "Unfinished trial has partial output; preserve it and choose a new output directory"
                )
    else:
        if manifest.exists():
            parser.error("Output already contains a manifest; choose a new directory")
        trials = design(args)
        for index, trial in enumerate(trials):
            path = (
                args.output
                / f"{index:03}-{trial['suite']}-{trial['workload']}-{trial['treatment']}.jsonl"
            )
            trial["output"] = str(path.resolve())
            trial["command"] = command(args, trial, path)
        manifest.write_text(json.dumps(trials, indent=2))
    for index, trial in enumerate(trials):
        if "returncode" in trial:
            continue
        print(
            f"{index + 1}/{len(trials)} {trial['suite']} {trial['workload']} {trial['treatment']}",
            flush=True,
        )
        with Path(trial["output"] + ".log").open("w") as log:
            process = subprocess.Popen(
                trial["command"], stdout=log, stderr=subprocess.STDOUT
            )
            try:
                trial["returncode"] = process.wait(
                    timeout=max(180, args.seconds + args.warmup + 90)
                )
            except subprocess.TimeoutExpired:
                trial["returncode"] = 124
            finally:
                if process.poll() is None:
                    import psutil

                    children = psutil.Process(process.pid).children(recursive=True)
                    for child in children:
                        try:
                            child.kill()
                        except psutil.NoSuchProcess:
                            pass
                    process.kill()
                    process.wait()
                    psutil.wait_procs(children, timeout=5)
        if trial["returncode"] == 0:
            try:
                validate_observation(trial)
            except (ValueError, KeyError) as error:
                trial["returncode"] = 65
                trial["validation_error"] = str(error)
        manifest.write_text(json.dumps(trials, indent=2))
        (args.output / "summary.json").write_text(
            json.dumps(summarize(trials), indent=2)
        )
    (args.output / "paired.json").write_text(
        json.dumps(paired_comparisons(trials), indent=2)
    )
    if any(trial["returncode"] != 0 for trial in trials):
        raise SystemExit("Some trials failed; inspect manifest and logs")


if __name__ == "__main__":
    main()
