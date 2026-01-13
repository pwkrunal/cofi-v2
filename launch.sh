#!/bin/bash

###############################################################################
# Cofi Services - Docker Launch Script
# Starts cofi-mediator, cofi-api, and cofi-dashboard services
# Skips containers that are already running
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Cofi Services - Docker Launch Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to check if container is running
container_running() {
    docker ps --filter "name=$1" --filter "status=running" --format "{{.Names}}" | grep -q "^$1$"
}

# Function to check if container exists (running or stopped)
container_exists() {
    docker ps -a --filter "name=$1" --format "{{.Names}}" | grep -q "^$1$"
}

# Function to check if image exists
image_exists() {
    docker images -q "$1" 2>/dev/null | grep -q .
}

# Function to start service
start_service() {
    local service_name=$1
    local container_name=$2

    echo -e "${YELLOW}[CHECK]${NC} Service: ${BLUE}${service_name}${NC} (${container_name})"

    # Check if already running
    if container_running "${container_name}"; then
        echo -e "${GREEN}[SKIP]${NC} Container ${container_name} is already running"
        return 0
    fi

    # Check if container exists but stopped
    if container_exists "${container_name}"; then
        echo -e "${YELLOW}[START]${NC} Starting existing container ${container_name}..."
        docker start "${container_name}"
        echo -e "${GREEN}[SUCCESS]${NC} Started ${container_name}"
        return 0
    fi

    # Container doesn't exist, use docker-compose
    echo -e "${YELLOW}[CREATE]${NC} Creating and starting ${container_name}..."
    docker-compose up -d "${service_name}"
    echo -e "${GREEN}[SUCCESS]${NC} Created and started ${container_name}"
}

# Check if docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}[ERROR]${NC} Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if docker-compose.yml exists
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}[ERROR]${NC} docker-compose.yml not found in current directory"
    exit 1
fi

# Check if images are built
echo -e "${BLUE}Checking Docker images...${NC}"
missing_images=false

if ! image_exists "cofi-mediator:latest"; then
    echo -e "${RED}[MISSING]${NC} Image cofi-mediator:latest not found"
    missing_images=true
fi

if ! image_exists "cofi-service:latest"; then
    echo -e "${RED}[MISSING]${NC} Image cofi-service:latest not found"
    missing_images=true
fi

if ! image_exists "cofi-dashboard:latest"; then
    echo -e "${RED}[MISSING]${NC} Image cofi-dashboard:latest not found"
    missing_images=true
fi

if [ "$missing_images" = true ]; then
    echo ""
    echo -e "${YELLOW}[ACTION REQUIRED]${NC} Some images are missing. Run './build.sh' first."
    exit 1
fi

echo -e "${GREEN}[OK]${NC} All images found"
echo ""

# Create network if it doesn't exist
echo -e "${BLUE}Checking Docker network...${NC}"
if ! docker network inspect auditnex-network > /dev/null 2>&1; then
    echo -e "${YELLOW}[CREATE]${NC} Creating network auditnex-network..."
    docker network create auditnex-network
    echo -e "${GREEN}[SUCCESS]${NC} Network created"
else
    echo -e "${GREEN}[OK]${NC} Network auditnex-network exists"
fi
echo ""

# Start services
echo -e "${BLUE}Starting services...${NC}"
echo ""

start_service "cofi-mediator" "cofi-mediator-service"
echo ""

start_service "cofi-api" "cofi-api"
echo ""

start_service "cofi-dashboard" "cofi-dashboard"
echo ""

# Note: cofi-service is not started automatically (restart: "no")
if container_exists "cofi-service"; then
    if container_running "cofi-service"; then
        echo -e "${CYAN}[INFO]${NC} Batch processing service (cofi-service) is running"
    else
        echo -e "${CYAN}[INFO]${NC} Batch processing service (cofi-service) exists but stopped"
        echo -e "       This service runs batch jobs on-demand"
        echo -e "       Start manually: ${YELLOW}docker start cofi-service${NC}"
    fi
else
    echo -e "${CYAN}[INFO]${NC} Batch processing service (cofi-service) will be created on first run"
    echo -e "       Start manually: ${YELLOW}docker-compose up -d cofi-service${NC}"
fi
echo ""

# Wait for services to be healthy
echo -e "${BLUE}Waiting for services to be ready...${NC}"
sleep 3

# Check service status
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Services Status${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

docker ps --filter "name=cofi-mediator-service" --filter "name=cofi-api" --filter "name=cofi-dashboard" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Launch Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Service URLs:"
echo -e "  ${CYAN}Mediator API:${NC}   http://localhost:5065"
echo -e "  ${CYAN}Cofi API:${NC}       http://localhost:5064"
echo -e "  ${CYAN}Dashboard:${NC}      http://localhost:5066"
echo ""
echo -e "${YELLOW}Commands:${NC}"
echo -e "  View logs:        ${BLUE}docker-compose logs -f [service-name]${NC}"
echo -e "  Stop all:         ${BLUE}./stop.sh${NC} or ${BLUE}docker-compose down${NC}"
echo -e "  Restart service:  ${BLUE}docker-compose restart [service-name]${NC}"
echo -e "  Run batch job:    ${BLUE}docker-compose up cofi-service${NC}"
echo ""
