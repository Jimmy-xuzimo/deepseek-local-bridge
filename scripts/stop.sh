#!/usr/bin/env bash
# 停止后台运行的服务（含浏览器子进程）
set -euo pipefail

DATA_DIR="${DSB_DATA_DIR:-}"
if [ -z "$DATA_DIR" ]; then
  if [ "$(uname -s)" = "Darwin" ]; then
    DATA_DIR="$HOME/Library/Application Support/DeepSeekBridge"
  else
    DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/DeepSeekBridge"
  fi
fi

PID_FILE="$DATA_DIR/service.pid"
if [ ! -f "$PID_FILE" ]; then
  echo "未找到 service.pid，服务可能未在后台运行。"
  exit 0
fi

pid="$(tr -d '[:space:]' < "$PID_FILE")"
if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
  echo "进程 $pid 不存在，清理 pid 文件。"
  rm -f "$PID_FILE"
  exit 0
fi

# 只结束确实属于本服务的进程
cmdline="$(ps -o command= -p "$pid" 2>/dev/null || true)"
if ! printf '%s' "$cmdline" | grep -q "app run"; then
  echo "拒绝结束：进程 $pid 的命令行不含 'app run'。" >&2
  echo "$cmdline" >&2
  exit 1
fi

kill "$pid" 2>/dev/null || true
for _ in $(seq 1 20); do
  kill -0 "$pid" 2>/dev/null || break
  sleep 0.3
done
kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
pkill -P "$pid" 2>/dev/null || true

rm -f "$PID_FILE"
echo "服务已停止。"
