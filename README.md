# Время намаза

Время ближайшего намаза текстом прямо в панели задач Windows 11, слева от кнопки «Пуск».

- Показывает следующий намаз и сколько до него осталось.
- Когда время наступает, надпись 15 минут подсвечена зелёным и приходит уведомление Windows.
- Левой кнопкой мыши можно сдвинуть надпись относительно «Пуска» (положение запоминается).
- Правая кнопка — расписание на день, «Сбросить положение», «Выход».

Время считается астрономически (алгоритм PrayTimes): Фаджр 16°, Иша 15° (метод ДУМ РФ),
ханафитский Аср. Город, координаты, углы и поправки задаются в начале `prayer_tray.py`
(по умолчанию — Москва).

## Установка

Скачайте `PrayTime-Setup-*.exe` из [Releases](https://github.com/SulaymonHursanov/pray-time/releases)
и запустите. Права администратора не нужны; по умолчанию включён автозапуск вместе с Windows.

Установщик не подписан, поэтому Windows может показать «Windows защитила ваш компьютер» —
нажмите «Подробнее» → «Выполнить в любом случае».

## Запуск из исходников

```
pip install comtypes pystray pillow
pythonw prayer_tray.py
```

`python prayer_tray.py --debug` — режим отладки (фон окошка красный и непрозрачный).

Настройки сохраняются в `%APPDATA%\PrayTime\prayer_tray.json`.

## Сборка установщика

Нужны Python 3 и [Inno Setup 6](https://jrsoftware.org/isdl.php) (`choco install innosetup`).

```
powershell -ExecutionPolicy Bypass -File build.ps1
```

Скрипт создаёт окружение `.venv-build`, собирает `dist\PrayTime\PrayTime.exe` через PyInstaller
и установщик `dist\PrayTime-Setup-<версия>.exe`. Версия задаётся в `installer\PrayTime.iss`.
