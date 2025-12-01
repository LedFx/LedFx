"""
Synthetic Signal Generator for Multi-FFT Testing

This module generates deterministic audio signals with known ground truth
for quantitative validation of tempo, onset, pitch, and melbank analysis.

Signal Types:
- Tempo/Beat: Click tracks with precise tempo (60-180 BPM)
- Onset: Various attack transients (impulse, sharp, medium, slow)
- Pitch: Pure tones across musical range (MIDI 21-108)
- Complex: Combinations with noise overlays

All signals include accompanying ground truth data for validation.
"""

import json
from pathlib import Path

import numpy as np

from .ground_truth_schema import (
    STANDARD_ATTACK_TYPES,
    BeatAnnotation,
    GroundTruth,
    OnsetAnnotation,
    PitchAnnotation,
    SignalDefinition,
    SignalMetadata,
    TestCriteria,
)

# Default sample rate matching LedFx
DEFAULT_SAMPLE_RATE = 44100


def midi_to_frequency(midi_note: int) -> float:
    """Convert MIDI note number to frequency in Hz."""
    return 440.0 * (2.0 ** ((midi_note - 69) / 12.0))


def generate_click(
    duration_samples: int,
    click_duration_samples: int = 100,
    amplitude: float = 1.0,
) -> np.ndarray:
    """
    Generate a single click impulse.

    Args:
        duration_samples: Total length of the click buffer
        click_duration_samples: Duration of the click itself
        amplitude: Peak amplitude (0.0 to 1.0)

    Returns:
        Audio samples as float32 array
    """
    click = np.zeros(duration_samples, dtype=np.float32)
    click_len = min(click_duration_samples, duration_samples)
    # Create a short impulse with exponential decay
    t = np.arange(click_len)
    click[:click_len] = amplitude * np.exp(-t / (click_len / 4))
    return click


def generate_click_track(
    bpm: float,
    duration: float,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    click_duration_ms: float = 10.0,
) -> tuple[np.ndarray, SignalDefinition]:
    """
    Generate a click track at a specific tempo with ground truth.

    Args:
        bpm: Beats per minute (60-180 typical)
        duration: Duration in seconds
        sample_rate: Audio sample rate
        click_duration_ms: Duration of each click in milliseconds

    Returns:
        Tuple of (audio_samples, signal_definition)
    """
    # Calculate timing
    beat_period = 60.0 / bpm  # seconds per beat
    num_samples = int(duration * sample_rate)
    click_samples = int(click_duration_ms * sample_rate / 1000.0)

    # Generate audio
    audio = np.zeros(num_samples, dtype=np.float32)

    # Generate ground truth
    beats = []
    beat_number = 1
    bar = 1
    time = 0.0

    while time < duration:
        # Place click at this time
        sample_idx = int(time * sample_rate)
        if sample_idx + click_samples <= num_samples:
            click = generate_click(click_samples, click_samples, 1.0)
            audio[sample_idx : sample_idx + click_samples] += click

        # Record beat annotation
        beats.append(
            BeatAnnotation(
                time=time,
                beat_number=beat_number,
                bar=bar,
            )
        )

        # Advance
        time += beat_period
        beat_number = (beat_number % 4) + 1
        if beat_number == 1:
            bar += 1

    # Create signal definition
    signal_def = SignalDefinition(
        signal_type="tempo",
        metadata=SignalMetadata(
            sample_rate=sample_rate,
            duration=duration,
            description=f"Click track at {bpm} BPM",
            bpm=bpm,
        ),
        ground_truth=GroundTruth(beats=beats),
        test_criteria=TestCriteria(
            tempo_tolerance_bpm=2.0,
            beat_timing_tolerance_ms=50.0,
            min_detection_rate=0.95,
        ),
    )

    return audio, signal_def


