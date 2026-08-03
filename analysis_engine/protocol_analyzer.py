from __future__ import annotations

import re
from dataclasses import dataclass

from models.meeting import Task


DECISION_MARKERS = (
    "решили",
    "принято решение",
    "договорились",
    "утвердили",
    "согласовали",
    "необходимо",
    "следует",
)

TASK_MARKERS = (
    "должен",
    "должна",
    "должны",
    "поручить",
    "поручено",
    "подготовить",
    "сделать",
    "проверить",
    "заказать",
    "согласовать",
    "предоставить",
    "завершить",
    "выпустить",
)

DEADLINE_PATTERN = re.compile(
    r"(до\s+\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?"
    r"|до\s+(?:понедельника|вторника|среды|четверга|пятницы|субботы|воскресенья)"
    r"|к\s+\d{1,2}\s+[а-яё]+"
    r"|до\s+конца\s+(?:дня|недели|месяца)"
    r"|срок\s*[:\-]?\s*[^,.!?]+)",
    re.IGNORECASE,
)

RESPONSIBLE_PATTERN = re.compile(
    r"(?i:ответственный|исполнитель)\s*[:\-–—]?\s*"
    r"([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){0,2})"
    r"(?=\s+(?:должен|должна|должны|поручено|поручить)\b|[,.!?;:]|$)"
)


def _sentences(text: str) -> list[str]:
    clean = re.sub(r"\[\d{2}:\d{2}(?::\d{2})?\]\s*", "", text)
    parts = re.split(r"(?<=[.!?])\s+|\n+", clean)
    return [part.strip() for part in parts if len(part.strip()) >= 8]


def build_summary(text: str, max_sentences: int = 6) -> str:
    sentences = _sentences(text)
    if not sentences:
        return ""
    important = [
        sentence
        for sentence in sentences
        if any(marker in sentence.lower() for marker in DECISION_MARKERS + TASK_MARKERS)
    ]
    selected = important[:max_sentences]
    if len(selected) < max_sentences:
        for sentence in sentences:
            if sentence not in selected:
                selected.append(sentence)
            if len(selected) >= max_sentences:
                break
    return "\n".join(f"• {item}" for item in selected)


def extract_decisions(text: str) -> list[str]:
    decisions: list[str] = []
    for sentence in _sentences(text):
        lowered = sentence.lower()
        if any(marker in lowered for marker in DECISION_MARKERS):
            decisions.append(sentence)
    return _deduplicate(decisions)


def extract_tasks(text: str) -> list[Task]:
    tasks: list[Task] = []
    for sentence in _sentences(text):
        lowered = sentence.lower()
        if not any(marker in lowered for marker in TASK_MARKERS):
            continue

        deadline_match = DEADLINE_PATTERN.search(sentence)
        responsible_match = RESPONSIBLE_PATTERN.search(sentence)

        tasks.append(
            Task(
                responsible=(
                    responsible_match.group(1).strip()
                    if responsible_match
                    else ""
                ),
                description=sentence,
                deadline=(
                    deadline_match.group(1).strip()
                    if deadline_match
                    else ""
                ),
                status="Не начато",
                source_text=sentence,
            )
        )
    unique: list[Task] = []
    seen: set[str] = set()
    for task in tasks:
        key = task.description.lower()
        if key not in seen:
            seen.add(key)
            unique.append(task)
    return unique


def _deduplicate(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
