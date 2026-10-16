#!/usr/bin/env bash
# 重启后台服务（用于让端口/局域网访问设置生效）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

"$ROOT/scripts/stop.sh" || true
sleep 2

if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "未找到 .venv，请先运行 scripts/setup.sh。" >&2
  exit 1
fi

mkdir -p "$ROOT/logs"
nohup "$ROOT/.venv/bin/python" -m app run --open-admin \
  > "$ROOT/logs/service.out.log" 2> "$ROOT/logs/service.err.log" &
echo "服务已在后台启动（PID $!）。"
sleep 4

if curl -fsS --max-time 5 "http://127.0.0.1:8317/healthz" >/dev/null 2>&1; then
  echo "健康检查通过：http://127.0.0.1:8317/healthz"
else
  echo "服务可能未正常启动，请查看 logs/service.err.log。" >&2
fi
