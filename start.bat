@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo 正在启动 DeepSeek Local Bridge ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run.ps1" %*
if errorlevel 1 (
  echo.
  echo 启动失败，请查看上面的错误信息。
  pause
)
