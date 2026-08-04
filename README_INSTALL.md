# Установка обновления Corporate UI + VU-метр

Скопируйте содержимое архива в:

```text
C:\Projects\Protokolist
```

с сохранением структуры папок и заменой:

```text
gui\main_window.py
```

Должна появиться новая папка:

```text
assets\
```

В ней находятся:

- `company_logo_light.png`
- `company_logo_dark.png`
- `company_logo_light.svg`
- `company_logo_dark.svg`
- `app_icon.png`

## Зависимость

Проверьте, установлен ли Pillow:

```powershell
python -m pip show Pillow
```

Если пакет не найден:

```powershell
python -m pip install Pillow
```

И добавьте в `requirements.txt`:

```text
Pillow>=10.0
```

## Проверка

```powershell
python -m pytest -v
python main.py
```

Во время записи должны отображаться:

- фирменный логотип в верхней части окна;
- иконка приложения;
- индикатор «Уровень микрофона»;
- числовой уровень от 0% до 100%.

## Коммит

```powershell
git add .
git commit -m "Add corporate branding and restore microphone level meter"
git push
```
