"""Replay a sender_bench sampling recording into per-family CPU stack summaries.

Run with the same Python 3.15 interpreter used to capture the recording:
  python3.15 tools/sender_profile_report.py /tmp/senders.jsonl

Only stacks inside measure_flushes count: imports, discovery substitutes,
preflight decoding, receiver setup and teardown are excluded. Multiple sizes or
variants of one sender class are aggregated; use separate benchmark runs when
comparing their profiles. Raw timing comparisons belong to unprofiled runs.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.effect_profile_report import summarize_stacks
from tools.sender_bench_protocols import SPECS


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    binary = Path(str(args.results) + ".sampling.bin")
    if sys.version_info < (3, 15) or not binary.exists():
        parser.error(
            "A sender_bench sampling recording and its Python 3.15 interpreter are required"
        )
    collapsed = Path(str(args.results) + ".sampling.collapsed")
    with Path(str(args.results) + ".replay.log").open("w") as log:
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
            stderr=subprocess.STDOUT,
            check=True,
        )
    lines = collapsed.read_text().splitlines()
    rows = [json.loads(line) for line in args.results.read_text().splitlines()]
    families = {}
    for row in rows:
        if row["status"] == "ok":
            families.setdefault(SPECS[row["sender"]].class_name, []).append(
                {
                    "e131_bytes_prototype": row.get("e131_bytes_prototype", False),
                    **{
                        key: row[key]
                        for key in (
                            "sender",
                            "pixels",
                            "pattern",
                            "mode",
                            "repeat",
                            "profiled",
                        )
                    },
                }
            )
    report = {
        "scope": "CPU samples within measure_flushes; per sender class, including all listed cases",
        "families": {},
    }
    for family, cases in families.items():
        selected = [line for line in lines if family + ".flush" in line]
        profile = summarize_stacks(selected, ("measure_flushes",))
        report["families"][family] = {"cases": cases, "profile": profile}
        print(f"{family}: {profile['active_samples']} measured samples")
        for hotspot in profile["top_self"][:5]:
            print(f"  {hotspot['active_sample_pct']:6.2f}% {hotspot['frame']}")
    destination = Path(str(args.results) + ".profiles.json")
    destination.write_text(json.dumps(report, indent=2) + "\n")
    print(destination)


if __name__ == "__main__":
    main()
