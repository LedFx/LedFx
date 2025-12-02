"""
Realistic Signal Generator for Real-World Validation

This module generates music-like test signals that more closely approximate
real audio content than pure synthetic signals. These signals are used for
validating that findings from synthetic tests hold up in realistic scenarios.

Signal Types:
- Drum patterns: Kick, snare, hi-hat with realistic envelope and harmonic content
- Bass lines: Melodic bass with sustained notes and portamento
- Chord progressions: Polyphonic content with realistic timbre
- Full mixes: Combined instruments with reverb and dynamic variation

Part of Milestone 4: Real-World Validation
"""

from dataclasses import dataclass, field

import numpy as np

from .ground_truth_schema import (
    BeatAnnotation,
    GroundTruth,
    OnsetAnnotation,
    PitchAnnotation,
    SignalDefinition,
    SignalMetadata,
    TestCriteria,
)

DEFAULT_SAMPLE_RATE = 44100


def midi_to_frequency(midi_note: float) -> float:
    """Convert MIDI note number to frequency in Hz."""
    return 440.0 * (2.0 ** ((midi_note - 69) / 12.0))


@dataclass
class DrumPattern:
    """Configuration for a drum pattern."""

    bpm: float = 120.0
    pattern_bars: int = 1
    kick_beats: list[float] = field(
        default_factory=lambda: [1, 3]
    )  # Beat numbers
    snare_beats: list[float] = field(default_factory=lambda: [2, 4])
    hihat_beats: list[float] = field(
        default_factory=lambda: [1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5]
    )


def generate_drum_sound(
    drum_type: str,
    duration: float,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    seed: int | None = 42,
) -> np.ndarray:
    """
    Generate a realistic drum sound with harmonics and envelope.

    Args:
        drum_type: 'kick', 'snare', or 'hihat'
        duration: Duration in seconds
        sample_rate: Audio sample rate
        seed: Random seed for reproducible noise generation

    Returns:
        Audio samples as float32 array
    """
    # Create random generator with optional seed for reproducibility
    rng = np.random.default_rng(seed)
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate

    if drum_type == "kick":
        # Kick drum: frequency sweep from ~150Hz to ~50Hz with exponential decay
        freq_start = 150.0
        freq_end = 50.0
        freq_decay = 10.0  # How fast frequency drops

        freq = freq_end + (freq_start - freq_end) * np.exp(-freq_decay * t)
        phase = 2 * np.pi * np.cumsum(freq) / sample_rate
        tone = np.sin(phase)

        # Envelope: quick attack, exponential decay
        attack_samples = int(0.005 * sample_rate)
        envelope = np.exp(-5.0 * t)
        envelope[:attack_samples] = np.linspace(0, 1, attack_samples)

        audio = tone * envelope

    elif drum_type == "snare":
        # Snare: combination of tone (~200Hz) and noise
        tone_freq = 200.0
        tone = np.sin(2 * np.pi * tone_freq * t)

        # Noise component (band-limited)
        noise = rng.standard_normal(num_samples)

        # Mix: 30% tone, 70% noise
        mixed = 0.3 * tone + 0.7 * noise

        # Envelope: quick attack, exponential decay
        attack_samples = int(0.002 * sample_rate)
        envelope = np.exp(-12.0 * t)
        envelope[:attack_samples] = np.linspace(0, 1, attack_samples)

        audio = mixed * envelope

    elif drum_type == "hihat":
        # Hi-hat: filtered noise
        noise = rng.standard_normal(num_samples)

        # High-pass filter simulation (simple differencing)
        filtered = np.diff(noise, prepend=0)
        filtered = np.diff(filtered, prepend=0)

        # Envelope: very quick decay
        attack_samples = int(0.001 * sample_rate)
        envelope = np.exp(-30.0 * t)
        envelope[:attack_samples] = np.linspace(0, 1, attack_samples)

        audio = filtered * envelope * 0.5  # Reduce level

    else:
        raise ValueError(f"Unknown drum type: {drum_type}")

    # Normalize
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio /= max_val

    return audio.astype(np.float32)


