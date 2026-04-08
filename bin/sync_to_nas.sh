#!/bin/bash

# Exit on error
set -e

# Variables
SOURCE_DIR="./"
DEST_DIR="/mnt/truenas/nfs/mcp"

echo "🚀 Syncing MCP files to TrueNAS..."

# Build exclusion list from .gitignore
# We extract lines that don't start with # and are not empty
GITIGNORE_EXCLUDES=$(grep -v '^#' .gitignore | grep -v '^$' | sed 's/^/--exclude="/' | sed 's/$/"/')

# Use rsync to sync files
# --archive: preserve permissions, timestamps, etc.
# --verbose: show progress
# --delete: remove files from destination that are no longer in source
rsync -av --delete \
    --exclude='.*' \
    --include='mcp-remote.iml' \
    ${GITIGNORE_EXCLUDES} \
    --exclude="push_to_hub.sh" \
    --exclude="sync_to_nas.sh" \
    --exclude="Dockerfile" \
    --exclude="uv.lock" \
    --exclude="docker-compose.yml" \
    --exclude="truenas-mcp.yaml" \
    --exclude="bin/" \
    "${SOURCE_DIR}" "${DEST_DIR}"

echo "✅ Sync complete! Files are now updated on TrueNAS."
