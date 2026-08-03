from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd
import soundfile as sf


class Recorder:
    def __init__(self, sample_rate: int = 16000) -> None:
        self.sample_rate = sample_rate
        self.recording = False
        self.audio_data: list[np.ndarray] = []
        self.live_buffer: list[np.ndarray] = []
        self.stream: Optional[sd.InputStream] = None
        self.device_index: int | None = None
        self.last_level = 0.0
        self._lock = threading.Lock()

    def set_device(self, device_index: int | None) -> None:
        self.device_index = device_index

    def start(self) -> None:
        if self.recording:
            return

        with self._lock:
            self.audio_data = []
            self.live_buffer = []
        self.last_level = 0.0
        self.recording = True

        def callback(indata, frames, time_info, status) -> None:
            if status:
                print(f"Audio status: {status}")
            if self.recording:
                block = indata.copy()
                with self._lock:
                    self.audio_data.append(block)
                    self.live_buffer.append(block)
                self.last_level = float(np.sqrt(np.mean(np.square(block))))

        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            device=self.device_index,
            callback=callback,
        )
        self.stream.start()

    def pop_live_chunk(self, overlap_seconds: float = 0.0) -> np.ndarray | None:
        """Возвращает окно и сохраняет его хвост для перекрытия со следующим окном."""
        with self._lock:
            if not self.live_buffer:
                return None

            audio = np.concatenate(self.live_buffer, axis=0)
            overlap_frames = max(0, int(overlap_seconds * self.sample_rate))

            if overlap_frames > 0 and len(audio) > overlap_frames:
                tail = audio[-overlap_frames:].copy()
                self.live_buffer = [tail]
            else:
                self.live_buffer = []

        return audio

    def live_buffer_duration(self) -> float:
        with self._lock:
            frames = sum(len(block) for block in self.live_buffer)
        return frames / self.sample_rate

    def stop(self, target_dir: Path) -> Path:
        if not self.recording:
            raise RuntimeError("Запись ещё не была запущена.")

        self.recording = False

        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        with self._lock:
            if not self.audio_data:
                raise RuntimeError("Не удалось получить звук с микрофона.")
            audio = np.concatenate(self.audio_data, axis=0)

        target_dir.mkdir(parents=True, exist_ok=True)
        filepath = target_dir / datetime.now().strftime("audio_%Y%m%d_%H%M%S.wav")
        sf.write(filepath, audio, self.sample_rate)
        return filepath
