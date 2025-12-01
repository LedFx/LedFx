"""
Tests for signal generation framework.

Validates that synthetic test signals are generated correctly with
proper ground truth annotations. This is the foundation for all
subsequent multi-FFT validation tests.
"""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

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
from .signal_generator import (
    DEFAULT_SAMPLE_RATE,
    STANDARD_TEMPOS,
    add_noise,
    generate_chromatic_scale,
    generate_click_track,
    generate_complex_signal,
    generate_onset_signal,
    generate_pitch_sequence,
    generate_tone,
    load_signal,
    midi_to_frequency,
    save_signal,
)


class TestMidiConversion:
    """Tests for MIDI to frequency conversion."""

    def test_a4_is_440hz(self):
        """A4 (MIDI 69) should be 440 Hz."""
        freq = midi_to_frequency(69)
        assert abs(freq - 440.0) < 0.01

    def test_a0_is_27_5hz(self):
        """A0 (MIDI 21) should be ~27.5 Hz."""
        freq = midi_to_frequency(21)
        assert abs(freq - 27.5) < 0.1

    def test_c8_is_4186hz(self):
        """C8 (MIDI 108) should be ~4186 Hz."""
        freq = midi_to_frequency(108)
        assert abs(freq - 4186.0) < 1.0

    def test_octave_doubles_frequency(self):
        """Each octave should double the frequency."""
        for midi in range(21, 108 - 12):
            lower = midi_to_frequency(midi)
            higher = midi_to_frequency(midi + 12)
            ratio = higher / lower
            assert abs(ratio - 2.0) < 0.001


class TestToneGeneration:
    """Tests for basic tone generation."""

    def test_sine_wave_frequency(self, sample_rate):
        """Verify sine wave has correct frequency."""
        freq = 440.0
        duration = 1.0
        audio = generate_tone(freq, duration, sample_rate, "sine")

        # Check length
        expected_samples = int(duration * sample_rate)
        assert len(audio) == expected_samples

        # Check frequency via zero crossings
        zero_crossings = np.where(np.diff(np.sign(audio)))[0]
        # Zero crossings should occur twice per period
        periods = len(zero_crossings) / 2
        detected_freq = periods / duration
        # Allow 2% tolerance
        assert abs(detected_freq - freq) / freq < 0.02

    def test_waveform_types(self, sample_rate):
        """Test all waveform types generate valid audio."""
        waveforms = ["sine", "triangle", "sawtooth", "square"]
        for waveform in waveforms:
            audio = generate_tone(440.0, 0.5, sample_rate, waveform)
            assert len(audio) > 0
            assert np.max(np.abs(audio)) <= 1.0
            assert audio.dtype == np.float32

    def test_amplitude_control(self, sample_rate):
        """Test amplitude parameter works correctly."""
        for amplitude in [0.1, 0.5, 0.8, 1.0]:
            audio = generate_tone(440.0, 0.1, sample_rate, "sine", amplitude)
            max_val = np.max(np.abs(audio))
            assert abs(max_val - amplitude) < 0.01


