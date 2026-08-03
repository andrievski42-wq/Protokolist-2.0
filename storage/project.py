from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from models.meeting import MeetingData


def _safe_name(value: str) -> str:
    value = value.strip() or "Новое совещание"
    value = re.sub(r'[<>:"/\\|?*]+', "_", value)
    return value[:80]


class MeetingProject:
    def __init__(self, title: str) -> None:
        created = datetime.now()
        folder_name = f"{created:%Y-%m-%d_%H-%M}_{_safe_name(title)}"
        self.folder = Path("archive") / folder_name
        self.folder.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_folder(cls, folder: Path) -> "MeetingProject":
        obj = cls.__new__(cls)
        obj.folder = folder
        return obj

    def save(self, meeting: MeetingData) -> Path:
        path = self.folder / "meeting.json"
        path.write_text(
            json.dumps(meeting.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (self.folder / "transcript.txt").write_text(
            meeting.transcript.strip(),
            encoding="utf-8",
        )
        return path

    def load(self) -> MeetingData:
        path = self.folder / "meeting.json"
        if not path.exists():
            raise FileNotFoundError("В папке нет meeting.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        return MeetingData.from_dict(data)
