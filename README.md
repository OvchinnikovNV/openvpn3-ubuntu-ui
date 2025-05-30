## Сборка и запуск

### 1. Установить зависимости:

```
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

### 2. Собрать приложение:

```
pyinstaller --clean --onefile --windowed --name openvpn3-ubuntu-ui main.py
```

### 3. Запуск

В директории `/dist` должен появиться файл `openvpn3-ubuntu-ui`


## Добавление приложения в систему

#### 1. `cp dist/openvpn3-ubuntu-ui  ~/.local/bin/`

#### 2. `cp resources/openvpn-icon.png ~/.local/share/icons/`

#### 3. Создать файл `~/.local/share/applications/openvpn3-ubuntu-ui.desktop`:

Заменить `{USERNAME}` на имя пользователя системы!
    
```
[Desktop Entry]
Name=OpenVPN3 UI
Exec=/home/{USERNAME}/.local/bin/openvpn3-ubuntu-ui
Icon=/home/{USERNAME}/.local/share/icons/openvpn-icon.png
Type=Application
Categories=Utility;
```

## Дополнительная информация

Логи записываются в `/home/{USERNAME}/.local/state/openvpn3-ubuntu-ui/`
