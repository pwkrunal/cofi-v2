# Cofi Services - Docker Deployment Scripts

## Overview

This directory contains unified deployment scripts for all Cofi services:
- **cofi-mediator** - Manages Docker containers on GPU machines (Port 5065)
- **cofi-api** - Handles file uploads and batch management (Port 5064)
- **cofi-dashboard** - Real-time monitoring UI (Port 5066)
- **cofi-service** - Batch processing pipeline (on-demand)

---

## Quick Start

### For Linux/Mac/WSL (Bash)

```bash
# 1. Build all Docker images
./build.sh

# 2. Start all services
./launch.sh

# 3. Stop all services
./stop.sh
```

### For Windows (Command Prompt)

```cmd
# 1. Build all Docker images
build.bat

# 2. Start all services
launch.bat

# 3. Stop all services
stop.bat
```

---

## Script Features

### ✅ Smart Skip Logic

All scripts intelligently skip operations that are already complete:

**build.sh / build.bat**
- ✅ Skips building images that already exist
- ✅ Shows which images are already built
- ✅ Only builds missing images

**launch.sh / launch.bat**
- ✅ Skips starting containers that are already running
- ✅ Restarts stopped containers instead of recreating
- ✅ Creates containers only if they don't exist
- ✅ Creates Docker network if missing

---

## Detailed Script Usage

### 1. Build Script

**Purpose:** Build Docker images for all services

**Files:**
- `build.sh` - Linux/Mac/WSL version
- `build.bat` - Windows version

**What it does:**
1. Checks if each Docker image already exists
2. Skips images that are already built
3. Builds only missing images
4. Shows summary of all built images

**Output:**
```
========================================
  Cofi Services - Docker Build Script
========================================

[BUILD] Checking image: cofi-mediator:latest
[SKIP] Image cofi-mediator:latest already exists
       Use 'docker rmi cofi-mediator:latest' to force rebuild

[BUILD] Checking image: cofi-service:latest
[BUILD] Building cofi-service...
[SUCCESS] Built cofi-service:latest

[BUILD] Checking image: cofi-dashboard:latest
[BUILD] Building cofi-dashboard...
[SUCCESS] Built cofi-dashboard:latest

========================================
  Build Complete!
========================================
```

**Force Rebuild:**
```bash
# Remove specific image and rebuild
docker rmi cofi-mediator:latest
./build.sh

# Remove all images and rebuild
docker rmi cofi-mediator:latest cofi-service:latest cofi-dashboard:latest
./build.sh

# Or use docker-compose
docker-compose build --no-cache
```

---

### 2. Launch Script

**Purpose:** Start all Cofi services

**Files:**
- `launch.sh` - Linux/Mac/WSL version
- `launch.bat` - Windows version

**What it does:**
1. Checks if Docker is running
2. Verifies all images are built (fails if missing)
3. Creates `auditnex-network` if it doesn't exist
4. Starts each service with smart logic:
   - If container is running → Skip
   - If container exists but stopped → Start it
   - If container doesn't exist → Create and start
5. Shows service status and URLs

**Output:**
```
========================================
  Cofi Services - Docker Launch Script
========================================

Checking Docker images...
[OK] All images found

Checking Docker network...
[OK] Network auditnex-network exists

Starting services...

[CHECK] Service: cofi-mediator (cofi-mediator-service)
[SKIP] Container cofi-mediator-service is already running

[CHECK] Service: cofi-api (cofi-api)
[START] Starting existing container cofi-api...
[SUCCESS] Started cofi-api

[CHECK] Service: cofi-dashboard (cofi-dashboard)
[CREATE] Creating and starting cofi-dashboard...
[SUCCESS] Created and started cofi-dashboard

[INFO] Batch processing service (cofi-service) will be created on first run
       Start manually: docker-compose up -d cofi-service

========================================
  Services Status
========================================

NAMES                    STATUS              PORTS
cofi-mediator-service    Up 2 minutes        0.0.0.0:5065->5065/tcp
cofi-api                 Up 10 seconds       0.0.0.0:5064->5064/tcp
cofi-dashboard           Up 3 seconds        0.0.0.0:5066->5066/tcp

========================================
  Launch Complete!
========================================

Service URLs:
  Mediator API:   http://localhost:5065
  Cofi API:       http://localhost:5064
  Dashboard:      http://localhost:5066
```

