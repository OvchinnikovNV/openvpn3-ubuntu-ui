## Сборка и запуск

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

## Сборка бинарника

```bash
. .venv/bin/activate
pyinstaller --clean --onefile --windowed --name openvpn3-ubuntu-ui main.py
cp dist/openvpn3-ubuntu-ui ~/.local/bin/
```

Перед `cp` закройте приложение, иначе файл будет занят.

## Установка в меню

1. `cp dist/openvpn3-ubuntu-ui ~/.local/bin/`
2. Создайте `~/.local/share/applications/openvpn3-ubuntu-ui.desktop`:

```
[Desktop Entry]
Name=OpenVPN3 UI
Exec=/home/{USERNAME}/.local/bin/openvpn3-ubuntu-ui
Type=Application
Terminal=false
Categories=Network;
```

## Разработка UI

После правок в `ui/designer/*.ui`:

```bash
pyuic6 ui/designer/mainwindow.ui -o ui/pyuic/mainwindow.py
pyuic6 ui/designer/manager.ui -o ui/pyuic/manager.py
```

## Структура

```
main.py              — точка входа
widgets/             — окна приложения
utils/               — openvpn3 CLI, worker, профили
ui/styles.py         — стили
ui/designer/         — макеты Qt Designer
ui/pyuic/            — сгенерированный UI-код
logger.py            — логи в ~/.local/state/openvpn3-ubuntu-ui/log.log
```

Профили подключений: `~/.config/openvpn3-ubuntu-ui/connections.json`

## Зависимости системы

```bash
sudo apt-get install openvpn3-client libxcb-cursor0 libxcb-xinerama0 libxcb-icccm4 \
  libxcb-keysyms1 libxcb-render-util0 libxcb-xkb1
```
