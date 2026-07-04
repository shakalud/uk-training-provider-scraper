@echo off
setlocal
cd /d "%~dp0"

echo Checking for Python...
where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python was not found.
    echo Install Python 3 from https://www.python.org/downloads/ and enable "Add Python to PATH".
    goto :error
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating the private Python environment...
    python -m venv .venv
    if errorlevel 1 goto :error
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :error

echo Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 goto :error

echo Installing required packages...
python -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo Installation complete. You can now run run_gui.bat
if not defined UKTS_NO_PAUSE pause
exit /b 0

:error
echo.
echo Installation failed. Review the message above, then try again.
if not defined UKTS_NO_PAUSE pause
exit /b 1