---

### 3. Stop Script

**Purpose:** Stop all running services

**Files:**
- `stop.sh` - Linux/Mac/WSL version
- `stop.bat` - Windows version

**What it does:**
1. Stops all containers defined in docker-compose.yml
2. Removes containers (but keeps images and volumes)
3. Keeps Docker network for next run

**Output:**
```
========================================
  Cofi Services - Docker Stop Script
========================================

Stopping all Cofi services...
[+] Running 4/4
 ✔ Container cofi-dashboard          Removed
 ✔ Container cofi-api                Removed
 ✔ Container cofi-mediator-service   Removed
 ✔ Network auditnex-network          Removed

========================================
  All services stopped
========================================

To start again: Run './launch.sh'
To remove images: Run 'docker-compose down --rmi all'
```

---

## Docker Compose Configuration

The unified `docker-compose.yml` at the root level manages all services:

```yaml
services:
  cofi-mediator:      # Port 5065
  cofi-service:       # Batch processing (on-demand)
  cofi-api:           # Port 5064
  cofi-dashboard:     # Port 5066

networks:
  auditnex-network:   # Shared network
```

**Service Dependencies:**
- `cofi-service` and `cofi-api` depend on `cofi-mediator`
- All services use the same `auditnex-network`

---

## Common Workflows

### First Time Setup

```bash
# 1. Build all images
./build.sh

# 2. Configure environment files
cp cofi-service/.env.example cofi-service/.env
cp cofi-dashboard/.env.example cofi-dashboard/.env
# Edit .env files with your settings

# 3. Start services
./launch.sh

# 4. Verify services are running
docker ps
```

### Daily Usage

```bash
# Start services (skips already running containers)
./launch.sh

# View logs
docker-compose logs -f cofi-dashboard

# Run batch processing
docker-compose up cofi-service

# Stop services when done
./stop.sh
```

### Development Workflow

```bash
# Start services in development mode
./launch.sh

# Make code changes in cofi-dashboard/src/
# Changes are hot-reloaded automatically (volumes mounted)

# Restart specific service to apply changes
docker-compose restart cofi-dashboard

# View real-time logs
docker-compose logs -f cofi-dashboard
```

### Troubleshooting

```bash
# Check if images exist
docker images | grep cofi

# Check if containers are running
docker ps -a | grep cofi

# View service logs
docker-compose logs cofi-dashboard
docker-compose logs cofi-api
docker-compose logs cofi-mediator

# Restart a specific service
docker-compose restart cofi-api

# Rebuild and restart
docker-compose up -d --build cofi-dashboard

# Force complete rebuild
docker-compose down --rmi all
./build.sh
./launch.sh
```

---

## Environment Variables

### Cofi Service (.env file in cofi-service/)

```env
# GPU Configuration
GPU_MACHINES=192.168.1.10,192.168.1.11
MEDIATOR_PORT=5065

# Batch Configuration
CLIENT_VOLUME=/client_volume
BATCH_DATE=15-12-2024
CURRENT_BATCH=1

# Event Logging (optimized for 10,000+ files)
LOG_FILE_START_EVENTS=false
PROGRESS_UPDATE_INTERVAL=100

# MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=password
MYSQL_DATABASE=testDb
```

### Cofi Dashboard (.env file in cofi-dashboard/)

```env
# MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=password
MYSQL_DATABASE=testDb

# SSE Configuration
SSE_POLL_INTERVAL=5
```

### Root Level (.env file at root - optional)

```env
# Shared settings for docker-compose.yml
STORAGE_PATH=./audio_files
CLIENT_VOLUME=./data
MYSQL_HOST=localhost
MYSQL_PASSWORD=your_secure_password
```

---

## Service Ports

| Service | Port | Purpose |
|---------|------|---------|
| cofi-mediator | 5065 | Mediator API (container management) |
| cofi-api | 5064 | File upload and batch management API |
| cofi-dashboard | 5066 | Real-time monitoring web UI |

**Make sure these ports are not in use:**
```bash
# Check if ports are available
netstat -an | grep -E "(5064|5065|5066)"

# Or use lsof (Linux/Mac)
lsof -i :5064
lsof -i :5065
lsof -i :5066
```

