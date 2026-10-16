#!/usr/bin/env bash
# 构建便携包（macOS / Linux；产物在 dist/ 下）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BUILD_VENV="$ROOT/.venv-build"
BUILD_PY="$BUILD_VENV/bin/python"
if [ ! -x "$BUILD_PY" ]; then
  echo "正在创建打包环境 .venv-build ..."
  python3 -m venv "$BUILD_VENV"
fi

echo "安装打包依赖 ..."
"$BUILD_PY" -m pip install --upgrade pip --quiet --disable-pip-version-check
"$BUILD_PY" -m pip install -r "$ROOT/requirements-dev.txt" --quiet --disable-pip-version-check

echo "开始打包（首次约 2-5 分钟）..."
"$BUILD_PY" -m PyInstaller --noconfirm --clean "$ROOT/scripts/deepseek_bridge.spec"

cp "$ROOT/README.md" "$ROOT/dist/DeepSeekBridge/README.md"
cp -r "$ROOT/docs" "$ROOT/dist/DeepSeekBridge/"

"$BUILD_PY" "$ROOT/scripts/make_archive.py"
echo "便携包已生成在 $ROOT/dist/ 下。"
