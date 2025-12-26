#!/usr/bin/env python3
"""
Librosa analysis worker for LedFx.

Receives raw float32 PCM blocks over stdin using a small binary protocol:
    <msg_type: uint8><payload_len: uint32><payload: raw bytes>

Currently supported message types:
    1 = audio block (mono float32 PCM)
    255 = shutdown

Outputs feature messages as JSON lines on stdout, e.g.:
    {"type": "feature_update", "tempo": 124.7}

Logs debug/errors to stderr.

This worker is single-threaded and synchronous — it does not block LedFx
because it runs in its own OS process, ensuring a dedicated GIL.
"""

import sys
import json
import logging
import time
import numpy as np
import librosa
import timeit
from ledfx.utils import Teleplot

from ledfx.integrations.librosa_worker.protocol import (
    HEADER_STRUCT,
    MSG_TYPE_AUDIO,
    MSG_TYPE_CONFIG,
    MSG_TYPE_SHUTDOWN,
    LEDFX_RATE,
)

_LOGGER = logging.getLogger(__name__)

PROCESS_PERIOD_SECONDS = 2.0      # how often to analyze
BUFFER_SECONDS = 8.0              # audio buffer window for analysis
MIN_SECONDS_BEFORE_ANALYSIS = 2.0 # wait until at least 2s data


