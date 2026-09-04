#!/usr/bin/env bash
# Lanzador para Linux/macOS (equivalente a iniciar.bat).
# Arranca backend y frontend, espera a que respondan y los para con Ctrl+C.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
BACKEND_PORT="${WEBDOM_BACKEND_PORT:-8000}"
FRONTEND_PORT="${WEBDOM_FRONTEND_PORT:-5173}"
mkdir -p logs

PY="$ROOT/venv/bin/python"
[ -x "$PY" ] || PY="$ROOT/.venv-linux/bin/python"
if [ ! -x "$PY" ]; then
    echo "Creando entorno virtual..."
    python3 -m venv "$ROOT/venv"
    PY="$ROOT/venv/bin/python"
    "$PY" -m pip install -q -r requirements.txt
fi

"$PY" -c "import fastapi, uvicorn, sqlalchemy" 2>/dev/null || "$PY" -m pip install -q -r requirements.txt

wait_for() {
    local url="$1" name="$2" tries=0
    until curl -fsS -o /dev/null --max-time 3 "$url"; do
        tries=$((tries + 1))
        if [ "$tries" -gt 60 ]; then
            echo "[ERROR] $name no respondio en $url"
            return 1
        fi
        sleep 1
    done
    echo "$name listo: $url"
}

cleanup() {
    echo "Deteniendo servicios..."
    [ -n "${BACK_PID:-}" ] && kill "$BACK_PID" 2>/dev/null || true
    [ -n "${FRONT_PID:-}" ] && kill "$FRONT_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

"$PY" run.py >logs/backend.log 2>&1 &
BACK_PID=$!
wait_for "http://127.0.0.1:$BACKEND_PORT/docs" "Backend" || { tail -20 logs/backend.log; exit 1; }

if command -v npm >/dev/null 2>&1 && [ -f frontend/package.json ]; then
    [ -d frontend/node_modules ] || (cd frontend && npm install --no-fund --no-audit)
    (cd frontend && npm run dev) >logs/frontend.log 2>&1 &
    FRONT_PID=$!
    wait_for "http://127.0.0.1:$FRONTEND_PORT/" "Frontend" || tail -20 logs/frontend.log
else
    echo "[AVISO] npm no disponible: solo backend."
fi

echo "Pulsa Ctrl+C para detener."
wait
