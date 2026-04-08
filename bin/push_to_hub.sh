#!/bin/bash

# Exit on error
set -e

# Variables
IMAGE_NAME="kkulagin/mcp-servers"
TAG="latest"

echo "🚀 Starting build and push process for ${IMAGE_NAME}:${TAG}..."

# 1. Build the Docker image
echo "📦 Building Docker image..."
docker build -t ${IMAGE_NAME}:${TAG} .

# 2. Push the image to Docker Hub
echo "📤 Pushing image to Docker Hub..."
docker push ${IMAGE_NAME}:${TAG}

echo "✅ Successfully pushed ${IMAGE_NAME}:${TAG} to Docker Hub!"
echo "You can find it at: https://hub.docker.com/repositories/kkulagin"
