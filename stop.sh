#!/usr/bin/env bash
# Stops backend + frontend started by start.sh. Leaves Postgres running
# (it's a shared container, not worth tearing down on every stop) —
# `docker compose stop postgres` yourself if you actually want that.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT_DIR/.run"

stop_one() {
  local name="$1" pid_file="$RUN_DIR/$1.pid"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "==> Stopping $name (pid $pid)"
      kill "$pid" 2>/dev/null
      for _ in $(seq 1 10); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.5
      done
      kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null
    else
      echo "==> $name not running (stale pid file)"
    fi
    rm -f "$pid_file"
  else
    echo "==> $name not running"
  fi
}

stop_one backend
stop_one frontend

echo
echo "Postgres left running — stop it yourself with:"
echo "  docker compose -f '$ROOT_DIR/docker-compose.yml' stop postgres"
