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

VERSION="$(sed -n 's/^APP_VERSION = "\(.*\)"/\1/p' "$ROOT/app/config.py")"
OS_NAME="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"
ZIP_NAME="DeepSeekBridge-${OS_NAME}-${ARCH}-${VERSION}.zip"

cp "$ROOT/README.md" "$ROOT/dist/DeepSeekBridge/README.md"
cp -r "$ROOT/docs" "$ROOT/dist/DeepSeekBridge/"

(cd "$ROOT/dist/DeepSeekBridge" && zip -qr "../$ZIP_NAME" .)
echo "已生成便携包：$ROOT/dist/$ZIP_NAME"
