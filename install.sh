#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
CONFIG_FILE="$PROJECT_DIR/config.json"
SERVICE_NAME="weatherbot"

echo "=== Установка зависимостей ==="
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install python-telegram-bot requests

echo "=== Настройка config.json ==="
if [ ! -f "$CONFIG_FILE" ]; then
    cat > "$CONFIG_FILE" <<EOL
{
    "city": "Khabarovsk",
    "latitude": 48.4827,
    "longitude": 135.0837,
    "lang": "ru",
    "units": "metric",
    "apis": {
        "open_meteo": {},
        "weatherapi": {
            "key": "YOUR_TOKEN"
        },
        "visual_crossing": {
            "key": "YOUR_TOKEN"
        }
    },
    "telegram_bot_token": "YOUR_TOKEN"
}
EOL
    echo "Файл config.json создан."
else
    echo "Файл config.json уже существует."
fi
nano "$CONFIG_FILE"

echo "=== Создание systemd сервиса ==="
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
sudo bash -c "cat > $SERVICE_FILE" <<EOL
[Unit]
Description=Weather Telegram Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
ExecStart=$VENV_DIR/bin/python $PROJECT_DIR/bot.py
Restart=always
User=$USER
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOL

echo "=== Перезапуск systemd и запуск бота ==="
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME

echo "✅ Бот запущен! Логи можно смотреть командой:"
echo "   sudo journalctl -u $SERVICE_NAME -f"
