@echo off
:: Run this once to compile obs_controller.py into a single .exe
:: Requirements: pip install pyinstaller keyboard

pip install pyinstaller keyboard --quiet

pyinstaller ^
  --onefile ^
  --noconsole ^
  --name "OBS Controller" ^
  obs_controller.py

echo.
echo Done. Find OBS Controller.exe in the dist\ folder.
pause
