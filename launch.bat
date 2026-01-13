@echo off
REM ############################################################################
REM Cofi Services - Docker Launch Script (Windows)
REM Starts cofi-mediator, cofi-api, and cofi-dashboard services
REM Skips containers that are already running
REM ############################################################################

setlocal enabledelayedexpansion

echo ========================================
echo   Cofi Services - Docker Launch Script
echo ========================================
echo.

REM Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not running. Please start Docker Desktop and try again.
    exit /b 1
)

REM Check if docker-compose.yml exists
if not exist "docker-compose.yml" (
    echo [ERROR] docker-compose.yml not found in current directory
    exit /b 1
)

REM Check if images are built
echo Checking Docker images...
set missing_images=0

docker images -q cofi-mediator:latest 2>nul | findstr /r "." >nul
if %errorlevel% neq 0 (
    echo [MISSING] Image cofi-mediator:latest not found
    set missing_images=1
)

docker images -q cofi-service:latest 2>nul | findstr /r "." >nul
if %errorlevel% neq 0 (
    echo [MISSING] Image cofi-service:latest not found
    set missing_images=1
)

docker images -q cofi-dashboard:latest 2>nul | findstr /r "." >nul
if %errorlevel% neq 0 (
    echo [MISSING] Image cofi-dashboard:latest not found
    set missing_images=1
)

if !missing_images! equ 1 (
    echo.
    echo [ACTION REQUIRED] Some images are missing. Run 'build.bat' first.
    exit /b 1
)

echo [OK] All images found
echo.

REM Create network if it doesn't exist
echo Checking Docker network...
docker network inspect auditnex-network >nul 2>&1
if %errorlevel% neq 0 (
    echo [CREATE] Creating network auditnex-network...
    docker network create auditnex-network
    echo [SUCCESS] Network created
) else (
    echo [OK] Network auditnex-network exists
)
echo.

REM Start services
echo Starting services...
echo.

call :start_service "cofi-mediator" "cofi-mediator-service"
echo.

call :start_service "cofi-api" "cofi-api"
echo.

call :start_service "cofi-dashboard" "cofi-dashboard"
echo.

REM Check if batch service exists
docker ps -a --filter "name=cofi-service" --format "{{.Names}}" | findstr /x "cofi-service" >nul
if %errorlevel% equ 0 (
    docker ps --filter "name=cofi-service" --filter "status=running" --format "{{.Names}}" | findstr /x "cofi-service" >nul
    if %errorlevel% equ 0 (
        echo [INFO] Batch processing service (cofi-service) is running
    ) else (
        echo [INFO] Batch processing service (cofi-service) exists but stopped
        echo        This service runs batch jobs on-demand
        echo        Start manually: docker start cofi-service
    )
) else (
    echo [INFO] Batch processing service (cofi-service) will be created on first run
    echo        Start manually: docker-compose up -d cofi-service
)
echo.

REM Wait for services to be healthy
echo Waiting for services to be ready...
timeout /t 3 /nobreak >nul

REM Check service status
echo ========================================
echo   Services Status
echo ========================================
echo.

docker ps --filter "name=cofi-mediator-service" --filter "name=cofi-api" --filter "name=cofi-dashboard" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo.
echo ========================================
echo   Launch Complete!
echo ========================================
echo.
echo Service URLs:
echo   Mediator API:   http://localhost:5065
echo   Cofi API:       http://localhost:5064
echo   Dashboard:      http://localhost:5066
echo.
echo Commands:
echo   View logs:        docker-compose logs -f [service-name]
echo   Stop all:         docker-compose down
echo   Restart service:  docker-compose restart [service-name]
echo   Run batch job:    docker-compose up cofi-service
echo.
goto :eof

:start_service
    set service_name=%~1
    set container_name=%~2

    echo [CHECK] Service: %service_name% (%container_name%)

    REM Check if already running
    docker ps --filter "name=%container_name%" --filter "status=running" --format "{{.Names}}" | findstr /x "%container_name%" >nul
    if %errorlevel% equ 0 (
        echo [SKIP] Container %container_name% is already running
        exit /b 0
    )

    REM Check if container exists but stopped
    docker ps -a --filter "name=%container_name%" --format "{{.Names}}" | findstr /x "%container_name%" >nul
    if %errorlevel% equ 0 (
        echo [START] Starting existing container %container_name%...
        docker start %container_name%
        echo [SUCCESS] Started %container_name%
        exit /b 0
    )

    REM Container doesn't exist, use docker-compose
    echo [CREATE] Creating and starting %container_name%...
    docker-compose up -d %service_name%
    echo [SUCCESS] Created and started %container_name%
    exit /b 0
