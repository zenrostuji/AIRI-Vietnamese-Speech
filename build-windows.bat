@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run start-ui.bat once before building.
  exit /b 1
)
.venv\Scripts\python.exe -m pip install -r requirements.txt || exit /b 1
.venv\Scripts\python.exe -c "import torch, torchaudio" >nul 2>nul
if errorlevel 1 (
  .venv\Scripts\python.exe -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu || exit /b 1
)
.venv\Scripts\pyinstaller.exe --noconfirm --clean --onedir --windowed --name "AIRI Vietnamese Speech" --add-data "ui;ui" --collect-all vieneu --collect-all faster_whisper --collect-all ctranslate2 --collect-all webview --collect-all torch --collect-all torchaudio launcher.py
echo.
echo Built: dist\AIRI Vietnamese Speech\AIRI Vietnamese Speech.exe
pause
