#!/bin/bash

# Exit on error
set -e

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# Set the project root to one level up from the bin directory
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Variables
IMAGE_NAME="kkulagin/mcp-servers"
UNIQUE_TAG="$(date +%Y%m%d%H%M)"
LATEST_TAG="latest"

echo "🚀 Starting build for ${IMAGE_NAME}:${UNIQUE_TAG}..."

# 2. Build the image with the unique tag

# 1. Build the Docker image
# We explicitly set the build context to the PROJECT_ROOT so that
# Docker can find the Dockerfile and pyproject.toml
echo "📦 Building Docker image from ${PROJECT_ROOT}..."
docker build -t ${IMAGE_NAME}:${UNIQUE_TAG} "${PROJECT_ROOT}"
docker tag ${IMAGE_NAME}:${UNIQUE_TAG} ${IMAGE_NAME}:${LATEST_TAG}

# 2. Push the image to Docker Hub
echo "📤 Pushing image to Docker Hub..."
docker push ${IMAGE_NAME}:${UNIQUE_TAG}
docker push ${IMAGE_NAME}:${LATEST_TAG}

echo "✅ Successfully pushed ${IMAGE_NAME}:${TAG} to Docker Hub!"
