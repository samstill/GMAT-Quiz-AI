@echo off
REM === GMAT Quiz Project Setup ===
echo.
echo === GMAT Quiz Project Setup ===

REM 1. Check for Python
echo.
echo Checking for Python installation...
where python >nul 2>nul
if errorlevel 1 (
    echo Python not found. Installing Python 3.11 via winget...
    winget install -e --id Python.Python.3.11
    echo.
    echo Please restart your terminal after Python installation, then re-run this script.
    pause
    exit /b 1
) else (
    for /f "tokens=*" %%v in ('python --version 2^>^&1') do set "PYVER=%%v"
    echo Found %PYVER%
)

REM 2. Create virtual environment
echo.
echo Creating a virtual environment (venv)...
if not exist venv (
    python -m venv venv
    echo Virtual environment created.
) else (
    echo Virtual environment already exists.
)

REM 3. Activate virtual environment
echo.
echo Activating virtual environment...
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    echo Virtual environment activated.
) else (
    echo Could not find venv activation script. Exiting.
    pause
    exit /b 1
)

REM 4. Install dependencies
echo.
echo Installing Python dependencies (FastAPI, Uvicorn, SQLAlchemy, etc.)...
REM Overwrite requirements.txt
(
    echo fastapi
    echo uvicorn[standard]
    echo sqlalchemy
    echo pydantic
    echo python-multipart
    echo aiofiles
) > requirements.txt

pip install --upgrade pip
pip install -r requirements.txt

echo.
echo Dependencies installed.

REM 5. Prompt to run backend
echo.
echo === Backend Setup Complete! ===
echo To start the FastAPI backend, run:
echo    call venv\Scripts\activate.bat
echo    uvicorn main:app --reload
echo.
echo The API will be available at http://127.0.0.1:8000
echo.

REM 6. Prompt to open frontend
echo To use the frontend, just open index.html in your browser.
echo.
echo You can now manage quizzes, upload questions, and take quizzes with a modern UI!
echo.
echo === Setup Complete! ===

REM 7. Ensure PowerShell execution policy is set to Bypass for CurrentUser
echo.
echo Setting PowerShell execution policy to Bypass for CurrentUser...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Set-ExecutionPolicy -Scope CurrentUser Bypass -Force"

pause
