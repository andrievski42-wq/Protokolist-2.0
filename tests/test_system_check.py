from pathlib import Path

import system_check


def test_check_ffmpeg_found(monkeypatch) -> None:
    monkeypatch.setattr(system_check.shutil, "which", lambda name: "ffmpeg.exe")
    result = system_check.check_ffmpeg()
    assert result.ok is True


def test_check_ffmpeg_missing(monkeypatch) -> None:
    monkeypatch.setattr(system_check.shutil, "which", lambda name: None)
    result = system_check.check_ffmpeg()
    assert result.ok is False


def test_ensure_required_directories(tmp_path: Path, monkeypatch) -> None:
    directories = tuple(tmp_path / name for name in ("archive", "recordings", "data", "logs"))
    monkeypatch.setattr(system_check, "REQUIRED_DIRS", directories)
    results = system_check.ensure_required_directories()
    assert all(item.ok for item in results)
    assert all(path.exists() for path in directories)


def test_format_check_report() -> None:
    report = system_check.format_check_report([
        system_check.CheckResult("FFmpeg", True, "готов"),
        system_check.CheckResult("Микрофон", False, "не найден"),
    ])
    assert "✓ FFmpeg" in report
    assert "✗ Микрофон" in report
