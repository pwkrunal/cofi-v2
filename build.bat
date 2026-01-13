@echo off
REM ############################################################################
REM Cofi Services - Docker Build Script (Windows)
REM Builds Docker images for cofi-mediator, cofi-service, and cofi-dashboard
REM Skips images that are already built
REM ############################################################################

setlocal enabledelayedexpansion

echo ========================================
echo   Cofi Services - Docker Build Script
echo ========================================
echo.

REM Function to check if image exists (using labels to track)
call :build_image "cofi-mediator" ".\cofi-mediator-service" "cofi-mediator:latest"
echo.

call :build_image "cofi-service" ".\cofi-service" "cofi-service:latest"
echo.

call :build_image "cofi-dashboard" ".\cofi-dashboard" "cofi-dashboard:latest"
echo.

REM Summary
echo ========================================
echo   Build Complete!
echo ========================================
echo.
echo Built images:
docker images | findstr /C:"cofi-mediator" /C:"cofi-service" /C:"cofi-dashboard" /C:"REPOSITORY"
echo.
echo Next step: Run 'launch.bat' to start all services
goto :eof

:build_image
    set name=%~1
    set context=%~2
    set tag=%~3

    echo [BUILD] Checking image: %tag%

    REM Check if image exists
    docker images -q %tag% 2>nul | findstr /r "." >nul
    if %errorlevel% equ 0 (
        echo [SKIP] Image %tag% already exists
        echo        Use 'docker rmi %tag%' to force rebuild
        exit /b 0
    )

    echo [BUILD] Building %name%...
    docker build -t %tag% %context%
    if %errorlevel% equ 0 (
        echo [SUCCESS] Built %tag%
    ) else (
        echo [FAILED] Failed to build %tag%
        exit /b 1
    )
    exit /b 0