---

## Docker Network

All services use a shared Docker bridge network: `auditnex-network`

**Network is automatically created by launch scripts**

Manual network management:
```bash
# Create network manually
docker network create auditnex-network

# Inspect network
docker network inspect auditnex-network

# Remove network (after stopping all services)
docker network rm auditnex-network
```

---

## Advanced Usage

### Running Individual Services

```bash
# Start only mediator
docker-compose up -d cofi-mediator

# Start only dashboard
docker-compose up -d cofi-dashboard

# Start API and dashboard (mediator starts automatically as dependency)
docker-compose up -d cofi-api cofi-dashboard
```

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f cofi-dashboard

# Last 100 lines
docker-compose logs --tail=100 cofi-api

# Since specific time
docker-compose logs --since 2024-12-15T10:00:00 cofi-service
```

### Executing Commands Inside Containers

```bash
# Access container shell
docker exec -it cofi-dashboard /bin/bash

# Run Python command
docker exec -it cofi-dashboard python -c "print('Hello')"

# Check MySQL connection from dashboard
docker exec -it cofi-dashboard python -c "from src.database import get_database; print(get_database())"
```

### Resource Management

```bash
# Check resource usage
docker stats cofi-mediator-service cofi-api cofi-dashboard

# Limit memory for a service (in docker-compose.yml)
deploy:
  resources:
    limits:
      memory: 512M
```

---

## Cleanup Commands

```bash
# Stop all services
./stop.sh

# Remove stopped containers
docker-compose down

# Remove containers and images
docker-compose down --rmi all

# Remove containers, images, and volumes
docker-compose down --rmi all -v

# Remove everything including network
docker-compose down --rmi all -v --remove-orphans

# Prune unused Docker resources (be careful!)
docker system prune -a
```

---

## Troubleshooting Guide

### Issue: "Images not found"

```bash
# Solution: Build images first
./build.sh
```

### Issue: "Port already in use"

```bash
# Solution: Find and stop the process using the port
# Linux/Mac
sudo lsof -i :5066
sudo kill -9 <PID>

# Windows
netstat -ano | findstr :5066
taskkill /PID <PID> /F
```

### Issue: "Docker daemon not running"

```bash
# Solution: Start Docker Desktop (Windows/Mac)
# Or start Docker service (Linux)
sudo systemctl start docker
```

### Issue: "Permission denied" on Linux

```bash
# Solution: Add user to docker group
sudo usermod -aG docker $USER
# Log out and log back in

# Or run with sudo
sudo ./launch.sh
```

### Issue: "Container keeps restarting"

```bash
# Solution: Check logs for errors
docker-compose logs cofi-dashboard

# Check environment variables
docker exec cofi-dashboard env

# Verify .env file exists
ls -la cofi-dashboard/.env
```

---

## File Permissions (Linux/Mac)

Make scripts executable:

```bash
chmod +x build.sh launch.sh stop.sh
```

---

## Platform-Specific Notes

### Windows
- Use `.bat` versions of scripts
- Run in Command Prompt or PowerShell
- Docker Desktop must be running
- WSL users can use `.sh` scripts

### Linux
- Use `.sh` versions of scripts
- May need `sudo` for Docker commands
- Ensure Docker service is running: `sudo systemctl start docker`

### Mac
- Use `.sh` versions of scripts
- Docker Desktop must be running
- Scripts work in Terminal

---

## Summary

| Task | Linux/Mac | Windows |
|------|-----------|---------|
| Build images | `./build.sh` | `build.bat` |
| Start services | `./launch.sh` | `launch.bat` |
| Stop services | `./stop.sh` | `stop.bat` |
| View logs | `docker-compose logs -f` | `docker-compose logs -f` |
| Restart service | `docker-compose restart <service>` | `docker-compose restart <service>` |

All scripts feature:
- ✅ Smart skip logic (don't rebuild/restart if already done)
- ✅ Colored output for easy reading
- ✅ Error handling and validation
- ✅ Helpful status messages
- ✅ Service URL display

**You're ready to deploy! Run `./launch.sh` (or `launch.bat` on Windows) to get started.** 🚀
