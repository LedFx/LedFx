"""Characterize real LedFx sender flush paths without contacting devices.

  python tools/sender_bench.py --senders all --pixels 60,300,1000 --output /tmp/senders.jsonl
  python tools/sender_bench.py --senders ddp,artnet,e131 --pixels 500000 --seconds 3 --repeats 3 --output /tmp/large.jsonl
  python tools/sender_bench.py --senders udp-adaptive,udp-warls --patterns dense,sparse,static --pixels 60 --output /tmp/deltas.jsonl
  python3.15 tools/sender_bench.py --senders e131 --pixels 10000 --sampling cpu --output /tmp/profile.jsonl

encode measures real flush/serialization with a counting sink. loopback uses real
UDP or TCP writes and a separate receiver process (excluded from sender CPU).
Every case first decodes emitted RGB independently, then validates received
packets against complete expected packet sets. Protocols without a frame ID only
support ordered-set validation, not a guarantee of atomic display updates.
OpenRGB is a TCP byte stream: write calls are not network packets. Serial and
Hue are encoding-only; baud-rate, DTLS and hardware capacity are not simulated.
Discovery, authentication and periodic SDK discovery/keepalive threads are
excluded; synchronous per-frame SDK serialization remains included.

Frames are precomputed float64 RGB, alternating dense or roughly 1%-changed
inputs (at least one pixel), or
static. Time is spent in flush, not effects, virtual assembly or websocket work.
--fps 0 measures saturation; use --fps 60 to measure a paced workload. Static
suppression is reported as zero sends, never as exceptionally high delivered FPS.
The default packet-count budget skips impractical per-pixel OSC cases explicitly.
Limits and unmeasured backends are written alongside the results. These local
measurements do not predict Wi-Fi, device firmware or physical LED latency.
"""

import argparse
import importlib.metadata
import ipaddress
import json
import math
import multiprocessing
import platform
import shutil
import socket
import statistics
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.sender_bench_protocols import (
    SPECS,
    UNMEASURED,
    canonical_packet,
    check_payload,
    make_sender,
)


class Sink:
    """Retain actual short-write semantics; remap every destination to loopback."""

    def __init__(self) -> None:
        self.capture: list[bytes] | None = []
        self.sock: socket.socket | None = None
        self.address = ("127.0.0.1", 0)
        self.transport = "udp"
        self.reset()

    def reset(self) -> None:
        self.calls = self.bytes = self.short_writes = self.errors = self.max_bytes = 0

    def send(self, data: Any) -> int:
        self.calls += 1
        self.max_bytes = max(self.max_bytes, len(data))
        if self.capture is not None:
            self.capture.append(bytes(data))
        try:
            sent = (
                len(data)
                if self.sock is None
                else (
                    self.sock.send(data)
                    if self.transport == "tcp"
                    else self.sock.sendto(data, self.address)
                )
            )
        except OSError:
            self.errors += 1
            raise
        self.bytes += sent
        self.short_writes += sent != len(data)
        return sent

    def sendto(self, data: Any, address: Any) -> int:
        return self.send(data)

    def write(self, data: Any) -> int:
        return self.send(data)

    def setsockopt(self, *args: Any) -> None:
        if self.sock is not None:
            self.sock.setsockopt(*args)

    def close(self) -> None:
        if self.sock is not None:
            self.sock.close()
            self.sock = None


class PacketMatcher:
    """Require every packet of an expected frame, in order and from one variant."""

    def __init__(
        self,
        name: str,
        frames: list[list[bytes]],
        partial_variants: set[int] | None = None,
    ) -> None:
        self.name = name
        self.partial_variants = partial_variants or set()
        self.keepalive_sets = 0
        self.pending_partial = False
        self.templates: dict[bytes, set[tuple[int, int, int]]] = {}
        for variant, frame in enumerate(frames):
            for position, packet in enumerate(frame):
                key = canonical_packet(name, packet)
                self.templates.setdefault(key, set()).add(
                    (variant, position, len(frame))
                )
        self.candidates: set[tuple[int, int, int]] = set()
        self.sequence: int | None = None
        self.packets = self.bytes = self.complete = self.invalid = 0

    def feed(self, data: bytes) -> None:
        self.packets += 1
        self.bytes += len(data)
        try:
            entries = self.templates.get(canonical_packet(self.name, data), set())
        except IndexError:
            entries = set()
        if not entries:
            self.invalid += 1
            self.candidates.clear()
            return
        sequence = data[1] if self.name == "ddp" else None
        if sequence != self.sequence:
            self.candidates.clear()
        self.sequence = sequence
        if self.pending_partial and not any(
            (variant, position, length) in self.candidates
            for variant, position, length in entries
        ):
            self.finish()
        next_candidates = set()
        for variant, position, length in entries:
            if position == 0 or (variant, position, length) in self.candidates:
                next_candidates.add((variant, position + 1, length))
        completed = {
            variant
            for variant, position, length in next_candidates
            if position == length
        }
        if completed - self.partial_variants:
            self.complete += 1
            self.pending_partial = False
            next_candidates.clear()
        elif completed:
            self.pending_partial = True
            next_candidates = {item for item in next_candidates if item[1] < item[2]}
        self.candidates = next_candidates

    def finish(self) -> None:
        if self.pending_partial:
            self.keepalive_sets += 1
            self.pending_partial = False