class AudioAnalyzer:
    """Encapsulates audio buffer and librosa analysis state."""
    
    def __init__(self):
        self.buffer = np.array([], dtype=np.float32)
        self.sample_rate = None
        self.max_len = None
        self.last_analysis_time = time.time()
        self.configured = False
        self.first = True

        # Rolling feature state for sections / moods
        self._feat_prev = None
        self._feat_mean = None
        self._section_cooldown = 0
        self._energy_mean = None
        self._energy_var = None
        self._onset_mean_mean = None
        self._onset_mean_var = None
        self._prev_z_energy = 0.0  # Store previous z-score for energy change detection

        # Tunable knobs (could come from config later)
        self._section_threshold = 0.4   # Lower = more sensitive (was 1.0, too high)
        self._section_min_gap_steps = 2 # with 2 s analysis step → min ~4 s between sections (was 8s)
    

    def handle_config(self, config: dict):
        """Update configuration from config message."""
        _LOGGER.error(f"Config received: {config}")

        self.sample_rate = config.get('sample_rate')
        self.window = config.get('sample_window', BUFFER_SECONDS)
        self.max_len = int(self.sample_rate * self.window)
        self.diag = config.get('diag', False)
        self.debug = config.get('debug', False)
        self.configured = True
        self.chill_z = config.get('chill_threshold', -0.3)
        self.build_z = config.get('build_threshold', 0.3)
        self.peak_z = config.get('peak_threshold', 0.7)
        self.ambient_z = config.get('ambient_threshold', -0.8)
    
    def process_audio_block(self, block: np.ndarray):
        """Add audio block to buffer and run analysis if throttle period elapsed."""
        # Skip processing if not configured yet
        if not self.configured:
            return

        # Append and slide buffer
        self.buffer = np.concatenate([self.buffer, block])
        if self.buffer.size > self.max_len:
            self.buffer = self.buffer[-self.max_len:]
        
        # Run analysis if enough data accumulated and enough time has passed
        current_time = time.time()
        if (self.buffer.size >= int(self.sample_rate * MIN_SECONDS_BEFORE_ANALYSIS) and 
            current_time - self.last_analysis_time >= PROCESS_PERIOD_SECONDS):
            start = timeit.default_timer()    
            
            self._analyze_and_emit()
            
            self.last_analysis_time = current_time

            if self.diag and not self.first:
                Teleplot.send(f"t_tot:{(timeit.default_timer() - start)*1000:.1f}")                

            # the first run of analysis has a high setup time, so do not measure
            if self.first:
                self.first = False

            
    def _analyze_and_emit(self):
        """Run librosa feature computation and emit JSON."""
        y = self.buffer
        _LOGGER.warning(f"Analyzing audio buffer of length {len(y)} samples")

        try:
            onset_env = librosa.onset.onset_strength(y=y, sr=self.sample_rate)
            tempo = librosa.beat.tempo(onset_envelope=onset_env, sr=self.sample_rate)
            tempo_val = float(tempo[0])

            # Basic spectral representation
            S = np.abs(librosa.stft(y, n_fft=2048, hop_length=512))

            # 1) Energy
            rms = float(librosa.feature.rms(S=S).mean())

            # 2) Timbre / brightness
            centroid = float(librosa.feature.spectral_centroid(S=S, sr=self.sample_rate).mean())
            bandwidth = float(librosa.feature.spectral_bandwidth(S=S, sr=self.sample_rate).mean())
            flatness = float(librosa.feature.spectral_flatness(S=S).mean())

            # 3) Rhythm stats from onset envelope
            onset_mean = float(onset_env.mean())
            onset_var = float(onset_env.var())

            # (Optional) Harmony snapshot – cheap 12-dim summary
            chroma = librosa.feature.chroma_stft(S=S, sr=self.sample_rate)
            chroma_mean = chroma.mean(axis=1).astype(float)  # 12-vector

        except Exception as e:
            # Do not crash worker — log error
            _LOGGER.error(f"onset_beat error: {e!r}")
            return

        # --- Build compact feature vector for section / mood logic ---

        curr_feat = np.concatenate([
            np.array(
                [
                    rms,
                    centroid,
                    bandwidth,
                    flatness,
                    onset_mean,
                    onset_var,
                    tempo_val,
                ],
                dtype=float,
            ),
            chroma_mean,  # 12 elements
        ])

        # --- Initialize state on first run ---
        if self._feat_mean is None or self._feat_prev is None:
            self._feat_mean = curr_feat.copy()
            self._feat_prev = curr_feat.copy()
            self._section_cooldown = 0
            section_change = False
            mood = "unknown"
            z_energy = 0.0
            z_density = 0.0
            dist = 0.0
        else:
            # --- Mood classification using z-scores (energy & density) ---

            # Init running stats on first real run
            if self._energy_mean is None:
                self._energy_mean = rms
                self._energy_var = 1e-6
                self._onset_mean_mean = onset_mean
                self._onset_mean_var = 1e-6

            # Exponential moving mean/variance (Welford-ish EMA)
            beta = 0.9  # closer to 1 = slower, more stable

            # Energy stats
            delta_e = rms - self._energy_mean
            self._energy_mean += (1.0 - beta) * delta_e
            self._energy_var = beta * self._energy_var + (1.0 - beta) * (delta_e ** 2)
            energy_std = max(self._energy_var ** 0.5, 1e-6)

            # Onset density stats
            delta_o = onset_mean - self._onset_mean_mean
            self._onset_mean_mean += (1.0 - beta) * delta_o
            self._onset_mean_var = beta * self._onset_mean_var + (1.0 - beta) * (delta_o ** 2)
            onset_std = max(self._onset_mean_var ** 0.5, 1e-6)

            # Z-scores: how many std above/below recent "normal"
            z_energy = (rms - self._energy_mean) / energy_std
            z_density = (onset_mean - self._onset_mean_mean) / onset_std
            
            # --- Update running mean for crude normalization ---
            alpha = 0.8  # smoothing factor
            self._feat_mean = alpha * self._feat_mean + (1.0 - alpha) * curr_feat

            # --- Section-change detection (distance between windows) ---
            diff = curr_feat - self._feat_prev
            norm = self._feat_mean + 1e-8
            dist = float(np.linalg.norm(diff / norm))
            
            # Also check for significant energy jumps (drops/buildups)
            energy_change = abs(z_energy - self._prev_z_energy)
            significant_energy_change = energy_change > 1.5  # Large energy shift

            # Cooldown so we don't spam section changes
            if self._section_cooldown > 0:
                self._section_cooldown -= 1
                section_change = False
            else:
                # Trigger on either: feature distance OR significant energy change
                if dist > self._section_threshold or significant_energy_change:
                    section_change = True
                    self._section_cooldown = self._section_min_gap_steps
                else:
                    section_change = False
            
            # Also consider brightness as a mood factor
            z_brightness = (centroid - 2000.0) / 1000.0  # Crude normalization around 2kHz

            # Consider tempo context
            tempo_fast = tempo_val > 130  # High BPM
            tempo_slow = tempo_val < 90   # Low BPM

            # Multi-dimensional mood classification (prioritize energy states)
            if z_energy < self.ambient_z and z_density < self.ambient_z:
                if tempo_slow:
                    mood = "ambient"      # Very low energy, low density, slow tempo
                else:
                    mood = "breakdown"    # Very low energy, low density, but fast tempo
            elif z_energy > self.peak_z and z_density > self.peak_z:
                if z_brightness > 0.5:
                    mood = "peak"         # High energy, dense, bright (chorus/drop)
                else:
                    mood = "intense"      # High energy, dense, but darker (heavy section)
            elif z_energy > self.peak_z or z_density > self.peak_z:
                # One dimension is high (mixed energy state)
                mood = "build"            # Building energy or density
            elif z_energy > self.build_z and z_density > self.build_z:
                mood = "build"            # Both lifting together
            elif z_energy > 0.0 or z_density > 0.0:
                # Above average energy or density
                mood = "groove"           # Moderate energy, steady rhythm
            elif z_energy < self.chill_z or z_density < self.chill_z:
                # Below average
                mood = "chill"            # Lower energy, relaxed
            else:
                # Near zero (average)
                mood = "groove"           # Steady state

            # Store current z_energy for next iteration's energy change detection
            self._prev_z_energy = z_energy

            # Keep for next step
            self._feat_prev = curr_feat

        # --- Emit JSON message ---

        msg = {
            "type": "feature_update",
            "tempo": tempo_val,

            # High-level states
            "mood": mood,                     # "ambient" | "chill" | "groove" | "build" | "peak" | "intense" | "breakdown" | "unknown"
            "section_change": section_change, # bool: boundary candidate
        }

        sys.stdout.write(json.dumps(msg) + "\n")
        sys.stdout.flush()

        # --- Debug telemetry ---
        if self.debug:
            # # Raw-ish features if you want them in the frontend / LedFx core
            # "energy_rms": rms,
            # "brightness_centroid": centroid,
            # "bandwidth": bandwidth,
            # "spectral_flatness": flatness,
            # "onset_mean": onset_mean,
            # "onset_var": onset_var,

            # # Debug info for tuning (optional, can remove later)
            # "z_energy": float(z_energy),
            # "z_density": float(z_density),
            # "section_distance": float(dist),

            # build a single string to send to Teleplot once

            lines = []
            lines.append(f"energy_rms:{rms}")
            lines.append(f"brightness_centroid:{centroid}")
            lines.append(f"bandwidth:{bandwidth}")
            lines.append(f"spectral_flatness:{flatness}")
            lines.append(f"onset_mean:{onset_mean}")
            lines.append(f"onset_var:{onset_var}")
    
            lines.append(f"z_energy:{z_energy}")
            lines.append(f"z_density:{z_density}")
            lines.append(f"section_distance:{dist}")

            Teleplot.send("\n".join(lines))


