@echo off
setlocal
set "VENV_DIR=%USERPROFILE%\.venvs\kotoba-transcriber"
set "VPY=%VENV_DIR%\Scripts\pythonw.exe"

if not exist "%VPY%" (
    echo [ERROR] Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)

start "" "%VPY%" "%~dp0main.py"
exit /b 0
