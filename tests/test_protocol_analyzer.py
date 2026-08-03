from analysis_engine.protocol_analyzer import (
    build_summary,
    extract_decisions,
    extract_tasks,
)


def test_extract_decisions() -> None:
    transcript = (
        "Обсудили состояние партии СП-10. "
        "Решили завершить функциональное тестирование до пятницы. "
        "После этого перешли к следующему вопросу."
    )

    decisions = extract_decisions(transcript)

    assert len(decisions) == 1
    assert "Решили завершить" in decisions[0]


def test_extract_task_with_deadline() -> None:
    transcript = (
        "Ответственный: Иванов должен подготовить отчёт до пятницы."
    )

    tasks = extract_tasks(transcript)

    assert len(tasks) == 1
    assert "подготовить отчёт" in tasks[0].description
    assert tasks[0].responsible == "Иванов"
    assert "до пятницы" in tasks[0].deadline
    assert tasks[0].status == "Не начато"


def test_duplicate_tasks_are_removed() -> None:
    transcript = (
        "Петров должен проверить плату до конца дня. "
        "Петров должен проверить плату до конца дня."
    )

    tasks = extract_tasks(transcript)

    assert len(tasks) == 1


def test_summary_prefers_decisions_and_tasks() -> None:
    transcript = (
        "Начали производственное совещание. "
        "Обсудили комплектующие. "
        "Решили запустить СП-9 во вторник. "
        "Иванов должен проверить документацию до конца дня. "
        "После этого совещание завершили."
    )

    summary = build_summary(transcript)

    assert "Решили запустить СП-9" in summary
    assert "Иванов должен проверить документацию" in summary