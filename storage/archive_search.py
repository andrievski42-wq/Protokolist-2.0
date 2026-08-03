from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SearchResult:
    folder: Path
    title: str
    created_at: str
    snippet: str


def search_archive(query: str, archive_dir: Path = Path("archive")) -> list[SearchResult]:
    query = query.strip().lower()
    if not query or not archive_dir.exists():
        return []

    results: list[SearchResult] = []

    for meeting_file in archive_dir.glob("*/meeting.json"):
        try:
            data = json.loads(meeting_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        searchable_parts = [
            data.get("title", ""),
            data.get("chairman", ""),
            data.get("secretary", ""),
            data.get("participants", ""),
            data.get("agenda", ""),
            data.get("discussion", ""),
            data.get("decisions", ""),
            data.get("transcript", ""),
            data.get("summary", ""),
        ]

        for task in data.get("tasks", []):
            searchable_parts.extend([
                task.get("responsible", ""),
                task.get("description", ""),
                task.get("deadline", ""),
                task.get("status", ""),
            ])

        haystack = "\n".join(searchable_parts)
        lowered = haystack.lower()
        position = lowered.find(query)
        if position < 0:
            continue

        start = max(0, position - 90)
        end = min(len(haystack), position + len(query) + 140)
        snippet = haystack[start:end].replace("\n", " ").strip()

        results.append(
            SearchResult(
                folder=meeting_file.parent,
                title=data.get("title", "") or meeting_file.parent.name,
                created_at=data.get("created_at", ""),
                snippet=snippet,
            )
        )

    results.sort(key=lambda item: item.created_at, reverse=True)
    return results
