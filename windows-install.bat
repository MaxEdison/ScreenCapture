@echo off
cd /d "%~dp0"
echo Installing requirements...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo GPU capture module could not be installed - installing the standard set instead.
    python -m pip install mss aiohttp pillow qrcode
)
echo.
echo All done. Run windows-run.bat to start.
pause
