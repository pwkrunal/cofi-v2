@echo off
REM ############################################################################
REM Cofi Services - Docker Stop Script (Windows)
REM Stops all running Cofi services
REM ############################################################################

echo ========================================
echo   Cofi Services - Docker Stop Script
echo ========================================
echo.

REM Stop services using docker-compose
echo Stopping all Cofi services...
docker-compose down

echo.
echo ========================================
echo   All services stopped
echo ========================================
echo.
echo To start again: Run 'launch.bat'
echo To remove images: Run 'docker-compose down --rmi all'
