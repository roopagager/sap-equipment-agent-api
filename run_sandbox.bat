@echo off
REM Run the SAP Equipment Agent API against the real SAP sandbox.
REM Needs Python 3.12+ and a free API key from api.sap.com (API_EQUIPMENT > Show API Key).
cd /d "%~dp0"

if not exist .venv (
  echo Creating virtual environment...
  python -m venv .venv || goto :nopython
)
call .venv\Scripts\activate.bat
python -m pip install -q -r requirements.txt

if "%SAP_API_KEY%"=="" set /p SAP_API_KEY=Paste your SAP API key and press Enter: 
if "%SAP_API_KEY%"=="" (echo No API key given. & pause & exit /b 1)
set SAP_MODE=sandbox

echo.
echo Starting on http://localhost:8000  -  press Ctrl+C to stop.
echo Opening equipment 10001883 (cooling water pump) in your browser...
start "" cmd /c "timeout /t 4 >nul & start http://localhost:8000/equipment/10001883"
python -m uvicorn app.main:app --port 8000
goto :eof

:nopython
echo Python was not found. Install Python 3.12+ from python.org and tick "Add to PATH".
pause