def receiver(
    connection: Any,
    name: str,
    frames: list[list[bytes]],
    transport: str,
    partial_variants: set[int],
    bind: str = "127.0.0.1",
) -> None:
    matcher = PacketMatcher(name, frames, partial_variants)
    sock = socket.socket(
        socket.AF_INET, socket.SOCK_STREAM if transport == "tcp" else socket.SOCK_DGRAM
    )
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
    sock.bind((bind, 0))
    if transport == "tcp":
        sock.listen(1)
    connection.send(sock.getsockname()[1])
    accepted = None
    try:
        if transport == "tcp":
            sock.settimeout(10)
            accepted, _ = sock.accept()
            source = accepted
        else:
            source = sock
        source.settimeout(0.02)
        buffer = bytearray()
        stopping = False
        resetting = False
        deadline = 0.0
        while True:
            if connection.poll():
                message = connection.recv()
                if message == "reset":
                    resetting = True
                else:
                    stopping = True
                    deadline = time.monotonic() + 0.5
            try:
                data = source.recv(65535)
                if not data:
                    break
                if transport == "tcp":
                    buffer.extend(data)
                    while len(buffer) >= 16:
                        if buffer[:4] != b"ORGB":
                            matcher.invalid += 1
                            buffer.clear()
                            break
                        size = 16 + int.from_bytes(buffer[12:16], sys.byteorder)
                        if size > 16 + 6 + 65535 * 4 or size < 22:
                            raise ValueError("Invalid OpenRGB stream length")
                        if len(buffer) < size:
                            break
                        matcher.feed(bytes(buffer[:size]))
                        del buffer[:size]
                else:
                    matcher.feed(data)
            except TimeoutError:
                if resetting:
                    if not matcher.complete or matcher.invalid:
                        raise ValueError(
                            "Initial full frame was not delivered before delta measurements"
                        )
                    matcher.packets = matcher.bytes = matcher.complete = (
                        matcher.invalid
                    ) = 0
                    matcher.keepalive_sets = 0
                    matcher.pending_partial = False
                    matcher.candidates.clear()
                    matcher.sequence = None
                    connection.send({"reset": True})
                    resetting = False
                if stopping:
                    break
            if stopping and time.monotonic() >= deadline:
                break
        matcher.finish()
        connection.send(
            {
                "packets": matcher.packets,
                "receive_buffer_bytes": source.getsockopt(
                    socket.SOL_SOCKET, socket.SO_RCVBUF
                ),
                "bytes": matcher.bytes,
                "complete_frames": matcher.complete,
                "partial_keepalive_sets": matcher.keepalive_sets,
                "invalid_packets": matcher.invalid,
                "trailing_tcp_bytes": len(buffer),
            }
        )
    except Exception as error:  # noqa: BLE001 - preserve failed benchmark cases
        connection.send({"error": repr(error)})
    finally:
        if accepted is not None:
            accepted.close()
        sock.close()
        connection.close()


