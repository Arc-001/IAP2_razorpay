#!/usr/bin/env bash
# One-point start for the whole stack: Postgres (docker), backend (FastAPI),
# frontend (Vue/Vite). Safe to re-run — skips anything already running.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT_DIR/.run"
mkdir -p "$RUN_DIR"

BACKEND_PORT="${BACKEND_PORT:-8123}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

is_running() {
  local pid_file="$1"
  [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null
}

echo "==> Postgres"
if docker compose -f "$ROOT_DIR/docker-compose.yml" ps postgres --status running 2>/dev/null | grep -q postgres; then
  echo "    already running"
else
  docker compose -f "$ROOT_DIR/docker-compose.yml" up -d postgres
fi

echo "==> Backend (FastAPI, :$BACKEND_PORT)"
if is_running "$RUN_DIR/backend.pid"; then
  echo "    already running (pid $(cat "$RUN_DIR/backend.pid"))"
else
  (
    cd "$ROOT_DIR/api"
    nohup uv run uvicorn app.main:app --port "$BACKEND_PORT" --reload \
      > "$RUN_DIR/backend.log" 2>&1 &
    echo $! > "$RUN_DIR/backend.pid"
  )
  echo "    starting (pid $(cat "$RUN_DIR/backend.pid")), log: .run/backend.log"

  for _ in $(seq 1 30); do
    if curl -s -o /dev/null "http://localhost:$BACKEND_PORT/health"; then
      echo "    healthy"
      break
    fi
    sleep 1
  done
fi

echo "==> Frontend (Vite, :$FRONTEND_PORT)"
if is_running "$RUN_DIR/frontend.pid"; then
  echo "    already running (pid $(cat "$RUN_DIR/frontend.pid"))"
else
  (
    cd "$ROOT_DIR/web"
    nohup npm run dev -- --port "$FRONTEND_PORT" \
      > "$RUN_DIR/frontend.log" 2>&1 &
    echo $! > "$RUN_DIR/frontend.pid"
  )
  echo "    starting (pid $(cat "$RUN_DIR/frontend.pid")), log: .run/frontend.log"
fi

echo
echo "Backend:  http://localhost:$BACKEND_PORT  (docs: /docs, health: /health, audit: /audit)"
echo "Frontend: http://localhost:$FRONTEND_PORT"
echo "Logs:     $RUN_DIR/{backend,frontend}.log"
echo "Stop with: ./stop.sh"
