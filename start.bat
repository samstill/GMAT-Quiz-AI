@echo off
echo Starting GMAT Quiz Application...

REM Check if user_databases directory exists
if not exist user_databases (
    echo Warning: user_databases directory not found.
    echo Running user database setup first...
    call setup_user_dbs.bat
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Start the application
echo Starting FastAPI server...
uvicorn main:app --reload --port 8000
