"""把 dist/DeepSeekBridge 打成 zip（跨平台，CI 与本地脚本共用）。"""

from __future__ import annotations

import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
BUNDLE_DIR = DIST_DIR / "DeepSeekBridge"

PLATFORM_TAGS = {"win32": "win64", "darwin": "macos", "linux": "linux"}


def read_version() -> str:
    config = ROOT / "app" / "config.py"
    for line in config.read_text(encoding="utf-8").splitlines():
        if line.startswith("APP_VERSION"):
            return line.split('"')[1]
    return "0.0.0"


def main() -> int:
    if not BUNDLE_DIR.exists():
        print(f"未找到 {BUNDLE_DIR}，请先运行 PyInstaller 打包。", file=sys.stderr)
        return 1
    tag = PLATFORM_TAGS.get(sys.platform, sys.platform)
    base = DIST_DIR / f"DeepSeekBridge-{tag}-{read_version()}"
    if base.with_suffix(".zip").exists():
        base.with_suffix(".zip").unlink()
    archive = shutil.make_archive(
        str(base), "zip", root_dir=str(DIST_DIR), base_dir="DeepSeekBridge"
    )
    print("archive:", archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
