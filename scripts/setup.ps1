# 创建虚拟环境并安装依赖
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Test-PythonExe([string]$exe, [string[]]$preArgs) {
    try {
        $out = & $exe @preArgs -c "import sys; print(1 if sys.version_info >= (3,10) else 0)" 2>$null
        return ($LASTEXITCODE -eq 0 -and "$out".Trim() -eq "1")
    } catch {
        return $false
    }
}

$pyExe = $null
$pyPre = @()
if ((Get-Command py -ErrorAction SilentlyContinue) -and (Test-PythonExe "py" @("-3.12"))) {
    $pyExe = "py"; $pyPre = @("-3.12")
} elseif ((Get-Command py -ErrorAction SilentlyContinue) -and (Test-PythonExe "py" @("-3"))) {
    $pyExe = "py"; $pyPre = @("-3")
} elseif ((Get-Command python -ErrorAction SilentlyContinue) -and (Test-PythonExe "python" @())) {
    $pyExe = "python"; $pyPre = @()
}

if (-not $pyExe) {
    Write-Host "未找到 Python 3.10 及以上版本。请先安装 Python 3.12（安装时勾选 Add python.exe to PATH）。" -ForegroundColor Red
    exit 1
}

$venvPath = Join-Path $root ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "正在创建虚拟环境 .venv ..."
    & $pyExe @pyPre -m venv $venvPath
    if (-not (Test-Path $venvPython)) {
        Write-Host "虚拟环境创建失败。" -ForegroundColor Red
        exit 1
    }
}

Write-Host "正在安装依赖（首次约 1-2 分钟）..."
& $venvPython -m pip install --upgrade pip --quiet --disable-pip-version-check
& $venvPython -m pip install -r (Join-Path $root "requirements.txt") --quiet --disable-pip-version-check

Write-Host "环境准备完成。" -ForegroundColor Green
