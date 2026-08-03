# Sprint 2 — логирование

## 1. Скопируйте файлы

Скопируйте в корень проекта:

- `app_logging.py`
- `tests/test_logging.py`

## 2. Измените `main.py`

Полностью замените его на:

```python
from app_logging import setup_logging
from gui.main_window import ProtokolistApp


logger = setup_logging()


if __name__ == "__main__":
    logger.info("Программа запущена")

    try:
        app = ProtokolistApp()
        app.mainloop()
    except Exception:
        logger.exception("Критическая ошибка приложения")
        raise
    finally:
        logger.info("Программа завершена")
```

## 3. Измените `gui/main_window.py`

В начало файла, рядом с импортами, добавьте:

```python
import logging
```

После импортов добавьте:

```python
logger = logging.getLogger("protokolist.gui")
```

В метод `_whisper_ready` первой строкой добавьте:

```python
logger.info("Модель Whisper загружена: %s", model_name)
```

В метод `start_recording` перед `self.recorder.start()` добавьте:

```python
logger.info(
    "Начало записи. Совещание=%r, микрофон=%r",
    self.title_entry.get().strip(),
    self.device_combo.get(),
)
```

В метод `stop_recording` сразу после сохранения `audio_path` добавьте:

```python
logger.info("Запись остановлена. Файл=%s", audio_path)
```

В метод `_show_transcript` первой строкой добавьте:

```python
logger.info("Расшифровка завершена. Символов=%d", len(text))
```

В метод `save_project` после `self.project.save(meeting)` добавьте:

```python
logger.info("Проект сохранён: %s", self.project.folder)
```

В метод `_show_error` первой строкой добавьте:

```python
logger.exception("%s: %s", title, exc)
```

## 4. Измените `.gitignore`

Добавьте:

```gitignore
logs/
.pytest_cache/
```

## 5. Проверка

```powershell
python -m pytest -v
python main.py
```

После запуска появится файл:

```text
logs\protokolist.log
```

## 6. Коммит

```powershell
git add .
git commit -m "Add application logging"
git push
```
