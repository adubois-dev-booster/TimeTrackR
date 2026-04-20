@echo off
cd /d "%~dp0"
call venv\Scripts\activate
pyinstaller TimeTrackR.spec --clean
echo.
echo Build termine : dist\TimeTrackR.exe
pause
