@echo off
rem Kotoba Transcriber setup.
rem Usage:  setup.bat            (asks which PyTorch build to install)
rem         setup.bat cu126      (skip the prompt: cu126 / cu128 / cpu)
setlocal EnableDelayedExpansion

rem Keep the virtual environment out of any synced folder (OneDrive, Google
rem Drive, Dropbox). PyTorch alone is several GB and syncing it is painful.
set "VENV_DIR=%USERPROFILE%\.venvs\kotoba-transcriber"
set "BACKEND=%~1"

echo === Kotoba Transcriber setup ===
echo venv: %VENV_DIR%
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] python was not found on PATH.
    echo         Install Python 3.11 or newer from https://www.python.org/downloads/
    goto :fail
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
    echo [ERROR] Python 3.11 or newer is required.
    python --version
    goto :fail
)

if not "%BACKEND%"=="" goto :resolve

where nvidia-smi >nul 2>&1
if errorlevel 1 (
    echo No NVIDIA GPU detected - installing the CPU build.
    echo Transcription will work but is roughly 10x slower.
    set "BACKEND=cpu"
    goto :resolve
)

echo Detected GPU:
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
echo.
echo Which PyTorch build should be installed?
echo   1) CUDA 12.6  - recommended for most NVIDIA GPUs
echo   2) CUDA 12.8  - newer GPUs and drivers
echo   3) CPU only   - no GPU acceleration
set "CHOICE="
set /p "CHOICE=Enter 1, 2 or 3 [1]: "
if "!CHOICE!"=="2" set "BACKEND=cu128"
if "!CHOICE!"=="3" set "BACKEND=cpu"
if "!BACKEND!"=="" set "BACKEND=cu126"

:resolve
set "TORCH_INDEX=https://download.pytorch.org/whl/%BACKEND%"
echo.
echo PyTorch build: %BACKEND%
echo Index:         %TORCH_INDEX%
echo.

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 goto :fail
)
set "VPY=%VENV_DIR%\Scripts\python.exe"

echo Upgrading pip...
"%VPY%" -m pip install --upgrade pip
if errorlevel 1 goto :fail

rem torchaudio must come from the same index so its build matches torch.
echo Installing PyTorch and torchaudio...
"%VPY%" -m pip install torch torchaudio --index-url %TORCH_INDEX%
if errorlevel 1 goto :fail

echo Installing application dependencies...
"%VPY%" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 goto :fail

echo.
echo Checking the installation...
"%VPY%" -c "import torch; print('torch', torch.__version__); print('cuda available:', torch.cuda.is_available()); print('device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU only')"

echo.
echo === Setup finished. Run run.bat to start the app. ===
echo Models are downloaded on first use (about 1.5 GB for the default model).
pause
exit /b 0

:fail
echo.
echo [ERROR] Setup failed. See the messages above.
pause
exit /b 1
