# Куда скопировать файлы

1. `gui/main_window.py` → заменить файл:
   `C:\Projects\Protokolist\gui\main_window.py`

2. `performance_metrics.py` → положить в корень:
   `C:\Projects\Protokolist\performance_metrics.py`

3. `tests/test_performance_metrics.py` → положить в:
   `C:\Projects\Protokolist\tests\test_performance_metrics.py`

## Проверка

```powershell
python -m pytest -v
python main.py
```

После тестовой записи проверьте:

```text
logs\protokolist.log
```

Там должны появиться строки:

```text
Метрики живого фрагмента: ...
Метрики распознавания: ...
```

## Коммит

```powershell
git add .
git commit -m "Add recognition performance metrics"
git push
```