def generate_onset_signal(
    attack_type: str,
    interval_ms: float = 500.0,
    duration: float = 10.0,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> tuple[np.ndarray, SignalDefinition]:
    """
    Generate onset test signals with various attack characteristics.

    Args:
        attack_type: One of 'impulse', 'sharp', 'medium', 'slow'
        interval_ms: Time between onsets in milliseconds
        duration: Total duration in seconds
        sample_rate: Audio sample rate

    Returns:
        Tuple of (audio_samples, signal_definition)
    """
    # Attack time mapping (in milliseconds)
    attack_times = {
        "impulse": 0.1,  # Near-instant
        "sharp": 1.0,  # 1ms attack
        "medium": 10.0,  # 10ms attack
        "slow": 50.0,  # 50ms attack
    }

    if attack_type not in attack_times:
        raise ValueError(
            f"Unknown attack type: {attack_type}. "
            f"Must be one of {list(attack_times.keys())}"
        )

    attack_ms = attack_times[attack_type]
    attack_samples = int(attack_ms * sample_rate / 1000.0)
    decay_samples = int(100 * sample_rate / 1000.0)  # 100ms decay

    num_samples = int(duration * sample_rate)
    audio = np.zeros(num_samples, dtype=np.float32)

    onsets = []
    interval_samples = int(interval_ms * sample_rate / 1000.0)

    time = 0.0
    while time < duration:
        sample_idx = int(time * sample_rate)

        # Generate attack-decay envelope
        total_len = attack_samples + decay_samples
        if sample_idx + total_len <= num_samples:
            envelope = np.zeros(total_len, dtype=np.float32)

            # Attack phase
            if attack_samples > 0:
                envelope[:attack_samples] = np.linspace(0, 1, attack_samples)
            else:
                envelope[0] = 1.0

            # Decay phase
            decay_t = np.arange(decay_samples)
            envelope[attack_samples:] = np.exp(-decay_t / (decay_samples / 3))

            # Apply to audio
            audio[sample_idx : sample_idx + total_len] += envelope

        # Record onset
        onsets.append(
            OnsetAnnotation(
                time=time,
                attack_ms=attack_ms,
                onset_type=attack_type,
            )
        )

        time += interval_ms / 1000.0

    # Normalize
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio /= max_val

    signal_def = SignalDefinition(
        signal_type="onset",
        metadata=SignalMetadata(
            sample_rate=sample_rate,
            duration=duration,
            description=f"Onset signal with {attack_type} attacks at {interval_ms}ms intervals",
        ),
        ground_truth=GroundTruth(onsets=onsets),
        test_criteria=TestCriteria(
            onset_timing_tolerance_ms=50.0,
            min_detection_rate=0.90,
        ),
    )

    return audio, signal_def


def generate_tone(
    frequency: float,
    duration: float,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    waveform: str = "sine",
    amplitude: float = 0.8,
) -> np.ndarray:
    """
    Generate a tone with specified frequency and waveform.

    Args:
        frequency: Frequency in Hz
        duration: Duration in seconds
        sample_rate: Audio sample rate
        waveform: 'sine', 'triangle', 'sawtooth', or 'square'
        amplitude: Peak amplitude (0.0 to 1.0)

    Returns:
        Audio samples as float32 array
    """
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    phase = 2 * np.pi * frequency * t

    if waveform == "sine":
        audio = np.sin(phase)
    elif waveform == "triangle":
        audio = (
            2 * np.abs(2 * (t * frequency - np.floor(t * frequency + 0.5))) - 1
        )
    elif waveform == "sawtooth":
        audio = 2 * (t * frequency - np.floor(t * frequency + 0.5))
    elif waveform == "square":
        audio = np.sign(np.sin(phase))
    else:
        raise ValueError(f"Unknown waveform: {waveform}")

    return (amplitude * audio).astype(np.float32)


def generate_pitch_sequence(
    midi_notes: list[int],
    note_duration: float = 1.0,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    waveform: str = "sine",
) -> tuple[np.ndarray, SignalDefinition]:
    """
    Generate a sequence of pitched tones with ground truth.

    Args:
        midi_notes: List of MIDI note numbers (21-108)
        note_duration: Duration of each note in seconds
        sample_rate: Audio sample rate
        waveform: Waveform type

    Returns:
        Tuple of (audio_samples, signal_definition)
    """
    total_duration = len(midi_notes) * note_duration
    num_samples = int(total_duration * sample_rate)
    audio = np.zeros(num_samples, dtype=np.float32)

    pitches = []
    current_time = 0.0

    for midi_note in midi_notes:
        frequency = midi_to_frequency(midi_note)
        tone = generate_tone(
            frequency=frequency,
            duration=note_duration,
            sample_rate=sample_rate,
            waveform=waveform,
        )

        # Apply envelope to avoid clicks
        fade_samples = int(0.01 * sample_rate)  # 10ms fade
        if len(tone) > 2 * fade_samples:
            tone[:fade_samples] *= np.linspace(0, 1, fade_samples)
            tone[-fade_samples:] *= np.linspace(1, 0, fade_samples)

        # Place in audio
        start_idx = int(current_time * sample_rate)
        end_idx = start_idx + len(tone)
        if end_idx <= num_samples:
            audio[start_idx:end_idx] = tone

        # Record pitch annotation
        pitches.append(
            PitchAnnotation(
                start_time=current_time,
                end_time=current_time + note_duration,
                midi_note=midi_note,
                frequency_hz=frequency,
                waveform=waveform,
            )
        )

        current_time += note_duration

    signal_def = SignalDefinition(
        signal_type="pitch",
        metadata=SignalMetadata(
            sample_rate=sample_rate,
            duration=total_duration,
            description=f"Pitch sequence: {len(midi_notes)} notes, {waveform} waveform",
        ),
        ground_truth=GroundTruth(pitches=pitches),
        test_criteria=TestCriteria(
            pitch_tolerance_cents=50.0,
            min_detection_rate=0.90,
        ),
    )

    return audio, signal_def


def generate_chromatic_scale(
    start_midi: int = 48,  # C3
    end_midi: int = 72,  # C5
    note_duration: float = 0.5,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    waveform: str = "sine",
) -> tuple[np.ndarray, SignalDefinition]:
    """
    Generate a chromatic scale for pitch detection testing.

    Args:
        start_midi: Starting MIDI note
        end_midi: Ending MIDI note (inclusive)
        note_duration: Duration of each note in seconds
        sample_rate: Audio sample rate
        waveform: Waveform type

    Returns:
        Tuple of (audio_samples, signal_definition)
    """
    midi_notes = list(range(start_midi, end_midi + 1))
    return generate_pitch_sequence(
        midi_notes=midi_notes,
        note_duration=note_duration,
        sample_rate=sample_rate,
        waveform=waveform,
    )


def add_noise(
    audio: np.ndarray,
    snr_db: float,
    seed: int | None = None,
) -> np.ndarray:
    """
    Add white noise to audio at specified SNR.

    Args:
        audio: Input audio samples
        snr_db: Signal-to-noise ratio in dB
        seed: Random seed for reproducible noise generation (None for non-deterministic)

    Returns:
        Audio with added noise
    """
    # Calculate signal power
    signal_power = np.mean(audio**2)
    if signal_power == 0:
        return audio

    # Calculate noise power for desired SNR
    snr_linear = 10 ** (snr_db / 10)
    noise_power = signal_power / snr_linear

    # Generate noise (optionally with seed for reproducibility)
    rng = np.random.default_rng(seed)
    noise = np.sqrt(noise_power) * rng.standard_normal(len(audio))

    return (audio + noise).astype(np.float32)


def generate_complex_signal(
    bpm: float = 120,
    duration: float = 30.0,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    snr_db: float = 20.0,
    noise_seed: int = 42,
) -> tuple[np.ndarray, SignalDefinition]:
    """
    Generate a complex test signal combining beats, onsets, and pitch.

    Args:
        bpm: Tempo in BPM
        duration: Duration in seconds
        sample_rate: Audio sample rate
        snr_db: Signal-to-noise ratio for added noise
        noise_seed: Random seed for reproducible noise generation

    Returns:
        Tuple of (audio_samples, signal_definition)
    """
    # Generate base click track
    audio, signal_def = generate_click_track(
        bpm=bpm,
        duration=duration,
        sample_rate=sample_rate,
    )

    # Add some pitched content (simple melody)
    num_samples = len(audio)
    melody_notes = [60, 62, 64, 65, 67, 69, 71, 72]  # C major scale
    note_duration = duration / len(melody_notes)

    for i, midi_note in enumerate(melody_notes):
        freq = midi_to_frequency(midi_note)
        tone = generate_tone(
            frequency=freq,
            duration=note_duration,
            sample_rate=sample_rate,
            waveform="sine",
            amplitude=0.3,
        )

        start_idx = int(i * note_duration * sample_rate)
        end_idx = min(start_idx + len(tone), num_samples)
        audio[start_idx:end_idx] += tone[: end_idx - start_idx]

    # Add noise
    audio = add_noise(audio, snr_db, seed=noise_seed)

    # Normalize
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio /= max_val
        audio *= 0.9

    # Update signal definition
    signal_def.signal_type = "complex"
    signal_def.metadata.description = (
        f"Complex signal: {bpm} BPM click + melody + {snr_db}dB SNR noise"
    )

    return audio, signal_def


def save_signal(
    audio: np.ndarray,
    signal_def: SignalDefinition,
    output_dir: str | Path,
    name: str,
) -> tuple[Path, Path]:
    """
    Save audio and ground truth to files.

    Args:
        audio: Audio samples
        signal_def: Signal definition with ground truth
        output_dir: Output directory
        name: Base name for files

    Returns:
        Tuple of (audio_path, ground_truth_path)
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save audio as raw float32 samples
    audio_path = output_dir / f"{name}.npy"
    np.save(audio_path, audio)

    # Save ground truth as JSON
    gt_path = output_dir / f"{name}.json"
    with open(gt_path, "w") as f:
        json.dump(signal_def.to_dict(), f, indent=2)

    return audio_path, gt_path


def load_signal(
    audio_path: str | Path,
    gt_path: str | Path | None = None,
) -> tuple[np.ndarray, SignalDefinition | None]:
    """
    Load audio and ground truth from files.

    Args:
        audio_path: Path to audio .npy file
        gt_path: Optional path to ground truth .json file

    Returns:
        Tuple of (audio_samples, signal_definition or None)
    """
    audio_path = Path(audio_path)
    audio = np.load(audio_path)

    signal_def = None
    if gt_path is None:
        # Try to find matching JSON
        gt_path = audio_path.with_suffix(".json")

    if gt_path and Path(gt_path).exists():
        with open(gt_path) as f:
            data = json.load(f)
        signal_def = SignalDefinition.from_dict(data)

    return audio, signal_def


# Standard test signal presets
STANDARD_TEMPOS = [60, 80, 100, 120, 140, 160, 180]
# STANDARD_ATTACK_TYPES is imported from ground_truth_schema
STANDARD_MIDI_RANGE = range(48, 73)  # C3 to C5


def generate_standard_test_set(
    output_dir: str | Path,
) -> list[tuple[Path, Path]]:
    """
    Generate a complete set of standard test signals.

    Args:
        output_dir: Directory to save signals

    Returns:
        List of (audio_path, ground_truth_path) tuples
    """
    output_dir = Path(output_dir)
    results = []

    # Tempo signals
    for bpm in STANDARD_TEMPOS:
        audio, signal_def = generate_click_track(bpm=bpm, duration=30.0)
        paths = save_signal(
            audio, signal_def, output_dir / "tempo", f"click_{bpm}bpm"
        )
        results.append(paths)

    # Onset signals
    for attack_type in STANDARD_ATTACK_TYPES:
        audio, signal_def = generate_onset_signal(
            attack_type=attack_type, duration=10.0
        )
        paths = save_signal(
            audio, signal_def, output_dir / "onset", f"onset_{attack_type}"
        )
        results.append(paths)

    # Pitch signals (chromatic scale using STANDARD_MIDI_RANGE)
    start_midi, end_midi = min(STANDARD_MIDI_RANGE), max(STANDARD_MIDI_RANGE)
    for waveform in ["sine", "triangle", "sawtooth", "square"]:
        audio, signal_def = generate_chromatic_scale(
            start_midi=start_midi,
            end_midi=end_midi,
            waveform=waveform,
        )
        paths = save_signal(
            audio, signal_def, output_dir / "pitch", f"chromatic_{waveform}"
        )
        results.append(paths)

    # Complex signals
    for snr in [20, 10, 0]:
        audio, signal_def = generate_complex_signal(snr_db=snr)
        paths = save_signal(
            audio, signal_def, output_dir / "complex", f"complex_snr{snr}"
        )
        results.append(paths)

    return results
