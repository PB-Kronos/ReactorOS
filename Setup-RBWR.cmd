@echo off
setlocal
cd /d "%~dp0"
if not exist ".runtime-temp" mkdir ".runtime-temp"
set "TEMP=%CD%\.runtime-temp"
set "TMP=%TEMP%"
python -m pip install --no-cache-dir --target ".desktop-runtime" "pywebview==6.1"
if errorlevel 1 pause
