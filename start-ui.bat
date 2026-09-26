@echo off
setlocal
cd /d "%~dp0"

rem Fast path: validate local packages, then launch without contacting the network.
if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python.exe -c "import fastapi, faster_whisper, numpy, soundfile, torch, torchaudio, uvicorn, vieneu, webview" >nul 2>nul
  if not errorlevel 1 goto :ready
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating Python environment...
  if exist ".python\cpython-3.10.20-windows-x86_64-none\python.exe" (
    ".python\cpython-3.10.20-windows-x86_64-none\python.exe" -m venv .venv || goto :python_error
  ) else (
    py -3.10 -m venv .venv || goto :python_error
  )
)
.venv\Scripts\python.exe -c "import sys; assert sys.version_info[:2] == (3, 10)" >nul 2>nul || goto :venv_error
.venv\Scripts\python.exe -m pip install --upgrade pip || goto :error
.venv\Scripts\python.exe -m pip install -r requirements.txt || goto :error
.venv\Scripts\python.exe -c "import torch, torchaudio" >nul 2>nul
if errorlevel 1 (
  echo Installing the CPU runtime required for voice cloning. This is a one-time download.
  .venv\Scripts\python.exe -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu || goto :error
)
type nul > ".venv\.airi-ready"
:ready
start "AIRI Vietnamese Speech" ".venv\Scripts\pythonw.exe" launcher.py
echo AIRI Vietnamese Speech is starting in its own window.
timeout /t 2 /nobreak >nul
goto :eof

:error
echo.
echo Setup failed. Check the internet connection, then run this file again.
pause
exit /b 1

:python_error
echo.
echo Python 3.10 64-bit is required for source mode.
echo Keep the included .python folder, or install Python 3.10 from python.org.
pause
exit /b 1

:venv_error
echo.
echo The .venv folder was copied from another computer or uses the wrong Python.
echo Rename or remove only the .venv folder, then run this file again.
pause
exit /b 1
