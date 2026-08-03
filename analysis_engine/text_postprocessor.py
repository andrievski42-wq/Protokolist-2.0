from __future__ import annotations

import json
import re
from pathlib import Path


class TextPostprocessor:
    def __init__(self, dictionary_path: Path = Path("data/corporate_terms.json")) -> None:
        self.dictionary_path = dictionary_path
        self.terms: list[str] = []
        self.replacements: dict[str, str] = {}
        self.reload()

    def reload(self) -> None:
        if not self.dictionary_path.exists():
            self.terms = []
            self.replacements = {}
            return
        data = json.loads(self.dictionary_path.read_text(encoding="utf-8"))
        self.terms = [str(item) for item in data.get("terms", [])]
        self.replacements = {
            str(source): str(target)
            for source, target in data.get("replacements", {}).items()
        }

    def build_prompt(self, base_prompt: str = "") -> str:
        parts = [base_prompt.strip()]
        if self.terms:
            parts.append(
                "Корпоративные термины и имена: "
                + ", ".join(self.terms)
                + "."
            )
        return "\n".join(item for item in parts if item)

    def correct(self, text: str) -> str:
        result = text
        for source, target in sorted(
            self.replacements.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            result = re.sub(
                re.escape(source),
                target,
                result,
                flags=re.IGNORECASE,
            )
        result = re.sub(r"[ \t]+", " ", result)
        result = re.sub(r"\s+([,.!?;:])", r"\1", result)
        result = re.sub(r"([,.!?;:])(?=\S)", r"\1 ", result)
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result.strip()
