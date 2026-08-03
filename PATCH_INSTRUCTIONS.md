# Sprint 2 — проверка окружения

Скопируйте в корень проекта:

- `system_check.py`
- `tests/test_system_check.py`

Полностью замените `main.py`:

```python
from tkinter import messagebox

from app_logging import setup_logging
from gui.main_window import ProtokolistApp
from system_check import (
    format_check_report,
    has_critical_errors,
    run_system_checks,
)

logger = setup_logging()

if __name__ == "__main__":
    logger.info("Программа запущена")
    try:
        checks = run_system_checks()
        report = format_check_report(checks)
        logger.info("Проверка окружения:\n%s", report)

        app = ProtokolistApp()

        if has_critical_errors(checks):
            app.after(
                200,
                lambda: messagebox.showwarning(
                    "Проверка системы",
                    "Обнаружены проблемы:\n\n" + report,
                ),
            )

        app.mainloop()
    except Exception:
        logger.exception("Критическая ошибка приложения")
        raise
    finally:
        logger.info("Программа завершена")
```

Проверка:

```powershell
python -m pytest -v
python main.py
```

Коммит:

```powershell
git add .
git commit -m "Add startup environment checks"
git push
```
