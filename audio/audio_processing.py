from __future__ import annotations

import subprocess
from pathlib import Path


def enhance_speech(input_path: Path, output_path: Path) -> Path:
    """Подготавливает речь для ASR: убирает гул, часть шума и нормализует громкость."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    filters = (
        "highpass=f=80,"
        "lowpass=f=7600,"
        "afftdn=nf=-25,"
        "loudnorm=I=-16:LRA=11:TP=-1.5"
    )

    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(input_path),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-af",
        filters,
        str(output_path),
    ]

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        return output_path
    except (subprocess.CalledProcessError, FileNotFoundError):
        # При проблеме с фильтрацией используем исходник, чтобы не сорвать работу.
        return input_path
