# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：onedir，内置 Playwright 驱动，使用系统 Edge/Chrome。"""

import os

from PyInstaller.utils.hooks import collect_all

ROOT = os.path.dirname(os.path.abspath(SPECPATH))  # noqa: F821 - SPECPATH 由 PyInstaller 注入
ENTRY = os.path.join(ROOT, "run_bridge.py")
STATIC = os.path.join(ROOT, "app", "static")

datas, binaries, hiddenimports = collect_all("playwright")
datas += [(STATIC, "app/static")]
hiddenimports += [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "multipart",
    "playwright._impl._driver",
]

analysis = Analysis(
    [ENTRY],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    excludes=["tkinter", "PIL", "numpy", "pandas", "matplotlib", "pytest"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="DeepSeekBridge",
    console=True,
    disable_windowed_traceback=False,
)
collect = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    name="DeepSeekBridge",
)
