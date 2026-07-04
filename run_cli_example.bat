@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Double-click install.bat first.
    if not defined UKTS_NO_PAUSE pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"
python run.py --scraper citb --limit 5 --no-email-finder --output-name cli_test
if errorlevel 1 (
    echo The test scrape failed.
    if not defined UKTS_NO_PAUSE pause
    exit /b 1
)

echo Test complete. Open the outputs folder to view the files.
exit /b 0
