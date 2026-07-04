@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: The application is not installed yet.
    echo Double-click install.bat first.
    goto :error
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :error

python -c "import requests, bs4, openpyxl, yaml" >nul 2>nul
if errorlevel 1 (
    echo ERROR: Required packages are missing.
    echo Run install.bat again, then retry.
    goto :error
)

if defined UKTS_GUI_TEST (
    python gui.py --test
) else (
    start "" ".venv\Scripts\pythonw.exe" gui.pyw
)
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo The GUI could not be started. Run install.bat and try again.
if not defined UKTS_NO_PAUSE pause
exit /b 1
