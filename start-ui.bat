@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creating Python environment...
  py -3.10 -m venv .venv || goto :error
)
.venv\Scripts\python.exe -m pip install --upgrade pip || goto :error
.venv\Scripts\python.exe -m pip install -r requirements.txt || goto :error
.venv\Scripts\python.exe -c "import torch, torchaudio" >nul 2>nul
if errorlevel 1 (
  echo Installing the CPU runtime required for voice cloning. This is a one-time download.
  .venv\Scripts\python.exe -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu || goto :error
)
start "AIRI Vietnamese Speech" .venv\Scripts\pythonw.exe launcher.py
echo AIRI Vietnamese Speech is starting in its own window.
timeout /t 2 /nobreak >nul
goto :eof

:error
echo.
echo Setup failed. Install Python 3.10 64-bit, then run this file again.
pause
