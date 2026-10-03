"""Benchmark real LedFx rendering, loopback DDP, and websocket pixel streaming.

Examples (run in the project environment):
  uv run python tools/pixel_bench.py --output /tmp/pixels.jsonl
  uv run python tools/pixel_bench.py --loops standard --streams full --profile \
      --repeats 1 --output /tmp/profile.jsonl
  uv run python tools/pixel_bench.py --baseline /tmp/pixels.jsonl \
      --max-regression 0.10 --output /tmp/after.jsonl
  python3.15 tools/pixel_bench.py --sampling cpu --loops standard \
      --streams full --repeats 1 --output /tmp/sampled.jsonl
  python3.15 -m profiling.sampling replay --flamegraph \
      /tmp/sampled.jsonl.artifacts/0-full-standard/sampling.bin

Each run has a fresh server process and temporary configuration. The controller
receives DDP on loopback and validates websocket RGB payloads; no physical device
is used. 'default' streams at most 81 pixels; 'full' bypasses the product's 65536
preview cap only inside the worker. Both default to a requested preview rate of
60 Hz. Rainbow requests 60 updates/sec by default; actual effect, render and
output rates are measured separately. ws_changed_fps distinguishes new images
from repeated previews of the same effect frame.

CPU is server process CPU (100% = one core), excluding the receiver. Callback
timings include instrumentation overhead. DDP complete frames and packet counts
distinguish successful delivery from a PUSH packet alone. Main-loop, rendering,
and effect-thread cProfile modes cover only the measured interval; profiled runs
are slower and must not be compared with unprofiled runs. Summary medians and
min/max expose run variation; use longer intervals/repeats on an otherwise idle
machine before treating a baseline regression as significant. This is a
throughput/CPU benchmark, not an end-to-end audio or physical LED latency test.

Python 3.15 --sampling launches the worker through profiling.sampling (all
threads, 1 kHz). Its binary recording includes startup, warmup and shutdown;
use sufficiently long runs to distinguish sustained costs from imports. Replay
with the same interpreter version to produce flamegraphs, pstats or JSONL.
Sampling runs are kept separate from unprofiled baselines. No system tracing
permissions are changed: the sampler is the worker's parent process.
"""

import argparse
import asyncio
import base64
import cProfile
import importlib.metadata
import importlib.util
import json
import logging
import math
import os
import platform
import shutil
import socket
import statistics
import struct
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch


def validate_frame(event: dict, expected_pixels: int) -> list[int]:
    """Reject malformed/truncated streams instead of counting them as throughput."""
    shape = event.get("shape")
    if (
        not isinstance(shape, list)
        or len(shape) != 2
        or any(type(n) is not int or n <= 0 for n in shape)
        or shape[0] * shape[1] != expected_pixels
    ):
        raise ValueError(
            f"Unexpected pixel shape: {shape!r}; expected {expected_pixels}"
        )
    pixels = event.get("pixels")
    if not isinstance(pixels, str):
        raise TypeError("Expected base64 RGB pixels")
    decoded = base64.b64decode(pixels, validate=True)
    if len(decoded) != expected_pixels * 3:
        raise ValueError(f"Truncated RGB frame: {len(decoded)} bytes")
    return shape


class DDPReceiver:
    """Validate sequential DDP packet offsets, including missing middle packets."""

    def __init__(self, pixels: int):
        self.expected_bytes = pixels * 3
        self.counts = [0, 0, 0, 0, 0]  # packets, bytes, PUSH, complete, invalid
        self.offset = 0
        self.sequence = None
        self.intact = False

    def feed(self, data: bytes) -> None:
        self.counts[0] += 1
        self.counts[1] += len(data)
        if len(data) < 10:
            self.counts[4] += 1
            self.intact = False
            return
        flags, sequence, datatype, destination, offset, length = struct.unpack(
            ">BBBBIH", data[:10]
        )
        if (
            flags & 0xC0 != 0x40
            or datatype != 0x0B
            or destination != 1
            or length != len(data) - 10
            or offset + length > self.expected_bytes
        ):
            self.counts[4] += 1
            self.intact = False
            return
        if offset == 0:
            self.sequence, self.offset, self.intact = sequence, 0, True
        self.intact = (
            self.intact and sequence == self.sequence and offset == self.offset
        )
        self.offset = offset + length
        if flags & 1:
            self.counts[2] += 1
            self.counts[3] += self.intact and self.offset == self.expected_bytes
            self.intact = False


