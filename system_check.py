from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import sounddevice as sd


@dataclass
class CheckResult:
    name: str
    ok: bool
    message: str


REQUIRED_DIRS = (
    Path("archive"),
    Path("recordings"),
    Path("data"),
    Path("logs"),
)


def ensure_required_directories() -> list[CheckResult]:
    results = []
    for directory in REQUIRED_DIRS:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            results.append(CheckResult(f"Папка {directory}", True, "готова"))
        except OSError as exc:
            results.append(CheckResult(f"Папка {directory}", False, str(exc)))
    return results


def check_ffmpeg() -> CheckResult:
    executable = shutil.which("ffmpeg")
    if executable:
        return CheckResult("FFmpeg", True, executable)
    return CheckResult("FFmpeg", False, "FFmpeg не найден в PATH.")


def check_microphone() -> CheckResult:
    try:
        devices = sd.query_devices()
        count = sum(
            1 for device in devices
            if int(device.get("max_input_channels", 0)) > 0
        )
        if count:
            return CheckResult("Микрофон", True, f"найдено устройств: {count}")
        return CheckResult("Микрофон", False, "Не найдено устройств записи.")
    except Exception as exc:
        return CheckResult("Микрофон", False, str(exc))


def check_free_space(path: Path = Path("."), minimum_gb: float = 5.0) -> CheckResult:
    try:
        usage = shutil.disk_usage(path.resolve())
        free_gb = usage.free / (1024 ** 3)
        return CheckResult(
            "Свободное место",
            free_gb >= minimum_gb,
            f"{free_gb:.1f} ГБ свободно",
        )
    except OSError as exc:
        return CheckResult("Свободное место", False, str(exc))


def run_system_checks() -> list[CheckResult]:
    results = ensure_required_directories()
    results.append(check_ffmpeg())
    results.append(check_microphone())
    results.append(check_free_space())
    return results


def format_check_report(results: list[CheckResult]) -> str:
    return "\n".join(
        f"{'✓' if result.ok else '✗'} {result.name}: {result.message}"
        for result in results
    )


def has_critical_errors(results: list[CheckResult]) -> bool:
    critical = {"FFmpeg", "Микрофон", "Свободное место"}
    return any(not item.ok and item.name in critical for item in results)
