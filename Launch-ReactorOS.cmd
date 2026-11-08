@echo off
setlocal
cd /d "%~dp0"
start "ReactorOS" /d "%~dp0" pythonw.exe "%~dp0reactor_os.py" %*
