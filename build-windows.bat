@echo off
setlocal
cd /d "%~dp0"
set "AIRI_DATA_BACKUP=%TEMP%\airi-speech-data-%RANDOM%-%RANDOM%"
if exist "dist\AIRI Vietnamese Speech\data" (
  xcopy "dist\AIRI Vietnamese Speech\data" "%AIRI_DATA_BACKUP%\" /e /i /h /y >nul || exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Run start-ui.bat once before building.
  exit /b 1
)
.venv\Scripts\python.exe -m pip install -r requirements-build.txt || exit /b 1
.venv\Scripts\python.exe -c "import torch, torchaudio" >nul 2>nul
if errorlevel 1 (
  .venv\Scripts\python.exe -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu || exit /b 1
)
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean "AIRI Vietnamese Speech.spec"
if exist "%AIRI_DATA_BACKUP%" (
  xcopy "%AIRI_DATA_BACKUP%" "dist\AIRI Vietnamese Speech\data\" /e /i /h /y >nul || exit /b 1
  echo Voice data backup kept at: %AIRI_DATA_BACKUP%
)
echo.
echo Built: dist\AIRI Vietnamese Speech\AIRI Vietnamese Speech.exe
pause
