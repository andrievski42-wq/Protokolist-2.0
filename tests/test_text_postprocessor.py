from pathlib import Path

from analysis_engine.text_postprocessor import TextPostprocessor


def test_known_replacements(tmp_path: Path) -> None:
    dictionary_path = tmp_path / "terms.json"
    dictionary_path.write_text(
        """
        {
          "terms": ["Whisper", "офлайн", "DDR"],
          "replacements": {
            "виспер": "Whisper",
            "оуфлайн": "офлайн",
            "ддр": "DDR"
          }
        }
        """,
        encoding="utf-8",
    )

    processor = TextPostprocessor(dictionary_path)

    source = "Виспер работает оуфлайн и распознаёт ддр."
    result = processor.correct(source)

    assert "Whisper" in result
    assert "офлайн" in result
    assert "DDR" in result


def test_prompt_contains_corporate_terms(tmp_path: Path) -> None:
    dictionary_path = tmp_path / "terms.json"
    dictionary_path.write_text(
        """
        {
          "terms": ["RDW", "H760", "СП-10"],
          "replacements": {}
        }
        """,
        encoding="utf-8",
    )

    processor = TextPostprocessor(dictionary_path)
    prompt = processor.build_prompt("Производственное совещание.")

    assert "Производственное совещание" in prompt
    assert "RDW" in prompt
    assert "H760" in prompt
    assert "СП-10" in prompt


def test_spacing_is_normalized(tmp_path: Path) -> None:
    dictionary_path = tmp_path / "terms.json"
    dictionary_path.write_text(
        """
        {
          "terms": [],
          "replacements": {}
        }
        """,
        encoding="utf-8",
    )

    processor = TextPostprocessor(dictionary_path)

    result = processor.correct(
        "Это   тест  ,который   должен работать."
    )

    assert result == "Это тест, который должен работать."