def _read_exact(n: int) -> bytes:
    """Read exactly n bytes from stdin or raise EOFError."""
    buf = bytearray(n)
    mv = memoryview(buf)
    total = 0
    while total < n:
        chunk = sys.stdin.buffer.read(n - total)
        if not chunk:
            raise EOFError("EOF while reading stdin")
        mv[total:total+len(chunk)] = chunk
        total += len(chunk)
    return buf


def main():
    analyzer = AudioAnalyzer()
    
    while True:
        try:
            # Read header
            header_bytes = _read_exact(HEADER_STRUCT.size)
        except EOFError:
            break

        msg_type, payload_len = HEADER_STRUCT.unpack(header_bytes)

        # Shutdown
        if msg_type == MSG_TYPE_SHUTDOWN:
            # Drain payload if any
            if payload_len:
                _ = _read_exact(payload_len)
            break
        
        # Configuration
        if msg_type == MSG_TYPE_CONFIG:
            try:
                payload = _read_exact(payload_len)
                config = json.loads(payload.decode('utf-8'))
                analyzer.handle_config(config)
            except (EOFError, json.JSONDecodeError) as e:
                _LOGGER.error(f"Config parse error: {e!r}")
            continue

        # Unknown — drain payload, skip
        if msg_type != MSG_TYPE_AUDIO:
            if payload_len:
                _ = _read_exact(payload_len)
            continue

        # Read audio block
        try:
            payload = _read_exact(payload_len)
        except EOFError:
            break

        block = np.frombuffer(payload, dtype=np.float32)
        analyzer.process_audio_block(block)


if __name__ == "__main__":
    # TODO: Remove this debug trap
    # Enable debugpy for worker debugging during development
    try:
        import debugpy
        debugpy.listen(("localhost", 5679))
        sys.stderr.write("[Worker] debugpy listening on port 5679 (ready for attach)\n")
        sys.stderr.flush()
    except ImportError:
        pass  # debugpy not available, continue without debugging
    except Exception as e:
        sys.stderr.write(f"[Worker] Failed to setup debugpy: {e}\n")
        sys.stderr.flush()
    
    try:
        main()
    except KeyboardInterrupt:
        pass
