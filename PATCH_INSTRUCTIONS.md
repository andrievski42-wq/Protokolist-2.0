# Sprint 2 — метрики производительности

## 1. Скопируйте файлы

В корень проекта:

- `performance_metrics.py`
- `tests/test_performance_metrics.py`

## 2. Измените `gui/main_window.py`

В импорты добавьте:

```python
from performance_metrics import build_metrics, format_metrics
```

`import time` у вас уже есть.

## 3. Измените `_recognize_full_audio`

В начале метода, сразу после `try:`, добавьте:

```python
started_at = time.perf_counter()
```

После формирования итогового текста и словарной коррекции добавьте:

```python
metrics = build_metrics(
    model_name=engine.model_name,
    audio_path=input_path,
    started_at=started_at,
    text=text,
)
logger.info("Метрики распознавания: %s", format_metrics(metrics))
```

## 4. Измените `_transcribe_live_array`

Перед вызовом `self.transcriber.transcribe(...)` добавьте:

```python
started_at = time.perf_counter()
```

После формирования `block` добавьте:

```python
metrics = build_metrics(
    model_name=self.transcriber.model_name,
    audio_path=input_path,
    started_at=started_at,
    text=block,
)
logger.info("Метрики живого фрагмента: %s", format_metrics(metrics))
```

## 5. Проверка

```powershell
python -m pytest -v
python main.py
```

В `logs\protokolist.log` появятся строки с `RTF`:

- `RTF < 1.0` — быстрее реального времени;
- `RTF = 1.0` — на границе;
- `RTF > 1.0` — модель не успевает.

## 6. Коммит

```powershell
git add .
git commit -m "Add speech recognition performance metrics"
git push
```
