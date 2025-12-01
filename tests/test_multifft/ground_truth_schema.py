"""
Ground Truth Schema for Multi-FFT Testing

This module defines the JSON schema for ground truth data used in
validating audio analysis accuracy. Ground truth files accompany
each synthetic test signal.
"""

from dataclasses import dataclass, field
from typing import Any

import voluptuous as vol

# Beat annotation schema
BEAT_SCHEMA = vol.Schema(
    {
        vol.Required("time"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("beat_number"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional("bar"): vol.All(vol.Coerce(int), vol.Range(min=1)),
    }
)

# Onset annotation schema
ONSET_SCHEMA = vol.Schema(
    {
        vol.Required("time"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("attack_ms"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("type"): vol.In(["impulse", "sharp", "medium", "slow"]),
    }
)

# Pitch annotation schema
PITCH_SCHEMA = vol.Schema(
    {
        vol.Required("start_time"): vol.All(
            vol.Coerce(float), vol.Range(min=0)
        ),
        vol.Required("end_time"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Required("midi_note"): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=127)
        ),
        vol.Optional("frequency_hz"): vol.All(
            vol.Coerce(float), vol.Range(min=0)
        ),
        vol.Optional("waveform"): vol.In(
            ["sine", "triangle", "sawtooth", "square"]
        ),
    }
)

# Test criteria schema
TEST_CRITERIA_SCHEMA = vol.Schema(
    {
        vol.Optional("tempo_tolerance_bpm", default=2.0): vol.All(
            vol.Coerce(float), vol.Range(min=0)
        ),
        vol.Optional("beat_timing_tolerance_ms", default=50.0): vol.All(
            vol.Coerce(float), vol.Range(min=0)
        ),
        vol.Optional("min_detection_rate", default=0.95): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=1)
        ),
        vol.Optional("onset_timing_tolerance_ms", default=50.0): vol.All(
            vol.Coerce(float), vol.Range(min=0)
        ),
        vol.Optional("pitch_tolerance_cents", default=50.0): vol.All(
            vol.Coerce(float), vol.Range(min=0)
        ),
    }
)

# Metadata schema
METADATA_SCHEMA = vol.Schema(
    {
        vol.Optional("bpm"): vol.All(
            vol.Coerce(float), vol.Range(min=20, max=300)
        ),
        vol.Required("sample_rate"): vol.All(
            vol.Coerce(int), vol.Range(min=8000, max=192000)
        ),
        vol.Required("duration"): vol.All(
            vol.Coerce(float), vol.Range(min=0.1)
        ),
        vol.Required("description"): str,
        vol.Optional("channels", default=1): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=2)
        ),
    }
)

# Ground truth data schema
GROUND_TRUTH_SCHEMA = vol.Schema(
    {
        vol.Optional("beats"): [BEAT_SCHEMA],
        vol.Optional("onsets"): [ONSET_SCHEMA],
        vol.Optional("pitches"): [PITCH_SCHEMA],
    }
)

# Complete signal definition schema
SIGNAL_SCHEMA = vol.Schema(
    {
        vol.Required("signal_type"): vol.In(
            ["tempo", "onset", "pitch", "complex"]
        ),
        vol.Required("metadata"): METADATA_SCHEMA,
        vol.Required("ground_truth"): GROUND_TRUTH_SCHEMA,
        vol.Optional("test_criteria"): TEST_CRITERIA_SCHEMA,
    }
)


@dataclass
class BeatAnnotation:
    """Single beat annotation with timing information."""

    time: float
    beat_number: int = 1
    bar: int = 1


@dataclass
class OnsetAnnotation:
    """Single onset annotation with timing and attack information."""

    time: float
    attack_ms: float = 1.0
    onset_type: str = "sharp"


@dataclass
class PitchAnnotation:
    """Single pitch annotation with timing and frequency information."""

    start_time: float
    end_time: float
    midi_note: int
    frequency_hz: float = 0.0
    waveform: str = "sine"

    def __post_init__(self):
        if self.frequency_hz == 0.0:
            # Calculate frequency from MIDI note
            self.frequency_hz = 440.0 * (2.0 ** ((self.midi_note - 69) / 12.0))


@dataclass
class SignalMetadata:
    """Metadata describing a test signal."""

    sample_rate: int
    duration: float
    description: str
    bpm: float = 0.0
    channels: int = 1


@dataclass
class TestCriteria:
    """Success criteria for test validation."""

    tempo_tolerance_bpm: float = 2.0
    beat_timing_tolerance_ms: float = 50.0
    min_detection_rate: float = 0.95
    onset_timing_tolerance_ms: float = 50.0
    pitch_tolerance_cents: float = 50.0


