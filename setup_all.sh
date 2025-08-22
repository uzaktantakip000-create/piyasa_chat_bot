#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 1) Python kontrolu ve sanal ortam
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 gerekli. Lutfen yukleyin." >&2
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "[1/5] Sanal ortam olusturuluyor..."
  python3 -m venv .venv
fi
source .venv/bin/activate

# 2) Bagimliliklar
echo "[2/5] Bagimliliklar yukleniyor..."
pip install -U pip
if [ -f requirements.txt ]; then
  pip install -r requirements.txt
else
  pip install fastapi "uvicorn[standard]" sqlalchemy python-dotenv redis openai httpx
fi

# 3) .env dosyasi
echo "[3/5] .env hazirlaniyor..."
if [ ! -f .env ]; then
  cp .env.example .env
fi
set_env() {
  key="$1"; val="$2"
  [ -z "$val" ] && return
  if grep -q "^$key=" .env 2>/dev/null; then
    sed -i.bak "/^$key=/d" .env && rm -f .env.bak
  fi
  echo "$key=$val" >> .env
}
read -p "OpenAI API key (sk- ile baslar): " OPENAI_API_KEY
set_env OPENAI_API_KEY "$OPENAI_API_KEY"
read -p "REDIS_URL (opsiyonel): " REDIS_URL
set_env REDIS_URL "$REDIS_URL"
read -p "DATABASE_URL (opsiyonel): " DATABASE_URL
set_env DATABASE_URL "$DATABASE_URL"

# 4) API ve Worker
echo "[4/5] API ve Worker baslatiliyor..."
uvicorn main:app --host 0.0.0.0 --port 8000 &
API_PID=$!
python worker.py &
WORKER_PID=$!

# 5) Frontend
if [ -f package.json ]; then
  echo "[5/5] Frontend baslatiliyor..."
  if command -v npm >/dev/null 2>&1; then
    if [ ! -d node_modules ]; then
      npm install
    fi
    npm run dev &
    FRONT_PID=$!
    echo "Frontend: http://localhost:5173"
  else
    echo "npm bulunamadi; frontend atlandi."
  fi
else
  echo "package.json yok; frontend atlandi."
fi

echo "API: http://localhost:8000"
echo "Dokumantasyon: http://localhost:8000/docs"

wait $API_PID $WORKER_PID ${FRONT_PID:-}
