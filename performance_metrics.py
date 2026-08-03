from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import soundfile as sf


@dataclass(frozen=True)
class RecognitionMetrics:
    model_name: str
    audio_seconds: float
    processing_seconds: float
    realtime_factor: float
    characters: int

    @property
    def faster_than_realtime(self) -> bool:
        return self.realtime_factor < 1.0


def get_audio_duration(audio_path: Path) -> float:
    info = sf.info(str(audio_path))

    if info.samplerate <= 0:
        return 0.0

    return float(info.frames) / float(info.samplerate)


def build_metrics(
    model_name: str,
    audio_path: Path,
    started_at: float,
    text: str,
) -> RecognitionMetrics:
    processing_seconds = max(
        0.0,
        time.perf_counter() - started_at,
    )
    audio_seconds = get_audio_duration(audio_path)

    realtime_factor = (
        processing_seconds / audio_seconds
        if audio_seconds > 0
        else 0.0
    )

    return RecognitionMetrics(
        model_name=model_name,
        audio_seconds=audio_seconds,
        processing_seconds=processing_seconds,
        realtime_factor=realtime_factor,
        characters=len(text),
    )


def format_metrics(metrics: RecognitionMetrics) -> str:
    speed_description = (
        "быстрее реального времени"
        if metrics.faster_than_realtime
        else "медленнее реального времени"
    )

    return (
        f"модель={metrics.model_name}; "
        f"аудио={metrics.audio_seconds:.1f} с; "
        f"обработка={metrics.processing_seconds:.1f} с; "
        f"RTF={metrics.realtime_factor:.2f}; "
        f"символов={metrics.characters}; "
        f"{speed_description}"
    )
