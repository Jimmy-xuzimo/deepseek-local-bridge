#!/usr/bin/env bash
# 启动服务（前台运行，Ctrl+C 停止）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -x "$ROOT/.venv/bin/python" ]; then
  "$ROOT/scripts/setup.sh"
fi

exec "$ROOT/.venv/bin/python" -m app run --open-admin "$@"
