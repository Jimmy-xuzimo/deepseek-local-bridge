# 停止后台运行的服务（含浏览器子进程）
$ErrorActionPreference = "Stop"

$dataDir = Join-Path $env:LOCALAPPDATA "DeepSeekBridge"
if ($env:DSB_DATA_DIR) { $dataDir = $env:DSB_DATA_DIR }
$pidFile = Join-Path $dataDir "service.pid"

if (-not (Test-Path -LiteralPath $pidFile)) {
    Write-Host "未找到 service.pid，服务可能未在后台运行。"
    exit 0
}

$servicePid = 0
if (-not [int]::TryParse((Get-Content -LiteralPath $pidFile -Raw).Trim(), [ref]$servicePid)) {
    Write-Host "pid 文件内容无效：$pidFile"
    exit 1
}

$proc = Get-CimInstance Win32_Process -Filter "ProcessId = $servicePid" -ErrorAction SilentlyContinue
if (-not $proc) {
    Write-Host "进程 $servicePid 不存在，清理 pid 文件。"
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    exit 0
}

if ($proc.CommandLine -notmatch "app run") {
    Write-Host "拒绝结束：进程 $servicePid 的命令行不含 'app run'。"
    Write-Host $proc.CommandLine
    exit 1
}

taskkill /PID $servicePid /T /F | Out-Null
Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
Write-Host "服务已停止（含浏览器子进程）。"
