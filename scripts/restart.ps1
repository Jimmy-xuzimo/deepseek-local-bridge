# 重启后台服务（用于让端口/局域网访问设置生效）
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

& (Join-Path $PSScriptRoot "stop.ps1")
Start-Sleep -Seconds 2

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "未找到 .venv，请先运行 scripts\setup.ps1。" -ForegroundColor Red
    exit 1
}

$logDir = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
Start-Process -FilePath $venvPython `
    -ArgumentList "-m", "app", "run", "--open-admin" `
    -WorkingDirectory $root -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir "service.out.log") `
    -RedirectStandardError (Join-Path $logDir "service.err.log")
Start-Sleep -Seconds 4

try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8317/healthz" -TimeoutSec 5
    Write-Host "服务已重启：$($health | ConvertTo-Json -Compress)" -ForegroundColor Green
} catch {
    Write-Host "服务可能未正常启动，请查看 logs\service.err.log。" -ForegroundColor Red
}