@dataclass
class GroundTruth:
    """Complete ground truth for a test signal."""

    beats: list[BeatAnnotation] = field(default_factory=list)
    onsets: list[OnsetAnnotation] = field(default_factory=list)
    pitches: list[PitchAnnotation] = field(default_factory=list)


@dataclass
class SignalDefinition:
    """Complete definition of a test signal with ground truth."""

    signal_type: str
    metadata: SignalMetadata
    ground_truth: GroundTruth
    test_criteria: TestCriteria = field(default_factory=TestCriteria)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "signal_type": self.signal_type,
            "metadata": {
                "sample_rate": self.metadata.sample_rate,
                "duration": self.metadata.duration,
                "description": self.metadata.description,
                "channels": self.metadata.channels,
            },
            "ground_truth": {},
            "test_criteria": {
                "tempo_tolerance_bpm": self.test_criteria.tempo_tolerance_bpm,
                "beat_timing_tolerance_ms": self.test_criteria.beat_timing_tolerance_ms,
                "min_detection_rate": self.test_criteria.min_detection_rate,
                "onset_timing_tolerance_ms": self.test_criteria.onset_timing_tolerance_ms,
                "pitch_tolerance_cents": self.test_criteria.pitch_tolerance_cents,
            },
        }

        if self.metadata.bpm > 0:
            result["metadata"]["bpm"] = self.metadata.bpm

        if self.ground_truth.beats:
            result["ground_truth"]["beats"] = [
                {
                    "time": b.time,
                    "beat_number": b.beat_number,
                    "bar": b.bar,
                }
                for b in self.ground_truth.beats
            ]

        if self.ground_truth.onsets:
            result["ground_truth"]["onsets"] = [
                {
                    "time": o.time,
                    "attack_ms": o.attack_ms,
                    "type": o.onset_type,
                }
                for o in self.ground_truth.onsets
            ]

        if self.ground_truth.pitches:
            result["ground_truth"]["pitches"] = [
                {
                    "start_time": p.start_time,
                    "end_time": p.end_time,
                    "midi_note": p.midi_note,
                    "frequency_hz": p.frequency_hz,
                    "waveform": p.waveform,
                }
                for p in self.ground_truth.pitches
            ]

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SignalDefinition":
        """Create from dictionary (JSON deserialization)."""
        # Validate against schema
        validated = SIGNAL_SCHEMA(data)

        metadata = SignalMetadata(
            sample_rate=validated["metadata"]["sample_rate"],
            duration=validated["metadata"]["duration"],
            description=validated["metadata"]["description"],
            bpm=validated["metadata"].get("bpm", 0.0),
            channels=validated["metadata"].get("channels", 1),
        )

        ground_truth = GroundTruth()

        gt_data = validated["ground_truth"]
        if "beats" in gt_data:
            ground_truth.beats = [
                BeatAnnotation(
                    time=b["time"],
                    beat_number=b.get("beat_number", 1),
                    bar=b.get("bar", 1),
                )
                for b in gt_data["beats"]
            ]

        if "onsets" in gt_data:
            ground_truth.onsets = [
                OnsetAnnotation(
                    time=o["time"],
                    attack_ms=o.get("attack_ms", 1.0),
                    onset_type=o.get("type", "sharp"),
                )
                for o in gt_data["onsets"]
            ]

        if "pitches" in gt_data:
            ground_truth.pitches = [
                PitchAnnotation(
                    start_time=p["start_time"],
                    end_time=p["end_time"],
                    midi_note=p["midi_note"],
                    frequency_hz=p.get("frequency_hz", 0.0),
                    waveform=p.get("waveform", "sine"),
                )
                for p in gt_data["pitches"]
            ]

        test_criteria = TestCriteria()
        if "test_criteria" in validated:
            tc = validated["test_criteria"]
            test_criteria = TestCriteria(
                tempo_tolerance_bpm=tc.get("tempo_tolerance_bpm", 2.0),
                beat_timing_tolerance_ms=tc.get("beat_timing_tolerance_ms", 50.0),
                min_detection_rate=tc.get("min_detection_rate", 0.95),
                onset_timing_tolerance_ms=tc.get("onset_timing_tolerance_ms", 50.0),
                pitch_tolerance_cents=tc.get("pitch_tolerance_cents", 50.0),
            )

        return cls(
            signal_type=validated["signal_type"],
            metadata=metadata,
            ground_truth=ground_truth,
            test_criteria=test_criteria,
        )
