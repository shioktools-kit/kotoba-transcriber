@echo off
rem Same as run.bat but keeps a console window so tracebacks stay visible.
setlocal
set "VENV_DIR=%USERPROFILE%\.venvs\kotoba-transcriber"
set "VPY=%VENV_DIR%\Scripts\python.exe"

if not exist "%VPY%" (
    echo [ERROR] Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)

"%VPY%" "%~dp0main.py"
pause