def frame_pair(pixels: int, pattern: str) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(2058)
    first = rng.integers(0, 256, (pixels, 3)).astype(np.float64)
    second = first.copy()
    count = pixels if pattern == "dense" else max(1, pixels // 100)
    if pattern != "static":
        second[:count] = (second[:count] + 73) % 256
    return first, second


def skip_reason(name: str, pixels: int, mode: str, packet_budget: int) -> str | None:
    spec = SPECS[name]
    if pixels > spec.max_pixels:
        return f"selected implementation/format limit: {spec.max_pixels} pixels; {spec.note}"
    if mode == "loopback" and spec.transport not in ("udp", "tcp"):
        return (
            f"{spec.transport} hardware/session not simulated; encoding-only coverage"
        )
    if name.startswith("osc-") and name != "osc-all":
        estimate = pixels * (3 if name == "osc-channels" else 1)
    elif name in ("artnet", "e131"):
        estimate = math.ceil(pixels / 170) + (name == "e131")
    elif name in ("ddp", "udp-dnrgb"):
        estimate = math.ceil(pixels / (480 if name == "ddp" else 489))
    else:
        estimate = 1
    if estimate > packet_budget:
        return f"benchmark packet budget: estimated {estimate} > {packet_budget}; increase --max-packets to include"
    return None


def run_case(
    name: str, pixels: int, pattern: str, mode: str, args: argparse.Namespace
) -> dict:
    spec = SPECS[name]
    inputs = frame_pair(pixels, pattern)
    sink = Sink()
    sender = make_sender(name, pixels, sink)
    templates = []
    previous = None
    for frame in (inputs[0], inputs[1], inputs[0]):
        sink.capture = []
        sender.flush(frame)
        packets = sink.capture
        if packets:
            check_payload(name, packets, frame, previous)
            templates.append(packets)
        elif previous is None or not np.array_equal(frame, previous):
            raise ValueError("Sender silently omitted a changed frame")
        previous = frame
    if not templates:
        raise ValueError("No packets for payload validation")
    partial_variants = set()
    if name.startswith("udp-") and pattern == "static":
        # Include timed keepalive packets as legitimate updates, but never
        # count an incomplete multi-packet refresh as a complete frame.
        sender.last_frame_sent_time = 0
        sink.capture = []
        sender.flush(inputs[0])
        if sink.capture:
            check_payload(name, sink.capture, inputs[0], inputs[0])
            if name == "udp-dnrgb" and len(sink.capture) < math.ceil(pixels / 489):
                partial_variants.add(len(templates))
            templates.append(sink.capture)
    sink.capture = None
    conn = process = None
    try:
        if mode == "loopback":
            context = multiprocessing.get_context("spawn")
            conn, child = context.Pipe()
            process = context.Process(
                target=receiver,
                args=(
                    child,
                    name,
                    templates,
                    spec.transport,
                    partial_variants,
                    args.bind,
                ),
            )
            process.start()
            child.close()
            if not conn.poll(10):
                raise TimeoutError("Receiver did not bind")
            sink.address = (args.bind, conn.recv())
            sink.transport = spec.transport
            sink.sock = socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM if spec.transport == "tcp" else socket.SOCK_DGRAM,
            )
            sink.sock.settimeout(5)
            if spec.transport == "tcp":
                sink.sock.connect(sink.address)
        if (
            conn is not None
            and pattern != "dense"
            and name in ("udp-warls", "udp-adaptive", "udp-dnrgb")
        ):
            # Delta/keepalive delivery only has meaning after the receiver has
            # a complete initial image. Drain and exclude that seed from timing.
            sender.last_frame = np.full(inputs[0].shape, -1)
            sender.last_frame_sent_time = 0
            sender.flush(inputs[0])
            conn.send("reset")
            if not conn.poll(10) or conn.recv() != {"reset": True}:
                raise ValueError("Could not seed receiver state")
        sink.reset()
        timings, seconds, cpu_seconds = measure_flushes(sender, inputs, args)
        frame_count = len(timings)
        received = None
        if conn is not None:
            conn.send("stop")
            if not conn.poll(10):
                raise TimeoutError("Receiver did not finish")
            received = conn.recv()
            if (
                "error" in received
                or received.get("invalid_packets")
                or received.get("trailing_tcp_bytes")
            ):
                raise ValueError(f"Receiver validation failed: {received}")
            if sink.calls and not (
                received["complete_frames"]
                or (pattern == "static" and received["partial_keepalive_sets"])
            ):
                raise ValueError(f"No complete frames received: {received}")
        if sink.errors or sink.short_writes:
            raise ValueError(
                f"Send errors={sink.errors}, short writes={sink.short_writes}"
            )
        return {
            "status": "ok",
            "seconds": round(seconds, 6),
            "input_dtype": "float64",
            "flush_calls": frame_count,
            "flush_fps": round(frame_count / seconds, 3),
            "flush_mean_ms": round(statistics.mean(timings) * 1000, 6),
            "flush_p95_ms": round(float(np.percentile(timings, 95)) * 1000, 6),
            "sender_cpu_pct": round(cpu_seconds / seconds * 100, 2),
            "cpu_ms_per_flush": round(cpu_seconds / frame_count * 1000, 6),
            "write_calls": sink.calls,
            "write_calls_per_flush": round(sink.calls / frame_count, 3),
            "application_bytes": sink.bytes,
            "application_MB_s": round(sink.bytes / seconds / 1e6, 3),
            "application_bytes_per_flush": round(sink.bytes / frame_count, 3),
            "max_write_bytes": sink.max_bytes,
            "udp_payload_over_1472": spec.transport == "udp" and sink.max_bytes > 1472,
            "received": received,
            "received_complete_fps": round(received["complete_frames"] / seconds, 3)
            if received
            else None,
            "preflight_packets_per_frame": [len(t) for t in templates],
            "partial_keepalive_variants": sorted(partial_variants),
            "preflight_bytes_per_frame": [sum(map(len, t)) for t in templates],
            "note": spec.note,
        }
    finally:
        sink.close()
        if process is not None:
            process.join(2)
            if process.is_alive():
                process.terminate()
                process.join(2)
        if conn is not None:
            conn.close()


