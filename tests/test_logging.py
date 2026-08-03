from pathlib import Path

import app_logging


def test_setup_logging_creates_log_file(tmp_path: Path, monkeypatch) -> None:
    log_dir = tmp_path / "logs"
    log_file = log_dir / "protokolist.log"

    monkeypatch.setattr(app_logging, "LOG_DIR", log_dir)
    monkeypatch.setattr(app_logging, "LOG_FILE", log_file)

    logger = app_logging.logging.getLogger("protokolist")
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)

    logger = app_logging.setup_logging()
    logger.info("test message")

    for handler in logger.handlers:
        handler.flush()

    assert log_file.exists()
    assert "test message" in log_file.read_text(encoding="utf-8")