def worker(args):
    sys.path.insert(0, args.repo)
    if args.loop == "uvloop":
        import uvloop

        factory = uvloop.new_event_loop
    elif args.loop == "winloop":
        import winloop

        factory = winloop.new_event_loop
    else:
        factory = asyncio.new_event_loop
    from aiohttp import web

    from ledfx.core import LedFxCore
    from ledfx.devices.ddp import DDPDevice
    from ledfx.events import Event
    from ledfx.virtuals import Virtual

    metrics = {
        "assemble": [],
        "flush": [],
        "visualise": [],
        "effect": [],
        "loop_lag": [],
    }
    profiles = {name: cProfile.Profile() for name in ("main", "render", "effect")}
    profiling = False

    def timed(fn, key):
        def call(*a, **kw):
            start = time.perf_counter()
            profile = profiles.get("render" if key in ("assemble", "flush") else key)
            selected = "render" if key in ("assemble", "flush") else key
            if profiling and profile is not None and args.profile == selected:
                result = profile.runcall(fn, *a, **kw)
            else:
                result = fn(*a, **kw)
            metrics[key].append([start, time.perf_counter() - start])
            return result

        return call

    Virtual.assemble_frame = timed(Virtual.assemble_frame, "assemble")
    DDPDevice.flush = timed(DDPDevice.flush, "flush")
    logging.basicConfig(level=logging.WARNING)
    with patch("ledfx.core.asyncio.new_event_loop", factory):
        core = LedFxCore(
            args.directory, host="127.0.0.1", port=args.port, offline_mode=True
        )
    core.config.visualisation_fps = args.preview_fps
    # Explicit benchmark-only bypass of the product's 65536-pixel UI cap.
    object.__setattr__(core.config, "visualisation_maxlen", args.vis_pixels)
    core.config.transmission_mode = "compressed"
    core.setup_visualisation_events()
    for kind in (Event.VIRTUAL_UPDATE, Event.DEVICE_UPDATE):
        for listener in core.events._listeners.get(kind, []):
            listener.callback = timed(listener.callback, "visualise")
    # Keep host media/hotplug services out of this synthetic experiment.
    core._start_audio_device_monitor = lambda: None
    from ledfx.nowplaying.providers.mpris import MPRISNowPlayingProvider
    from ledfx.nowplaying.providers.smtc import SMTCNowPlayingProvider

    MPRISNowPlayingProvider.start = lambda self: None
    SMTCNowPlayingProvider.start = lambda self: None

    async def begin_measurement(request):
        nonlocal profiling
        profiling = bool(args.profile)
        if args.profile == "main":
            profiles["main"].enable()
        return web.json_response({"started": True})

    async def end_measurement(request):
        nonlocal profiling
        profiling = False
        profiles["main"].disable()
        return web.json_response({"stopped": True})

    core.http.app.router.add_post("/benchmark/start", begin_measurement)
    core.http.app.router.add_post("/benchmark/stop", end_measurement)

    async def measure_loop_lag():
        while True:
            start = time.perf_counter()
            await asyncio.sleep(0.01)
            now = time.perf_counter()
            metrics["loop_lag"].append([now, max(0, now - start - 0.01)])

    async def start():
        try:
            await core.async_start()
            config = {
                "name": "Benchmark",
                "pixel_count": args.pixels,
                "refresh_rate": args.refresh_rate,
            }
            if args.device == "ddp":
                config.update(ip_address="127.0.0.1", port=args.sink_port)
            await core.devices.add_new_device(args.device, config)
            cls = core.effects.get_class("rainbow")
            cls.effect_loop = timed(cls.effect_loop, "effect")
            core.virtuals.set_effect(
                "benchmark",
                "rainbow",
                cls.config_model().model_validate(
                    {"speed": args.effect_speed, "blur": 0}
                ),
                store=False,
            )
            Path(args.directory, "ready.json").write_text(
                json.dumps(
                    {
                        "loop": str(type(core.loop)),
                        "pid": os.getpid(),
                        "refresh_rate": core.virtuals.get("benchmark").refresh_rate,
                    }
                )
            )
            core.loop.create_task(measure_loop_lag())
        except BaseException:
            logging.getLogger(__name__).exception("Benchmark startup failed")
            await core.async_stop(1)

    core.loop.create_task(start())
    try:
        core.loop.run_forever()
    finally:
        profiles["main"].disable()
        Path(args.directory, "metrics.json").write_text(json.dumps(metrics))
        if args.profile:
            profiles[args.profile].dump_stats(
                str(Path(args.directory, f"{args.profile}.prof"))
            )
        core.loop.close()


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def summarize(times, start, end):
    values = sorted(d * 1000 for t, d in times if start <= t < end)
    return {
        "count": len(values),
        "fps": round(len(values) / (end - start), 2),
        "mean_ms": round(statistics.mean(values), 3) if values else 0,
        "p95_ms": round(values[int(0.95 * (len(values) - 1))], 3) if values else 0,
    }


