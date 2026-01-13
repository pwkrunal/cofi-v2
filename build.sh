#!/bin/bash

###############################################################################
# Cofi Services - Docker Build Script
# Builds Docker images for cofi-mediator, cofi-service, and cofi-dashboard
# Skips images that are already built
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Cofi Services - Docker Build Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to check if image exists
image_exists() {
    docker images -q "$1" 2>/dev/null | grep -q .
}

# Function to build image
build_image() {
    local name=$1
    local context=$2
    local tag=$3

    echo -e "${YELLOW}[BUILD]${NC} Checking image: ${BLUE}${tag}${NC}"

    if image_exists "${tag}"; then
        echo -e "${GREEN}[SKIP]${NC} Image ${tag} already exists"
        echo -e "       Use 'docker rmi ${tag}' to force rebuild"
        return 0
    fi

    echo -e "${YELLOW}[BUILD]${NC} Building ${name}..."
    if docker build -t "${tag}" "${context}"; then
        echo -e "${GREEN}[SUCCESS]${NC} Built ${tag}"
    else
        echo -e "${RED}[FAILED]${NC} Failed to build ${tag}"
        return 1
    fi
}

# Build all images
echo -e "${BLUE}Step 1/3: Building cofi-mediator${NC}"
build_image "cofi-mediator" "./cofi-mediator-service" "cofi-mediator:latest"
echo ""

echo -e "${BLUE}Step 2/3: Building cofi-service${NC}"
build_image "cofi-service" "./cofi-service" "cofi-service:latest"
echo ""

echo -e "${BLUE}Step 3/3: Building cofi-dashboard${NC}"
build_image "cofi-dashboard" "./cofi-dashboard" "cofi-dashboard:latest"
echo ""

# Summary
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Build Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Built images:"
docker images | grep -E "(REPOSITORY|cofi-mediator|cofi-service|cofi-dashboard)" | head -4
echo ""
echo -e "${YELLOW}Next step:${NC} Run './launch.sh' to start all services"
