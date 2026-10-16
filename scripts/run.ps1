# 启动服务（前台运行，Ctrl+C 停止）
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    & (Join-Path $PSScriptRoot "setup.ps1")
}

& $venvPython -m app run --open-admin @args