def spawn_worker(command: list[str], log_path: Path) -> subprocess.Popen:
    with log_path.open("w", encoding="utf-8") as log:
        return subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)


def append_result(path: str, result: dict) -> None:
    with open(path, "a", encoding="utf-8") as out:
        out.write(json.dumps(result) + "\n")


def stop_worker(proc, process) -> None:
    """Reap the launcher and its real Windows worker on failed runs too."""
    import psutil

    if proc is None:
        return
    children = []
    try:
        children = psutil.Process(proc.pid).children(recursive=True)
    except psutil.NoSuchProcess:
        pass
    if process is not None and process.pid != proc.pid:
        children.append(process)
    for child in children:
        try:
            child.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(children, timeout=5)
    for child in alive:
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


async def run_one(args, loop, vis, repeat):
    import aiohttp
    import psutil

    with tempfile.TemporaryDirectory(prefix="ledfx-pixels-") as directory:
        port = free_port()
        sink = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sink.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
        sink.bind(("127.0.0.1", 0))
        sink.settimeout(0.2)
        ddp = DDPReceiver(args.pixels)
        stop = threading.Event()

        def drain():
            while not stop.is_set():
                try:
                    data = sink.recv(65536)
                except TimeoutError:
                    continue
                ddp.feed(data)

        receiver = threading.Thread(target=drain)
        receiver.start()
        command = [
            sys.executable,
            __file__,
            "--worker",
            "--repo",
            args.repo,
            "--loop",
            loop,
            "--directory",
            directory,
            "--port",
            str(port),
            "--sink-port",
            str(sink.getsockname()[1]),
            "--pixels",
            str(args.pixels),
            "--vis-pixels",
            str(args.pixels if vis == "full" else 81),
            "--device",
            args.device,
            "--refresh-rate",
            str(args.refresh_rate),
            "--preview-fps",
            str(args.preview_fps),
            "--effect-speed",
            str(args.effect_speed),
        ]
        if args.profile:
            command.extend(["--profile", args.profile])
        if args.sampling:
            command = [
                sys.executable,
                "-m",
                "profiling.sampling",
                "run",
                "--all-threads",
                "--mode",
                args.sampling,
                "--binary",
                "-o",
                str(Path(directory, "sampling.bin")),
                *command[1:],
            ]
        proc = process = None
        try:
            proc = await asyncio.to_thread(
                spawn_worker, command, Path(directory, "server.log")
            )
            ready = Path(directory, "ready.json")
            deadline = time.monotonic() + 60
            while not ready.exists():
                if proc.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError(Path(directory, "server.log").read_text())
                await asyncio.sleep(0.1)
            # Windows venv python.exe is a launcher, not the actual server.
            process = psutil.Process(json.loads(ready.read_text())["pid"])
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            ) as session:
                ws = None
                if vis != "none":
                    ws = await session.ws_connect(
                        f"http://127.0.0.1:{port}/api/websocket",
                        max_msg_size=max(1024 * 1024, args.pixels * 4 + 4096),
                    )
                    await ws.send_json(
                        {
                            "id": 1,
                            "type": "subscribe_event",
                            "event_type": "visualisation_update",
                        }
                    )
                ws_count = ws_bytes = 0
                ws_changed = 0
                previous_pixels = None
                shape = None
                decoded_pixels = None

                async def receive_for(duration, measure):
                    nonlocal \
                        ws_count, \
                        ws_bytes, \
                        shape, \
                        decoded_pixels, \
                        ws_changed, \
                        previous_pixels
                    deadline = time.perf_counter() + duration
                    if ws is None:
                        await asyncio.sleep(duration)
                        return
                    while time.perf_counter() < deadline:
                        try:
                            msg = await ws.receive(
                                timeout=max(0.01, deadline - time.perf_counter())
                            )
                        except TimeoutError:
                            break
                        if msg.type in (
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.CLOSE,
                            aiohttp.WSMsgType.ERROR,
                        ):
                            raise RuntimeError(
                                f"Websocket closed during measurement: {msg}"
                            )
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            continue
                        if "visualisation_update" not in msg.data:
                            continue
                        if measure:
                            ws_count += 1
                            ws_bytes += len(msg.data.encode())
                            event = json.loads(msg.data)
                            decoded_pixels = (
                                args.pixels if vis == "full" else min(81, args.pixels)
                            )
                            shape = validate_frame(event, decoded_pixels)
                            if event["pixels"] != previous_pixels:
                                ws_changed += 1
                            previous_pixels = event["pixels"]

                await receive_for(args.warmup, False)
                async with session.post(
                    f"http://127.0.0.1:{port}/benchmark/start"
                ) as response:
                    response.raise_for_status()
                cpu0 = sum(process.cpu_times()[:2])
                counts0 = ddp.counts.copy()
                begin = time.perf_counter()
                await receive_for(args.seconds, True)
                end = time.perf_counter()
                cpu1 = sum(process.cpu_times()[:2])
                counts1 = ddp.counts.copy()
                rss = process.memory_info().rss
                async with session.post(
                    f"http://127.0.0.1:{port}/benchmark/stop"
                ) as response:
                    response.raise_for_status()
                if ws:
                    await ws.close()
                async with session.post(f"http://127.0.0.1:{port}/api/power", json={}):
                    pass
            await asyncio.to_thread(proc.wait, 30)
            metrics = json.loads(Path(directory, "metrics.json").read_text())
            server_log = Path(directory, "server.log").read_text(encoding="utf-8")
            if (
                "frame render failed" in server_log
                or "Exception in thread" in server_log
            ):
                raise RuntimeError(
                    f"Worker thread failed during benchmark:\n{server_log}"
                )
            result = {
                "loop": loop,
                "platform": sys.platform,
                "python": f"{sys.version_info.major}.{sys.version_info.minor}",
                "repeat": repeat,
                "device": args.device,
                "pixels": args.pixels,
                "refresh_rate": args.refresh_rate,
                "effective_refresh_rate": json.loads(ready.read_text())["refresh_rate"],
                "preview_fps": args.preview_fps,
                "effect_speed": args.effect_speed,
                "stream": vis,
                "profiled": (
                    f"sampling-{args.sampling}"
                    if args.sampling
                    else args.profile or False
                ),
                "loop_class": json.loads(ready.read_text())["loop"],
                "seconds": round(end - begin, 3),
                "server_cpu_pct": round((cpu1 - cpu0) / (end - begin) * 100, 1),
                "rss_mb": round(rss / 1e6, 1),
                "ws_fps": round(ws_count / (end - begin), 2),
                "ws_changed_fps": round(ws_changed / (end - begin), 2),
                "ws_MB_s": round(ws_bytes / (end - begin) / 1e6, 2),
                "ws_shape": shape,
                "ws_decoded_pixels": decoded_pixels,
                "ddp_MB_s": round((counts1[1] - counts0[1]) / (end - begin) / 1e6, 2),
                "ddp_push_fps": round((counts1[2] - counts0[2]) / (end - begin), 2),
                "ddp_complete_fps": round((counts1[3] - counts0[3]) / (end - begin), 2),
                "ddp_invalid_packets": counts1[4] - counts0[4],
                "ddp_packets": counts1[0] - counts0[0],
                **{k: summarize(v, begin, end) for k, v in metrics.items()},
            }
            if not result["assemble"]["count"]:
                raise RuntimeError("No rendered frames during measurement")
            if vis != "none" and not ws_count:
                raise RuntimeError("No websocket pixel frames during measurement")
            if args.device == "ddp" and (
                counts1[3] == counts0[3] or result["ddp_invalid_packets"]
            ):
                raise RuntimeError(
                    f"No complete DDP frames or malformed packets: {result}"
                )
            print(json.dumps(result), flush=True)
            await asyncio.to_thread(append_result, args.output, result)
            return result
        finally:
            await asyncio.to_thread(stop_worker, proc, process)
            stop.set()
            receiver.join()
            sink.close()
            # Preserve diagnostics even when validation/startup fails.
            artifact_dir = (
                Path(str(args.output) + ".artifacts") / f"{repeat}-{vis}-{loop}"
            )
            artifact_dir.mkdir(parents=True, exist_ok=True)
            for name in (
                "server.log",
                "metrics.json",
                "main.prof",
                "render.prof",
                "effect.prof",
                "sampling.bin",
            ):
                source = Path(directory, name)
                if source.exists():
                    shutil.copy2(source, artifact_dir / name)


