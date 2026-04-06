@echo off
echo Closing any running instance of OBS Controller...
taskkill /f /im "OBS Controller.exe" 2>nul
timeout /t 1 /nobreak >nul

echo Installing dependencies...
pip install pyinstaller --quiet

echo Building...
pyinstaller --onefile --noconsole --name "OBS Controller" obs_controller.py

echo.
echo Done. Find OBS Controller.exe in the dist\ folder.
pause
