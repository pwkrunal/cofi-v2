#!/bin/bash

###############################################################################
# Cofi Services - Docker Stop Script
# Stops all running Cofi services
###############################################################################

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Cofi Services - Docker Stop Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Stop services using docker-compose
echo -e "${YELLOW}Stopping all Cofi services...${NC}"
docker-compose down

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  All services stopped${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}To start again:${NC} Run './launch.sh'"
echo -e "${YELLOW}To remove images:${NC} Run 'docker-compose down --rmi all'"
