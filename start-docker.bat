@echo off
REM GMAT Quiz Docker Setup Script for Windows
REM This script will build and start the entire application with Docker

echo 🚀 Starting GMAT Quiz Application with Docker...
echo =================================================

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker is not installed. Please install Docker Desktop first.
    echo    Visit: https://docs.docker.com/desktop/windows/
    pause
    exit /b 1
)

REM Check if Docker Compose is available
docker-compose --version >nul 2>&1
if errorlevel 1 (
    docker compose version >nul 2>&1
    if errorlevel 1 (
        echo ❌ Docker Compose is not available. Please install Docker Compose.
        pause
        exit /b 1
    )
)

REM Create .env file if it doesn't exist
if not exist .env (
    echo 📝 Creating .env file from .env.example...
    copy .env.example .env >nul
    echo ✅ .env file created. You can edit it later to add your Google API key.
)

REM Create necessary directories if they don't exist
echo 📁 Creating necessary directories...
if not exist user_databases mkdir user_databases
if not exist JSON mkdir JSON
if not exist images mkdir images

REM Stop any existing containers
echo 🛑 Stopping any existing containers...
docker-compose down --remove-orphans >nul 2>&1

REM Build and start the application
echo 🔨 Building and starting the application...
docker-compose up --build -d

REM Wait for the application to be ready
echo ⏳ Waiting for the application to start...
timeout /t 10 /nobreak >nul

REM Check if the application is running
docker-compose ps | findstr "Up" >nul
if errorlevel 1 (
    echo ❌ Failed to start the application. Check logs with: docker-compose logs
    pause
    exit /b 1
) else (
    echo.
    echo ✅ SUCCESS! GMAT Quiz Application is now running!
    echo =================================================
    echo 🌐 Frontend (Web App): http://localhost
    echo 🔧 Backend API: http://localhost:8000
    echo 📚 API Documentation: http://localhost:8000/docs
    echo.
    echo � SSL Setup (for production domain):
    echo    • Run: setup-ssl.bat
    echo    • After SSL: https://gmat.harshitpadha.me
    echo.
    echo �📋 Useful commands:
    echo    • View logs: docker-compose logs -f
    echo    • Stop app: docker-compose down
    echo    • Restart: docker-compose restart
    echo.
    echo 🔧 To add your Google API key:
    echo    1. Edit the .env file
    echo    2. Set GOOGLE_API_KEY=your_actual_key
    echo    3. Restart with: docker-compose restart
    echo.
)

pause
