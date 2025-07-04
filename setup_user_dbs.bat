@echo off
REM Setup User Databases Script
echo Setting up user database management system for GMAT Quiz...

echo Step 1: Making sure the authentication database is properly migrated...
python migrate_db.py

echo Step 2: Creating user_databases directory if needed...
IF NOT EXIST user_databases mkdir user_databases

echo Step 3: Running data migration to user databases...
python migrate_user_db.py

echo Setup complete!
echo.
echo Now you can run start.bat to start the application with the new multi-database system.
echo.
pause