def generate_drum_pattern(
    pattern: DrumPattern,
    num_bars: int = 4,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> tuple[np.ndarray, SignalDefinition]:
    """
    Generate a complete drum pattern with ground truth.

    Args:
        pattern: DrumPattern configuration
        num_bars: Number of bars to generate
        sample_rate: Audio sample rate

    Returns:
        Tuple of (audio_samples, signal_definition)
    """
    beat_duration = 60.0 / pattern.bpm
    bar_duration = 4 * beat_duration  # 4 beats per bar
    total_duration = num_bars * bar_duration

    num_samples = int(total_duration * sample_rate)
    audio = np.zeros(num_samples, dtype=np.float32)

    # Pre-generate drum sounds
    kick = generate_drum_sound("kick", 0.2, sample_rate)
    snare = generate_drum_sound("snare", 0.15, sample_rate)
    hihat = generate_drum_sound("hihat", 0.1, sample_rate)

    beats = []
    onsets = []
    beat_counter = 1
    bar_counter = 1

    for bar in range(num_bars):
        bar_start = bar * bar_duration

        # Place kick drums
        for beat_pos in pattern.kick_beats:
            beat_time = bar_start + (beat_pos - 1) * beat_duration
            sample_idx = int(beat_time * sample_rate)

            if sample_idx + len(kick) <= num_samples:
                audio[sample_idx : sample_idx + len(kick)] += kick * 0.8

            # Record beat annotation
            beats.append(
                BeatAnnotation(
                    time=beat_time,
                    beat_number=beat_counter,
                    bar=bar_counter,
                )
            )
            onsets.append(
                OnsetAnnotation(
                    time=beat_time,
                    attack_ms=5.0,
                    onset_type="sharp",
                )
            )
            beat_counter = (beat_counter % 4) + 1
            if beat_counter == 1:
                bar_counter += 1

        # Place snare drums
        for beat_pos in pattern.snare_beats:
            beat_time = bar_start + (beat_pos - 1) * beat_duration
            sample_idx = int(beat_time * sample_rate)

            if sample_idx + len(snare) <= num_samples:
                audio[sample_idx : sample_idx + len(snare)] += snare * 0.6

            onsets.append(
                OnsetAnnotation(
                    time=beat_time,
                    attack_ms=2.0,
                    onset_type="sharp",
                )
            )

        # Place hi-hats
        for beat_pos in pattern.hihat_beats:
            beat_time = bar_start + (beat_pos - 1) * beat_duration
            sample_idx = int(beat_time * sample_rate)

            if sample_idx + len(hihat) <= num_samples:
                audio[sample_idx : sample_idx + len(hihat)] += hihat * 0.3

    # Normalize
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val * 0.9

    signal_def = SignalDefinition(
        signal_type="tempo",
        metadata=SignalMetadata(
            sample_rate=sample_rate,
            duration=total_duration,
            description=f"Drum pattern at {pattern.bpm} BPM ({num_bars} bars)",
            bpm=pattern.bpm,
        ),
        ground_truth=GroundTruth(beats=beats, onsets=onsets),
        test_criteria=TestCriteria(
            tempo_tolerance_bpm=3.0,
            beat_timing_tolerance_ms=50.0,
            min_detection_rate=0.7,  # Relaxed for realistic signals
        ),
    )

    return audio, signal_def


def generate_bass_note(
    midi_note: int,
    duration: float,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    attack_ms: float = 10.0,
    release_ms: float = 50.0,
) -> np.ndarray:
    """
    Generate a bass note with realistic harmonics and envelope.

    Args:
        midi_note: MIDI note number
        duration: Note duration in seconds
        sample_rate: Audio sample rate
        attack_ms: Attack time in milliseconds
        release_ms: Release time in milliseconds

    Returns:
        Audio samples as float32 array
    """
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    freq = midi_to_frequency(midi_note)

    # Generate harmonics (fundamental + 2nd, 3rd, 4th harmonics)
    audio = np.sin(2 * np.pi * freq * t)  # Fundamental
    audio += 0.5 * np.sin(2 * np.pi * 2 * freq * t)  # 2nd harmonic
    audio += 0.25 * np.sin(2 * np.pi * 3 * freq * t)  # 3rd harmonic
    audio += 0.125 * np.sin(2 * np.pi * 4 * freq * t)  # 4th harmonic

    # ADSR envelope
    attack_samples = int(attack_ms * sample_rate / 1000)
    release_samples = int(release_ms * sample_rate / 1000)
    sustain_samples = max(0, num_samples - attack_samples - release_samples)

    envelope = np.ones(num_samples)
    if attack_samples > 0:
        envelope[:attack_samples] = np.linspace(0, 1, attack_samples)
    if release_samples > 0 and sustain_samples + attack_samples < num_samples:
        release_start = attack_samples + sustain_samples
        envelope[release_start:] = np.linspace(
            1, 0, num_samples - release_start
        )

    audio = audio * envelope

    # Normalize
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio /= max_val

    return audio.astype(np.float32)


def generate_bass_line(
    notes: list[tuple[int, float]],  # [(midi_note, duration), ...]
    bpm: float = 120.0,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> tuple[np.ndarray, SignalDefinition]:
    """
    Generate a bass line with ground truth.

    Args:
        notes: List of (midi_note, duration_beats) tuples
        bpm: Tempo in BPM
        sample_rate: Audio sample rate

    Returns:
        Tuple of (audio_samples, signal_definition)
    """
    beat_duration = 60.0 / bpm

    # Calculate total duration
    total_beats = sum(dur for _, dur in notes)
    total_duration = total_beats * beat_duration
    num_samples = int(total_duration * sample_rate)

    audio = np.zeros(num_samples, dtype=np.float32)
    pitches = []
    onsets = []
    current_time = 0.0

    for midi_note, duration_beats in notes:
        duration = duration_beats * beat_duration
        note_audio = generate_bass_note(
            midi_note, duration, sample_rate, attack_ms=10.0, release_ms=50.0
        )

        sample_idx = int(current_time * sample_rate)
        end_idx = min(sample_idx + len(note_audio), num_samples)
        audio[sample_idx:end_idx] += note_audio[: end_idx - sample_idx] * 0.7

        # Record annotations
        pitches.append(
            PitchAnnotation(
                start_time=current_time,
                end_time=current_time + duration,
                midi_note=midi_note,
                frequency_hz=midi_to_frequency(midi_note),
                waveform="sine",  # Closest approximation
            )
        )
        onsets.append(
            OnsetAnnotation(
                time=current_time,
                attack_ms=10.0,
                onset_type="medium",
            )
        )

        current_time += duration

    # Normalize
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val * 0.8

    signal_def = SignalDefinition(
        signal_type="pitch",
        metadata=SignalMetadata(
            sample_rate=sample_rate,
            duration=total_duration,
            description=f"Bass line at {bpm} BPM ({len(notes)} notes)",
            bpm=bpm,
        ),
        ground_truth=GroundTruth(pitches=pitches, onsets=onsets),
        test_criteria=TestCriteria(
            pitch_tolerance_cents=100.0,  # Relaxed for harmonics
            min_detection_rate=0.6,
        ),
    )

    return audio, signal_def


def generate_chord(
    notes: list[int],  # MIDI notes
    duration: float,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> np.ndarray:
    """
    Generate a chord with multiple notes.

    Args:
        notes: List of MIDI note numbers
        duration: Duration in seconds
        sample_rate: Audio sample rate

    Returns:
        Audio samples as float32 array
    """
    num_samples = int(duration * sample_rate)
    audio = np.zeros(num_samples, dtype=np.float32)
    t = np.arange(num_samples) / sample_rate

    for midi_note in notes:
        freq = midi_to_frequency(midi_note)
        # Rich tone with harmonics
        tone = np.sin(2 * np.pi * freq * t)
        tone += 0.3 * np.sin(2 * np.pi * 2 * freq * t)
        tone += 0.1 * np.sin(2 * np.pi * 3 * freq * t)
        audio += tone

    # Apply envelope
    attack_samples = int(0.05 * sample_rate)
    release_samples = int(0.1 * sample_rate)

    envelope = np.ones(num_samples)
    if attack_samples > 0:
        envelope[:attack_samples] = np.linspace(0, 1, attack_samples)
    if release_samples > 0:
        release_start = max(0, num_samples - release_samples)
        envelope[release_start:] = np.linspace(
            1, 0, num_samples - release_start
        )

    audio = audio * envelope

    # Normalize
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio /= max_val

    return audio.astype(np.float32)


def generate_chord_progression(
    progression: list[
        tuple[list[int], float]
    ],  # [([notes], duration_beats), ...]
    bpm: float = 120.0,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> tuple[np.ndarray, SignalDefinition]:
    """
    Generate a chord progression with ground truth.

    Args:
        progression: List of (chord_notes, duration_beats) tuples
        bpm: Tempo in BPM
        sample_rate: Audio sample rate

    Returns:
        Tuple of (audio_samples, signal_definition)
    """
    beat_duration = 60.0 / bpm

    total_beats = sum(dur for _, dur in progression)
    total_duration = total_beats * beat_duration
    num_samples = int(total_duration * sample_rate)

    audio = np.zeros(num_samples, dtype=np.float32)
    pitches = []
    onsets = []
    current_time = 0.0

    for chord_notes, duration_beats in progression:
        duration = duration_beats * beat_duration
        chord_audio = generate_chord(chord_notes, duration, sample_rate)

        sample_idx = int(current_time * sample_rate)
        end_idx = min(sample_idx + len(chord_audio), num_samples)
        audio[sample_idx:end_idx] += chord_audio[: end_idx - sample_idx] * 0.5

        # Record root note as primary pitch
        root_note = min(chord_notes)
        pitches.append(
            PitchAnnotation(
                start_time=current_time,
                end_time=current_time + duration,
                midi_note=root_note,
                frequency_hz=midi_to_frequency(root_note),
            )
        )
        onsets.append(
            OnsetAnnotation(
                time=current_time,
                attack_ms=50.0,
                onset_type="medium",
            )
        )

        current_time += duration

    # Normalize
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val * 0.8

    signal_def = SignalDefinition(
        signal_type="complex",
        metadata=SignalMetadata(
            sample_rate=sample_rate,
            duration=total_duration,
            description=f"Chord progression at {bpm} BPM ({len(progression)} chords)",
            bpm=bpm,
        ),
        ground_truth=GroundTruth(pitches=pitches, onsets=onsets),
        test_criteria=TestCriteria(
            pitch_tolerance_cents=150.0,  # Very relaxed for polyphonic
            min_detection_rate=0.4,
        ),
    )

    return audio, signal_def


def add_reverb(
    audio: np.ndarray,
    decay: float = 0.3,
    delay_ms: float = 30.0,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> np.ndarray:
    """
    Add simple reverb effect to audio.

    Args:
        audio: Input audio samples
        decay: Reverb decay factor (0-1)
        delay_ms: Delay time in milliseconds
        sample_rate: Audio sample rate

    Returns:
        Audio with reverb applied
    """
    delay_samples = int(delay_ms * sample_rate / 1000)

    # Simple comb filter reverb
    output = np.copy(audio)
    for i in range(len(audio)):
        if i >= delay_samples:
            output[i] += decay * output[i - delay_samples]

    # Normalize to prevent clipping
    max_val = np.max(np.abs(output))
    if max_val > 1.0:
        output /= max_val

    return output.astype(np.float32)


def add_dynamics(
    audio: np.ndarray,
    variation: float = 0.3,
    period_seconds: float = 2.0,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> np.ndarray:
    """
    Add dynamic variation (volume swells) to audio.

    Args:
        audio: Input audio samples
        variation: Amount of volume variation (0-1)
        period_seconds: Period of volume change
        sample_rate: Audio sample rate

    Returns:
        Audio with dynamics applied
    """
    t = np.arange(len(audio)) / sample_rate
    modulation = 1.0 - variation * 0.5 * (
        1.0 + np.sin(2 * np.pi * t / period_seconds)
    )
    return (audio * modulation).astype(np.float32)


def generate_full_mix(
    bpm: float = 120.0,
    duration: float = 30.0,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    include_reverb: bool = True,
    include_dynamics: bool = True,
) -> tuple[np.ndarray, SignalDefinition]:
    """
    Generate a full mix combining drums, bass, and chords.

    Args:
        bpm: Tempo in BPM
        duration: Duration in seconds
        sample_rate: Audio sample rate
        include_reverb: Whether to add reverb
        include_dynamics: Whether to add dynamic variation

    Returns:
        Tuple of (audio_samples, signal_definition)
    """
    beat_duration = 60.0 / bpm
    num_bars = int(duration / (4 * beat_duration))

    # Generate drum pattern
    pattern = DrumPattern(bpm=bpm)
    drums, drum_def = generate_drum_pattern(pattern, num_bars, sample_rate)

    # Generate bass line (simple repeating pattern)
    bass_notes = [
        (36, 1),  # C2
        (36, 1),
        (38, 1),  # D2
        (41, 1),  # F2
    ] * (num_bars // 1 + 1)
    bass, bass_def = generate_bass_line(
        bass_notes[: num_bars * 4], bpm, sample_rate
    )

    # Generate chord progression
    chords = [
        ([48, 52, 55], 4),  # C major
        ([53, 57, 60], 4),  # F major
        ([55, 59, 62], 4),  # G major
        ([48, 52, 55], 4),  # C major
    ] * (num_bars // 4 + 1)
    chord_audio, chord_def = generate_chord_progression(
        chords[: num_bars // 4 + 1], bpm, sample_rate
    )

    # Mix signals
    min_len = min(len(drums), len(bass), len(chord_audio))
    mix = np.zeros(min_len, dtype=np.float32)
    mix += drums[:min_len] * 0.5  # Drums at 50%
    mix += bass[:min_len] * 0.35  # Bass at 35%
    mix += chord_audio[:min_len] * 0.25  # Chords at 25%

    # Apply effects
    if include_reverb:
        mix = add_reverb(
            mix, decay=0.2, delay_ms=25.0, sample_rate=sample_rate
        )

    if include_dynamics:
        mix = add_dynamics(
            mix, variation=0.2, period_seconds=4.0, sample_rate=sample_rate
        )

    # Final normalization
    max_val = np.max(np.abs(mix))
    if max_val > 0:
        mix = mix / max_val * 0.9

    # Combine ground truth from all sources
    all_beats = drum_def.ground_truth.beats
    all_onsets = drum_def.ground_truth.onsets

    signal_def = SignalDefinition(
        signal_type="complex",
        metadata=SignalMetadata(
            sample_rate=sample_rate,
            duration=len(mix) / sample_rate,
            description=f"Full mix at {bpm} BPM (drums + bass + chords)",
            bpm=bpm,
        ),
        ground_truth=GroundTruth(beats=all_beats, onsets=all_onsets),
        test_criteria=TestCriteria(
            tempo_tolerance_bpm=5.0,
            beat_timing_tolerance_ms=75.0,
            min_detection_rate=0.5,  # Relaxed for complex mix
        ),
    )

    return mix, signal_def


# Standard realistic test signal configurations
STANDARD_DRUM_PATTERNS = {
    "rock_4_4": DrumPattern(
        bpm=120.0,
        kick_beats=[1, 3],
        snare_beats=[2, 4],
        hihat_beats=[1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5],
    ),
    "electronic_4_on_floor": DrumPattern(
        bpm=128.0,
        kick_beats=[1, 2, 3, 4],
        snare_beats=[2, 4],
        hihat_beats=[1.5, 2.5, 3.5, 4.5],
    ),
    "hip_hop": DrumPattern(
        bpm=90.0,
        kick_beats=[1, 2.5, 3],
        snare_beats=[2, 4],
        hihat_beats=[1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5],
    ),
    "fast_punk": DrumPattern(
        bpm=180.0,
        kick_beats=[1, 2, 3, 4],
        snare_beats=[2, 4],
        hihat_beats=[1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5],
    ),
}

STANDARD_BASS_LINES = {
    "simple_root": [(36, 2), (38, 2), (40, 2), (41, 2)],  # C-D-E-F
    "octave_pattern": [(36, 1), (48, 1), (38, 1), (50, 1)],  # Root + octave
    "walking_bass": [(36, 1), (38, 1), (40, 1), (41, 1), (43, 1), (45, 1)],
}

STANDARD_CHORD_PROGRESSIONS = {
    "pop_1_5_6_4": [
        ([48, 52, 55], 4),  # C
        ([55, 59, 62], 4),  # G
        ([57, 60, 64], 4),  # Am
        ([53, 57, 60], 4),  # F
    ],
    "jazz_2_5_1": [
        ([50, 53, 57, 60], 2),  # Dm7
        ([55, 59, 62, 65], 2),  # G7
        ([48, 52, 55, 59], 4),  # Cmaj7
    ],
}


def generate_realistic_test_set(
    output_dir: str | None = None,
) -> list[tuple[np.ndarray, SignalDefinition]]:
    """
    Generate a complete set of realistic test signals.

    Args:
        output_dir: Optional directory to save signals

    Returns:
        List of (audio, signal_definition) tuples
    """
    results = []

    # Generate drum patterns at various tempos
    for pattern_name, pattern in STANDARD_DRUM_PATTERNS.items():
        audio, signal_def = generate_drum_pattern(
            pattern, num_bars=8, sample_rate=DEFAULT_SAMPLE_RATE
        )
        signal_def.metadata.description = f"Drum pattern: {pattern_name}"
        results.append((audio, signal_def))

    # Generate bass lines
    for line_name, notes in STANDARD_BASS_LINES.items():
        for bpm in [90, 120, 150]:
            audio, signal_def = generate_bass_line(
                notes * 4,  # Repeat 4 times
                bpm=bpm,
                sample_rate=DEFAULT_SAMPLE_RATE,
            )
            signal_def.metadata.description = (
                f"Bass line: {line_name} @ {bpm} BPM"
            )
            results.append((audio, signal_def))

    # Generate chord progressions
    for prog_name, chords in STANDARD_CHORD_PROGRESSIONS.items():
        for bpm in [80, 120]:
            audio, signal_def = generate_chord_progression(
                chords * 2,  # Repeat twice
                bpm=bpm,
                sample_rate=DEFAULT_SAMPLE_RATE,
            )
            signal_def.metadata.description = (
                f"Chord progression: {prog_name} @ {bpm} BPM"
            )
            results.append((audio, signal_def))

    # Generate full mixes at various tempos
    for bpm in [90, 120, 140]:
        audio, signal_def = generate_full_mix(
            bpm=bpm,
            duration=20.0,
            sample_rate=DEFAULT_SAMPLE_RATE,
        )
        results.append((audio, signal_def))

    return results
