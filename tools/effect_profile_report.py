"""Summarize a pixel_bench catalog sweep and replay per-effect sampling stacks.

Run with the same Python 3.15 interpreter that captured the profiles:
  python3.15 tools/effect_profile_report.py /tmp/catalog.jsonl

Reports CPU stack shares only within active rendering/audio/preview stacks to
avoid ranking imports and shutdown as effect bottlenecks. Warmup is included;
short catalog runs are screening, not statistically robust regression gates.
"""

import argparse
import collections
import json
import subprocess
import sys
from pathlib import Path

ACTIVE_STACKS = (
    "Virtual.thread_function",
    "TemporalEffect.thread_function",
    "_audio_sample_callback",
    "handle_visualisation_update",
    "WebsocketConnection",
)


def summarize_stacks(
    lines: list[str], active_stacks: tuple[str, ...] = ACTIVE_STACKS
) -> dict:
    total = active = 0
    leaf = collections.Counter()
    inclusive = collections.Counter()
    for line in lines:
        stack, count = line.rsplit(" ", 1)
        count = int(count)
        total += count
        if not any(marker in stack for marker in active_stacks):
            continue
        active += count
        frames = [
            frame.rsplit(":", 1)[0]
            for frame in stack.split(";")
            if not frame.startswith("tid:")
        ]
        leaf[frames[-1]] += count
        inclusive.update({frame: count for frame in set(frames)})

    def top(counter):
        return (
            [
                {
                    "frame": name,
                    "samples": n,
                    "active_sample_pct": round(n / active * 100, 2),
                }
                for name, n in counter.most_common(15)
            ]
            if active
            else []
        )

    return {
        "all_samples": total,
        "active_samples": active,
        "top_self": top(leaf),
        "top_inclusive": top(inclusive),
    }


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.results.read_text().splitlines()]
    artifacts = Path(str(args.results) + ".artifacts")
    report = []
    for row in rows:
        effect = row.get("effect_id", "rainbow")
        case = f"{row['repeat']}-{row['stream']}-{row['loop']}"
        folder = artifacts / (effect + "-") / case
        if not folder.exists():
            folder = artifacts / case
        binary = folder / "sampling.bin"
        profile = {}
        if binary.exists():
            collapsed = folder / "sampling.collapsed"
            with (folder / "replay.log").open("w") as log:
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "profiling.sampling",
                        "replay",
                        "--collapsed",
                        "-o",
                        str(collapsed),
                        str(binary),
                    ],
                    stdout=log,
                    stderr=log,
                    check=True,
                )
            profile = summarize_stacks(collapsed.read_text().splitlines())
        report.append(
            {
                "effect": effect,
                "rows": row.get("rows", 1),
                "pixels": row["pixels"],
                "render_fps": row["assemble"]["fps"],
                "effect_ms": row["effect"]["mean_ms"],
                "audio_fps": row.get("audio", {}).get("fps", 0),
                "audio_update_ms": row.get("audio_update", {}).get("mean_ms", 0),
                "server_cpu_pct": row["server_cpu_pct"],
                "rss_mb": row["rss_mb"],
                "ws_changed_fps": row["ws_changed_fps"],
                "ddp_complete_fps": row["ddp_complete_fps"],
                "profile": profile,
            }
        )
    report.sort(key=lambda r: r["effect_ms"] + r["audio_update_ms"], reverse=True)
    destination = Path(str(args.results) + ".profiles.json")
    destination.write_text(json.dumps(report, indent=2) + "\n")
    print(destination)
    for row in report:
        print(
            f"{row['effect']:22} render={row['render_fps']:6.2f} FPS  effect={row['effect_ms']:8.3f} ms  audio update={row['audio_update_ms']:8.3f} ms  CPU={row['server_cpu_pct']:6.1f}%"
        )


if __name__ == "__main__":
    main()