class TestClickTrackGeneration:
    """Tests for click track (tempo) signal generation."""

    def test_click_track_basic(self, sample_rate):
        """Test basic click track generation."""
        audio, signal_def = generate_click_track(
            bpm=120,
            duration=10.0,
            sample_rate=sample_rate,
        )

        # Check audio properties
        expected_samples = int(10.0 * sample_rate)
        assert len(audio) == expected_samples
        assert audio.dtype == np.float32

        # Check signal definition
        assert signal_def.signal_type == "tempo"
        assert signal_def.metadata.bpm == 120
        assert signal_def.metadata.sample_rate == sample_rate

    def test_click_track_beat_count(self, sample_rate):
        """Verify correct number of beats in ground truth."""
        bpm = 120
        duration = 10.0
        audio, signal_def = generate_click_track(
            bpm=bpm,
            duration=duration,
            sample_rate=sample_rate,
        )

        # At 120 BPM, should have 2 beats per second
        expected_beats = int(duration * bpm / 60)
        actual_beats = len(signal_def.ground_truth.beats)

        # Allow for slight timing differences at boundaries
        assert abs(actual_beats - expected_beats) <= 1

    def test_click_track_beat_timing(self, sample_rate):
        """Verify beat timestamps match expected timing."""
        bpm = 120
        beat_period = 60.0 / bpm  # 0.5 seconds

        audio, signal_def = generate_click_track(
            bpm=bpm,
            duration=5.0,
            sample_rate=sample_rate,
        )

        # Check beat spacing
        beats = signal_def.ground_truth.beats
        for i in range(1, len(beats)):
            delta = beats[i].time - beats[i - 1].time
            assert abs(delta - beat_period) < 0.001

    @pytest.mark.parametrize("bpm", STANDARD_TEMPOS)
    def test_standard_tempos(self, bpm, sample_rate):
        """Test generation at all standard tempos."""
        audio, signal_def = generate_click_track(
            bpm=bpm,
            duration=5.0,
            sample_rate=sample_rate,
        )

        assert signal_def.metadata.bpm == bpm
        assert len(signal_def.ground_truth.beats) > 0
        assert np.max(np.abs(audio)) > 0

    def test_click_track_bar_counting(self, sample_rate):
        """Verify bar and beat number annotations."""
        audio, signal_def = generate_click_track(
            bpm=120,
            duration=10.0,
            sample_rate=sample_rate,
        )

        beats = signal_def.ground_truth.beats
        for i, beat in enumerate(beats):
            expected_beat_number = (i % 4) + 1
            expected_bar = (i // 4) + 1
            assert beat.beat_number == expected_beat_number
            assert beat.bar == expected_bar


class TestOnsetSignalGeneration:
    """Tests for onset signal generation."""

    @pytest.mark.parametrize("attack_type", STANDARD_ATTACK_TYPES)
    def test_attack_types(self, attack_type, sample_rate):
        """Test all attack types generate valid signals."""
        audio, signal_def = generate_onset_signal(
            attack_type=attack_type,
            interval_ms=500.0,
            duration=5.0,
            sample_rate=sample_rate,
        )

        assert signal_def.signal_type == "onset"
        assert len(signal_def.ground_truth.onsets) > 0
        assert np.max(np.abs(audio)) <= 1.0

    def test_onset_timing(self, sample_rate):
        """Verify onset timestamps match expected timing."""
        interval_ms = 500.0
        audio, signal_def = generate_onset_signal(
            attack_type="sharp",
            interval_ms=interval_ms,
            duration=5.0,
            sample_rate=sample_rate,
        )

        onsets = signal_def.ground_truth.onsets
        for i in range(1, len(onsets)):
            delta_ms = (onsets[i].time - onsets[i - 1].time) * 1000
            assert abs(delta_ms - interval_ms) < 1.0

    def test_onset_count(self, sample_rate):
        """Verify correct number of onsets generated."""
        interval_ms = 500.0
        duration = 5.0
        audio, signal_def = generate_onset_signal(
            attack_type="impulse",
            interval_ms=interval_ms,
            duration=duration,
            sample_rate=sample_rate,
        )

        expected_onsets = int(duration * 1000 / interval_ms)
        actual_onsets = len(signal_def.ground_truth.onsets)
        assert abs(actual_onsets - expected_onsets) <= 1

    def test_invalid_attack_type(self, sample_rate):
        """Test that invalid attack type raises error."""
        with pytest.raises(ValueError):
            generate_onset_signal(
                attack_type="invalid",
                sample_rate=sample_rate,
            )


class TestPitchSignalGeneration:
    """Tests for pitch signal generation."""

    def test_pitch_sequence_basic(self, sample_rate):
        """Test basic pitch sequence generation."""
        midi_notes = [60, 62, 64, 65, 67]  # C D E F G
        audio, signal_def = generate_pitch_sequence(
            midi_notes=midi_notes,
            note_duration=0.5,
            sample_rate=sample_rate,
        )

        assert signal_def.signal_type == "pitch"
        assert len(signal_def.ground_truth.pitches) == len(midi_notes)

        # Check duration
        expected_duration = len(midi_notes) * 0.5
        assert abs(signal_def.metadata.duration - expected_duration) < 0.01

    def test_pitch_annotations(self, sample_rate):
        """Verify pitch annotations are correct."""
        midi_notes = [48, 60, 72]  # C3, C4, C5
        audio, signal_def = generate_pitch_sequence(
            midi_notes=midi_notes,
            note_duration=1.0,
            sample_rate=sample_rate,
        )

        pitches = signal_def.ground_truth.pitches
        for i, pitch in enumerate(pitches):
            assert pitch.midi_note == midi_notes[i]
            assert abs(pitch.frequency_hz - midi_to_frequency(midi_notes[i])) < 0.1
            assert pitch.start_time == i * 1.0
            assert pitch.end_time == (i + 1) * 1.0

    def test_chromatic_scale(self, sample_rate):
        """Test chromatic scale generation."""
        audio, signal_def = generate_chromatic_scale(
            start_midi=48,
            end_midi=60,
            note_duration=0.5,
            sample_rate=sample_rate,
        )

        # Should have 13 notes (C3 to C4 inclusive)
        assert len(signal_def.ground_truth.pitches) == 13

        # Check chromatic sequence
        pitches = signal_def.ground_truth.pitches
        for i in range(1, len(pitches)):
            assert pitches[i].midi_note == pitches[i - 1].midi_note + 1

    def test_waveform_options(self, sample_rate):
        """Test different waveform options for pitch signals."""
        midi_notes = [60]
        waveforms = ["sine", "triangle", "sawtooth", "square"]

        for waveform in waveforms:
            audio, signal_def = generate_pitch_sequence(
                midi_notes=midi_notes,
                waveform=waveform,
                sample_rate=sample_rate,
            )
            assert signal_def.ground_truth.pitches[0].waveform == waveform


class TestComplexSignalGeneration:
    """Tests for complex signal generation."""

    def test_complex_signal_basic(self, sample_rate):
        """Test basic complex signal generation."""
        audio, signal_def = generate_complex_signal(
            bpm=120,
            duration=10.0,
            sample_rate=sample_rate,
            snr_db=20.0,
        )

        assert signal_def.signal_type == "complex"
        assert len(signal_def.ground_truth.beats) > 0
        assert np.max(np.abs(audio)) <= 1.0

    def test_noise_levels(self, sample_rate):
        """Test different noise levels."""
        for snr_db in [30, 20, 10, 0]:
            audio, signal_def = generate_complex_signal(
                bpm=120,
                duration=5.0,
                sample_rate=sample_rate,
                snr_db=snr_db,
            )
            assert len(audio) > 0
            assert np.max(np.abs(audio)) <= 1.0


class TestNoiseAddition:
    """Tests for noise addition utility."""

    def test_snr_calculation(self, sample_rate):
        """Verify SNR is approximately correct."""
        # Generate clean signal
        clean = generate_tone(440.0, 1.0, sample_rate)

        # Add noise at known SNR
        snr_db = 20.0
        noisy = add_noise(clean, snr_db)

        # Estimate actual SNR
        noise = noisy - clean
        signal_power = np.mean(clean**2)
        noise_power = np.mean(noise**2)

        if noise_power > 0:
            actual_snr = 10 * np.log10(signal_power / noise_power)
            # Allow 2 dB tolerance
            assert abs(actual_snr - snr_db) < 2.0


class TestSignalSaveLoad:
    """Tests for saving and loading signals."""

    def test_save_load_roundtrip(self, temp_signal_dir, sample_rate):
        """Test saving and loading preserves data."""
        # Generate signal
        audio, signal_def = generate_click_track(
            bpm=120,
            duration=5.0,
            sample_rate=sample_rate,
        )

        # Save
        audio_path, gt_path = save_signal(
            audio, signal_def, temp_signal_dir, "test_signal"
        )

        # Load
        loaded_audio, loaded_def = load_signal(audio_path, gt_path)

        # Verify audio
        np.testing.assert_array_almost_equal(audio, loaded_audio)

        # Verify definition
        assert loaded_def.signal_type == signal_def.signal_type
        assert loaded_def.metadata.bpm == signal_def.metadata.bpm
        assert loaded_def.metadata.sample_rate == signal_def.metadata.sample_rate
        assert len(loaded_def.ground_truth.beats) == len(signal_def.ground_truth.beats)

    def test_save_creates_directories(self, temp_signal_dir, sample_rate):
        """Test that save creates nested directories."""
        audio, signal_def = generate_click_track(
            bpm=120, duration=2.0, sample_rate=sample_rate
        )

        nested_dir = temp_signal_dir / "deep" / "nested" / "path"
        audio_path, gt_path = save_signal(audio, signal_def, nested_dir, "test")

        assert audio_path.exists()
        assert gt_path.exists()

    def test_load_infers_ground_truth_path(self, temp_signal_dir, sample_rate):
        """Test that load can infer ground truth path from audio path."""
        audio, signal_def = generate_click_track(
            bpm=120, duration=2.0, sample_rate=sample_rate
        )

        audio_path, _ = save_signal(
            audio, signal_def, temp_signal_dir, "infer_test"
        )

        # Load without explicit ground truth path
        loaded_audio, loaded_def = load_signal(audio_path)

        assert loaded_def is not None
        assert loaded_def.signal_type == "tempo"


class TestGroundTruthSchema:
    """Tests for ground truth schema validation."""

    def test_signal_definition_to_dict(self, sample_rate):
        """Test SignalDefinition serialization."""
        audio, signal_def = generate_click_track(
            bpm=120, duration=2.0, sample_rate=sample_rate
        )

        data = signal_def.to_dict()

        assert "signal_type" in data
        assert "metadata" in data
        assert "ground_truth" in data
        assert "test_criteria" in data

        # Verify JSON serializable
        json_str = json.dumps(data)
        assert len(json_str) > 0

    def test_signal_definition_from_dict(self):
        """Test SignalDefinition deserialization."""
        data = {
            "signal_type": "tempo",
            "metadata": {
                "sample_rate": 44100,
                "duration": 5.0,
                "description": "Test signal",
                "bpm": 120,
            },
            "ground_truth": {
                "beats": [
                    {"time": 0.5, "beat_number": 1, "bar": 1},
                    {"time": 1.0, "beat_number": 2, "bar": 1},
                ]
            },
            "test_criteria": {
                "tempo_tolerance_bpm": 2.0,
                "min_detection_rate": 0.95,
            },
        }

        signal_def = SignalDefinition.from_dict(data)

        assert signal_def.signal_type == "tempo"
        assert signal_def.metadata.bpm == 120
        assert len(signal_def.ground_truth.beats) == 2
        assert signal_def.test_criteria.tempo_tolerance_bpm == 2.0


class TestSignalPlayer:
    """Tests for the SignalPlayer utility class."""

    def test_frame_iteration(self, signal_player_factory, click_track_120bpm):
        """Test iterating through audio frames."""
        audio, signal_def = click_track_120bpm
        player = signal_player_factory(audio, signal_def, hop_size=367)

        frames = []
        while not player.is_exhausted():
            frame = player.get_next_frame()
            if frame is not None:
                frames.append(frame)

        # Should have processed all audio
        total_samples = sum(len(f) for f in frames)
        # Allow for some padding at the end
        assert total_samples >= len(audio)

    def test_frame_size(self, signal_player_factory, click_track_120bpm):
        """Test that frames have consistent size."""
        audio, signal_def = click_track_120bpm
        hop_size = 256
        player = signal_player_factory(audio, signal_def, hop_size=hop_size)

        frame = player.get_next_frame()
        assert len(frame) == hop_size

    def test_reset(self, signal_player_factory, click_track_120bpm):
        """Test resetting playback position."""
        audio, signal_def = click_track_120bpm
        player = signal_player_factory(audio, signal_def, hop_size=367)

        # Advance a few frames
        for _ in range(10):
            player.get_next_frame()

        assert player.get_current_time() > 0

        # Reset
        player.reset()
        assert player.get_current_time() == 0

    def test_current_time(self, signal_player_factory, click_track_120bpm):
        """Test current time tracking."""
        audio, signal_def = click_track_120bpm
        hop_size = 441  # 10ms at 44100 Hz
        player = signal_player_factory(audio, signal_def, hop_size=hop_size)

        # Advance 100 frames (should be ~1 second)
        for _ in range(100):
            player.get_next_frame()

        expected_time = 100 * hop_size / signal_def.metadata.sample_rate
        assert abs(player.get_current_time() - expected_time) < 0.01
