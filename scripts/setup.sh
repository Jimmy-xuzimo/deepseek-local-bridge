#!/usr/bin/env bash
# 创建虚拟环境并安装依赖（macOS / Linux）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

find_python() {
  for candidate in python3.13 python3.12 python3.11 python3.10 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
        echo "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

PY="$(find_python || true)"
if [ -z "$PY" ]; then
  echo "未找到 Python 3.10 及以上版本，请先安装（https://www.python.org/downloads/）。" >&2
  exit 1
fi

VENV="$ROOT/.venv"
if [ ! -x "$VENV/bin/python" ]; then
  echo "正在创建虚拟环境 .venv ..."
  "$PY" -m venv "$VENV"
fi

echo "正在安装依赖（首次约 1-2 分钟）..."
"$VENV/bin/python" -m pip install --upgrade pip --quiet --disable-pip-version-check
"$VENV/bin/python" -m pip install -r "$ROOT/requirements.txt" --quiet --disable-pip-version-check

echo "环境准备完成。"