async def driver(args):
    rows = []
    for repeat in range(args.repeats):
        loops = args.loops.split(",")
        if repeat % 2:
            loops.reverse()
        for vis in args.streams.split(","):
            for loop in loops:
                rows.append(await run_one(args, loop, vis, repeat))
    summary = summarize_runs(rows)
    Path(str(args.output) + ".summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    if args.baseline:
        baseline = [
            json.loads(line)
            for line in Path(args.baseline).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        regressions = compare_baseline(rows, baseline, args.max_regression)
        if regressions:
            raise RuntimeError(
                "Performance baseline failed:\n" + "\n".join(regressions)
            )


def scenario_key(row: dict) -> str:
    return "/".join(
        str(row[k])
        for k in (
            "platform",
            "python",
            "loop",
            "device",
            "pixels",
            "refresh_rate",
            "preview_fps",
            "effect_speed",
            "stream",
            "profiled",
        )
    )


def summarize_runs(rows: list[dict]) -> dict:
    groups = {}
    for row in rows:
        groups.setdefault(scenario_key(row), []).append(row)
    summary = {}
    for key, runs in groups.items():
        metrics = {}
        for name in (
            "render_fps",
            "effect_fps",
            "ws_fps",
            "ws_changed_fps",
            "ddp_complete_fps",
            "server_cpu_pct",
            "rss_mb",
        ):
            values = [
                r["assemble"]["fps"]
                if name == "render_fps"
                else r["effect"]["fps"]
                if name == "effect_fps"
                else r[name]
                for r in runs
            ]
            metrics[name] = {
                "median": statistics.median(values),
                "min": min(values),
                "max": max(values),
            }
        summary[key] = {"runs": len(runs), "metrics": metrics}
    return summary


def compare_baseline(
    rows: list[dict], baseline: list[dict], tolerance: float
) -> list[str]:
    """Explicit opt-in throughput gate; do not compare unlike scenarios."""
    previous, current = summarize_runs(baseline), summarize_runs(rows)
    failures = []
    for key, group in current.items():
        if key not in previous:
            failures.append(f"{key}: no matching baseline scenario")
            continue
        for metric in (
            "render_fps",
            "effect_fps",
            "ws_fps",
            "ws_changed_fps",
            "ddp_complete_fps",
        ):
            before = previous[key]["metrics"][metric]["median"]
            after = group["metrics"][metric]["median"]
            if before > 0 and after < before * (1 - tolerance):
                failures.append(
                    f"{key} {metric}: {before:.2f} -> {after:.2f} (>{tolerance:.0%} regression)"
                )
    return failures


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--repo",
        default=str(Path(__file__).resolve().parent.parent),
        help="LedFx source checkout",
    )
    p.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    p.add_argument(
        "--loop", choices=["standard", "uvloop", "winloop"], help=argparse.SUPPRESS
    )
    p.add_argument(
        "--loops",
        default="auto",
        help="Comma-separated loops; auto uses standard plus the installed platform accelerator",
    )
    p.add_argument("--directory", help=argparse.SUPPRESS)
    p.add_argument("--port", type=int, help=argparse.SUPPRESS)
    p.add_argument("--sink-port", type=int, help=argparse.SUPPRESS)
    p.add_argument("--pixels", type=int, default=500000)
    p.add_argument(
        "--refresh-rate",
        type=int,
        default=60,
        help="Requested output FPS; LedFx rounds to a supported rate",
    )
    p.add_argument(
        "--preview-fps", type=int, default=60, help="Websocket rate limit (1–60)"
    )
    p.add_argument(
        "--effect-speed",
        type=float,
        default=6,
        help="Rainbow speed: 6 requests 60 effect updates/sec (0.1–20)",
    )
    p.add_argument("--vis-pixels", type=int, default=81, help=argparse.SUPPRESS)
    p.add_argument("--seconds", type=float, default=8)
    p.add_argument("--warmup", type=float, default=2)
    p.add_argument("--streams", default="none,default,full")
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--device", choices=["ddp", "dummy"], default="ddp")
    p.add_argument(
        "--output",
        help="New JSONL results file; metadata, summaries, logs and profiles are saved alongside it",
    )
    p.add_argument(
        "--profile",
        nargs="?",
        const="main",
        choices=["main", "render", "effect"],
        help="Profile one measured thread per run (default: main). CPython 3.12 cannot run independent cProfiles simultaneously. Inspect .prof files with pstats or SnakeViz",
    )
    p.add_argument(
        "--sampling",
        choices=["wall", "cpu", "gil"],
        help="Python 3.15 all-thread sampling, including startup/warmup; saves replayable sampling.bin",
    )
    p.add_argument(
        "--baseline",
        help="Previous JSONL results; fail when median throughput regresses",
    )
    p.add_argument(
        "--max-regression",
        type=float,
        default=0.10,
        help="Allowed fractional throughput regression (default 0.10)",
    )
    args = p.parse_args(argv)
    if args.sampling and (sys.version_info < (3, 15) or args.profile):
        p.error(
            "--sampling requires Python 3.15+ and cannot be combined with --profile"
        )
    if (
        args.pixels <= 0
        or args.vis_pixels <= 0
        or args.seconds <= 0
        or args.warmup < 0
        or args.repeats <= 0
        or not all(
            math.isfinite(n) for n in (args.seconds, args.warmup, args.max_regression)
        )
    ):
        p.error(
            "pixels, seconds and repeats must be positive; warmup must be nonnegative"
        )
    if (
        args.refresh_rate <= 0
        or not 1 <= args.preview_fps <= 60
        or not 0.1 <= args.effect_speed <= 20
    ):
        p.error(
            "refresh-rate must be positive, preview-fps in 1–60, effect-speed in 0.1–20"
        )
    if not 0 <= args.max_regression < 1:
        p.error("max-regression must be in [0, 1)")
    if not all(s in {"none", "default", "full"} for s in args.streams.split(",")):
        p.error("streams must contain only none,default,full")
    accelerator = "winloop" if sys.platform == "win32" else "uvloop"
    if args.loops == "auto":
        args.loops = "standard" + (
            "," + accelerator if importlib.util.find_spec(accelerator) else ""
        )
    for loop in args.loops.split(","):
        if loop not in {"standard", "uvloop", "winloop"}:
            p.error(f"Unknown loop: {loop}")
        if loop != "standard" and importlib.util.find_spec(loop) is None:
            p.error(
                f"{loop} is not installed; install it in this environment to compare it"
            )
    if args.worker and not all((args.directory, args.port, args.sink_port, args.loop)):
        p.error("Internal worker requires directory, port, sink-port and loop")
    return args


def write_metadata(args) -> None:
    versions = {}
    for package in (
        "aiohttp",
        "numpy",
        "uvloop",
        "winloop",
        "aubio-ledfx",
        "pyfastnoiselite-ledfx",
        "samplerate-ledfx",
        "audio-hotplug",
        "python-rtmidi",
        "pyflac",
        "psutil",
    ):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None

    def git(*command):
        try:
            result = subprocess.run(
                ["git", "-C", args.repo, *command],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return None

    metadata = {
        "python": sys.version,
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "packages": versions,
        "revision": git("rev-parse", "HEAD"),
        "working_tree": git("status", "--short"),
        "arguments": vars(args),
        "notes": "Loopback synthetic Rainbow workload. 100% CPU is one server core. Receiver CPU excluded. Full stream bypasses UI cap. Profiled runs include profiler overhead.",
    }
    Path(str(args.output) + ".metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )


def main() -> None:
    args = parse_args()
    if args.worker:
        worker(args)
    else:
        if args.output is None:
            args.output = str(
                Path(tempfile.mkdtemp(prefix="ledfx-pixel-results-"), "results.jsonl")
            )
        if Path(args.output).exists():
            raise SystemExit(
                f"Refusing to mix runs with existing results: {args.output}"
            )
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        write_metadata(args)
        print(f"Results: {args.output}", file=sys.stderr)
        asyncio.run(driver(args))


if __name__ == "__main__":
    main()
