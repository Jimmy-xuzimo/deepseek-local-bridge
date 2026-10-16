# 构建 Windows 便携版（onedir + zip）
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$buildVenv = Join-Path $root ".venv-build"
$buildPython = Join-Path $buildVenv "Scripts\python.exe"
if (-not (Test-Path $buildPython)) {
    Write-Host "正在创建打包环境 .venv-build ..."
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.12 -m venv $buildVenv 2>$null
    }
    if (-not (Test-Path $buildPython)) {
        if (Get-Command python -ErrorAction SilentlyContinue) {
            & python -m venv $buildVenv
        }
    }
    if (-not (Test-Path $buildPython)) {
        Write-Host "无法创建打包环境，请确认已安装 Python 3.10+。" -ForegroundColor Red
        exit 1
    }
}

Write-Host "安装打包依赖 ..."
& $buildPython -m pip install --upgrade pip --quiet --disable-pip-version-check
& $buildPython -m pip install -r (Join-Path $root "requirements-dev.txt") --quiet --disable-pip-version-check

Write-Host "开始打包（首次约 2-5 分钟）..."
& $buildPython -m PyInstaller --noconfirm --clean (Join-Path $root "scripts\deepseek_bridge.spec")

$distDir = Join-Path $root "dist\DeepSeekBridge"
Copy-Item (Join-Path $root "README.md") (Join-Path $distDir "README.md") -Force
Copy-Item (Join-Path $root "docs") $distDir -Recurse -Force

& (Join-Path $buildVenv "Scripts\python.exe") (Join-Path $root "scripts\make_archive.py")
Write-Host "便携包已生成在 $root\dist 下。" -ForegroundColor Green
