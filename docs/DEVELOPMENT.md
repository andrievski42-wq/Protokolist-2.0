# Разработка

## Рабочий процесс

Перед началом работы:

```powershell
git pull
git status
```

После изменения:

```powershell
git add .
git commit -m "Краткое описание изменения"
git push
```

## Создание ветки

Для значительной функции:

```powershell
git switch -c feature/logging
```

После завершения:

```powershell
git add .
git commit -m "Add application logging"
git push -u origin feature/logging
```

## Проверка проекта

```powershell
python -m compileall .
python main.py
```

После добавления тестов:

```powershell
python -m pytest
```
