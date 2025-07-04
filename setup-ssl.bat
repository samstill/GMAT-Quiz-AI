@echo off
REM SSL Certificate Setup Script for gmat.harshitpadha.me (Windows)

set DOMAIN=gmat.harshitpadha.me
set EMAIL=harshitpadha@gmail.com

echo 🔒 Setting up SSL certificates for %DOMAIN%
echo ==============================================

REM Create directories for SSL certificates
echo 📁 Creating SSL directories...
if not exist ssl mkdir ssl
if not exist ssl\certbot mkdir ssl\certbot
if not exist ssl\certbot\conf mkdir ssl\certbot\conf
if not exist ssl\certbot\www mkdir ssl\certbot\www

REM Check if certificates already exist
if exist ssl\certbot\conf\live\%DOMAIN% (
    echo ✅ SSL certificates already exist for %DOMAIN%
    echo 🔄 To renew certificates, run: docker-compose exec certbot certbot renew
    pause
    exit /b 0
)

REM Start containers without SSL first
echo 🚀 Starting containers for initial setup...
docker-compose up -d

REM Wait for nginx to be ready
echo ⏳ Waiting for nginx to be ready...
timeout /t 10 /nobreak >nul

REM Request SSL certificate
echo 🔒 Requesting SSL certificate for %DOMAIN%...
docker-compose run --rm certbot certbot certonly --webroot --webroot-path=/var/www/certbot --email %EMAIL% --agree-tos --no-eff-email -d %DOMAIN%

if errorlevel 1 (
    echo ❌ Failed to obtain SSL certificate
    echo 📋 Troubleshooting steps:
    echo    1. Ensure %DOMAIN% points to this server's IP
    echo    2. Check DNS propagation: nslookup %DOMAIN%
    echo    3. Verify port 80 is accessible from the internet
    echo    4. Check domain ownership
    pause
    exit /b 1
) else (
    echo ✅ SSL certificate obtained successfully!
    echo 🔄 Restarting nginx with SSL configuration...
    docker-compose restart frontend
    
    echo.
    echo 🎉 SSL setup completed!
    echo ========================
    echo 🌐 Your site is now available at:
    echo    https://%DOMAIN%
    echo    http://localhost (for local development)
    echo.
    echo 🔧 Certificate management:
    echo    • Auto-renewal is configured
    echo    • Certificates are stored in .\ssl\certbot\
    echo    • Manual renewal: docker-compose exec certbot certbot renew
)

pause