def measure_flushes(
    sender: Any, inputs: tuple[np.ndarray, np.ndarray], args: argparse.Namespace
) -> tuple[list[float], float, float]:
    """Sampling marker excludes imports, setup, payload validation and teardown."""
    timings = []
    started = time.perf_counter()
    cpu = time.process_time()
    deadline = started + args.seconds
    frame_count = 0
    while time.perf_counter() < deadline:
        # The preflight ends on frame 0. Start with frame 1 to exercise deltas.
        frame = inputs[(frame_count + 1) % 2]
        begin = time.perf_counter()
        sender.flush(frame)
        elapsed = time.perf_counter() - begin
        timings.append(elapsed)
        frame_count += 1
        if args.fps:
            delay = (
                min(started + frame_count / args.fps, deadline) - time.perf_counter()
            )
            if delay > 0:
                time.sleep(delay)
    cpu_seconds = time.process_time() - cpu
    seconds = time.perf_counter() - started
    return timings, seconds, cpu_seconds


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--senders", default="ddp,artnet,e131,udp-dnrgb,opc,openrgb,osc-three,adalight"
    )
    parser.add_argument("--pixels", default="60,1000,10000,500000")
    parser.add_argument("--patterns", default="dense")
    parser.add_argument("--modes", default="encode,loopback")
    parser.add_argument("--seconds", type=float, default=2)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--fps", type=float, default=0)
    parser.add_argument("--max-packets", type=int, default=10000)
    parser.add_argument(
        "--bind",
        default="127.0.0.1",
        help="IPv4 loopback address for the local receiver",
    )
    parser.add_argument("--sampling", choices=["cpu", "wall", "gil"])
    parser.add_argument(
        "--sampled-worker", choices=["cpu", "wall", "gil"], help=argparse.SUPPRESS
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        address = ipaddress.ip_address(args.bind)
        if address.version != 4 or not address.is_loopback:
            parser.error("--bind must be an IPv4 loopback address")
    except ValueError:
        parser.error("--bind must be an IPv4 loopback address")
    args.senders = list(SPECS) if args.senders == "all" else args.senders.split(",")
    try:
        args.pixels = [int(n) for n in args.pixels.split(",")]
    except ValueError:
        parser.error("--pixels must contain positive integers")
    args.patterns = args.patterns.split(",")
    args.modes = args.modes.split(",")
    if (
        any(n not in SPECS for n in args.senders)
        or any(p not in ("dense", "sparse", "static") for p in args.patterns)
        or any(m not in ("encode", "loopback") for m in args.modes)
    ):
        parser.error("Unknown sender, pattern or mode")
    if (
        not args.pixels
        or min(args.pixels) < 1
        or args.repeats < 1
        or args.max_packets < 1
        or not math.isfinite(args.seconds)
        or args.seconds <= 0
        or not math.isfinite(args.fps)
        or args.fps < 0
    ):
        parser.error("Counts/durations must be positive and FPS finite and nonnegative")
    if args.output.exists():
        parser.error("Output already exists; use a new path")
    return args


def probe_loopback(bind: str) -> dict:
    """Expose local routing/fragmentation failures before blaming a sender."""
    delivery = {}
    for size in (1472, 1500, 3004, 16000, 65507):
        with (
            socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as incoming,
            socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as outgoing,
        ):
            incoming.bind((bind, 0))
            incoming.settimeout(0.1)
            outgoing.sendto(b"x" * size, incoming.getsockname())
            try:
                delivery[size] = len(incoming.recv(65535)) == size
            except TimeoutError:
                delivery[size] = False
    route = None
    if platform.system() == "Linux" and shutil.which("ip"):
        route = subprocess.run(
            ["ip", "route", "get", bind], capture_output=True, text=True, check=False
        ).stdout.strip()
    return {"address": bind, "udp_payload_delivered": delivery, "route": route}


def summarize(rows: list[dict]) -> list[dict]:
    groups = {}
    keys = (
        "sender",
        "pixels",
        "pattern",
        "mode",
        "requested_fps",
        "profiled",
        "loopback_address",
    )
    for row in rows:
        key = tuple(row.get(k) for k in keys)
        groups.setdefault(key, []).append(row)
    summaries = []
    for key, group in groups.items():
        item = dict(zip(keys, key))
        item["runs"] = len(group)
        item["statuses"] = [r["status"] for r in group]
        item["metrics"] = {}
        successful = [r for r in group if r["status"] == "ok"]
        for metric in (
            "flush_fps",
            "flush_mean_ms",
            "flush_p95_ms",
            "cpu_ms_per_flush",
            "sender_cpu_pct",
            "application_MB_s",
            "write_calls_per_flush",
            "application_bytes_per_flush",
            "received_complete_fps",
        ):
            values = [r[metric] for r in successful if r.get(metric) is not None]
            if values:
                item["metrics"][metric] = {
                    "median": statistics.median(values),
                    "min": min(values),
                    "max": max(values),
                }
        item["issues"] = sorted(
            {r.get("reason", r.get("error", "")) for r in group} - {""}
        )
        summaries.append(item)
    return summaries


def main() -> None:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.sampling:
        if sys.version_info < (3, 15):
            raise SystemExit("profiling.sampling requires Python 3.15")
        remaining = sys.argv[1:]
        if "--sampling" in remaining:
            i = remaining.index("--sampling")
            del remaining[i : i + 2]
        else:
            remaining = [
                item for item in remaining if not item.startswith("--sampling=")
            ]
        remaining.extend(["--sampled-worker", args.sampling])
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "profiling.sampling",
                "run",
                "--all-threads",
                "--mode",
                args.sampling,
                "--binary",
                "-o",
                str(args.output) + ".sampling.bin",
                __file__,
                *remaining,
            ],
            check=False,
        )
        raise SystemExit(result.returncode)
    metadata = {
        "platform": platform.platform(),
        "python": sys.version,
        "numpy": np.__version__,
        "packages": {
            p: importlib.metadata.version(p)
            for p in ("sacn", "stupidartnet", "python-osc")
        },
        "senders": {n: vars(s) for n, s in SPECS.items()},
        "unmeasured": UNMEASURED,
        "scope": __doc__,
        "sampling": args.sampled_worker,
        "arguments": {
            key: str(value) if isinstance(value, Path) else value
            for key, value in vars(args).items()
        },
        "loopback_probe": probe_loopback(args.bind)
        if "loopback" in args.modes
        else None,
        "git_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[1],
            text=True,
        ).strip(),
        "git_status": subprocess.check_output(
            ["git", "status", "--short"],
            cwd=Path(__file__).resolve().parents[1],
            text=True,
        ),
    }
    Path(str(args.output) + ".metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n"
    )
    failures = 0
    results = []
    with args.output.open("x") as output:
        for repeat in range(args.repeats):
            for pixels in args.pixels:
                for name in args.senders:
                    for pattern in args.patterns:
                        for mode in args.modes:
                            row = {
                                "sender": name,
                                "pixels": pixels,
                                "pattern": pattern,
                                "mode": mode,
                                "repeat": repeat,
                                "requested_fps": args.fps,
                                "profiled": args.sampled_worker or False,
                                "loopback_address": args.bind
                                if mode == "loopback"
                                else None,
                            }
                            reason = skip_reason(name, pixels, mode, args.max_packets)
                            if reason:
                                row.update(status="skipped", reason=reason)
                            else:
                                try:
                                    row.update(
                                        run_case(name, pixels, pattern, mode, args)
                                    )
                                except Exception as error:  # noqa: BLE001 - preserve failed benchmark cases
                                    traceback.print_exc(file=sys.stderr)
                                    row.update(status="failed", error=repr(error))
                                    failures += 1
                            results.append(row)
                            output.write(json.dumps(row) + "\n")
                            output.flush()
                            print(json.dumps(row), flush=True)
    Path(str(args.output) + ".summary.json").write_text(
        json.dumps(summarize(results), indent=2) + "\n"
    )
    raise SystemExit(bool(failures))


if __name__ == "__main__":
    main()
