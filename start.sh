#!/data/data/com.termux/files/usr/bin/bash
# Для Linux/Termux. Загружает .env и запускает бота с веб-сервером на 1230.
cd "$(dirname "$0")" || exit 1
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi
export WEB_PORT=1230
# PORT задаётся хостингом, если он нужен; локально используем 1230.
if [ -z "${PORT:-}" ]; then export PORT=1230; fi
if [ -z "${BOT_TOKEN:-}" ]; then
  echo "BOT_TOKEN не задан. Скопируй .env.example в .env и заполни его."
  exit 1
fi
python -m pip install -r requirements.txt
exec python main.py
