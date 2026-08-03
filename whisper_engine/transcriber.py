from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from faster_whisper import WhisperModel


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


class Transcriber:
    def __init__(
        self,
        model_name: str = "medium",
        device: str = "cpu",
        compute_type: str = "int8",
        cpu_threads: int = 4,
        num_workers: int = 1,
    ) -> None:
        self.model_name = model_name
        print(f"Загрузка модели Whisper: {model_name}...")
        self.model = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
            cpu_threads=max(1, int(cpu_threads)),
            num_workers=max(1, int(num_workers)),
        )
        print(f"Whisper готов: {model_name}")

    def transcribe(
        self,
        audio_file: Path,
        language: str = "ru",
        beam_size: int = 7,
        temperature: float = 0.0,
        initial_prompt: str = "",
        live_mode: bool = False,
        no_speech_threshold: float = 0.55,
        log_prob_threshold: float = -1.0,
        compression_ratio_threshold: float = 2.4,
    ) -> list[TranscriptSegment]:
        segments, _ = self.model.transcribe(
            str(audio_file),
            language=language,
            task="transcribe",
            beam_size=beam_size,
            temperature=temperature,
            vad_filter=True,
            vad_parameters={
                "min_silence_duration_ms": 350 if live_mode else 500,
                "speech_pad_ms": 250,
            },
            # Для коротких живых окон отключаем перенос декодерного состояния:
            # это уменьшает накопление ошибочных фраз и повторов.
            condition_on_previous_text=not live_mode,
            initial_prompt=initial_prompt.strip() or None,
            no_speech_threshold=no_speech_threshold,
            log_prob_threshold=log_prob_threshold,
            compression_ratio_threshold=compression_ratio_threshold,
            repetition_penalty=1.08,
        )

        result: list[TranscriptSegment] = []
        for segment in segments:
            text = segment.text.strip()
            if text:
                result.append(
                    TranscriptSegment(
                        start=float(segment.start),
                        end=float(segment.end),
                        text=text,
                    )
                )
        return result


def format_timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02}:{minutes:02}:{secs:02}"
    return f"{minutes:02}:{secs:02}"


def format_segments(segments: list[TranscriptSegment]) -> str:
    return "\n".join(
        f"[{format_timestamp(item.start)}] {item.text}"
        for item in segments
    )
