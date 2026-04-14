#!/bin/bash

# Exit on error
set -e

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# Set the project root to one level up from the bin directory
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Variables
SOURCE_DIR="${PROJECT_ROOT}/"
DEST_DIR="/mnt/truenas/nfs/mcp"

echo "🚀 Syncing MCP files to TrueNAS..."

# Ensure we are looking for .gitignore in the project root
GITIGNORE_FILE="${PROJECT_ROOT}/.gitignore"

if [ -f "$GITIGNORE_FILE" ]; then
    GITIGNORE_EXCLUDES=$(grep -v '^#' "$GITIGNORE_FILE" | grep -v '^$' | sed 's/^/--exclude="/' | sed 's/$/"/')
else
    echo "⚠️ Warning: .gitignore not found at $GITIGNORE_FILE"
    GITIGNORE_EXCLUDES=""
fi

# Use rsync with modified flags for NFS:
# -rlD: replaces -a (archive) but omits -t (times), -o (owner), and -g (group)
# --no-perms: avoid trying to set permissions that the NFS share might reject
rsync -rlptD --no-owner --no-group --no-perms --verbose --delete \
    --exclude='.*' \
    --exclude='**/__pycache__/' \
    --exclude='tmp/' \
    ${GITIGNORE_EXCLUDES} \
    --include='mcp-remote.iml' \
    --exclude='*.iml' \
    --exclude='*.log' \
    --exclude="bin/" \
    --exclude="push_to_hub.sh" \
    --exclude="sync_to_nas.sh" \
    --exclude="Dockerfile" \
    --exclude="uv.lock" \
    --exclude="docker-compose.yml" \
    --exclude="truenas-mcp.yaml" \
    "${SOURCE_DIR}" "${DEST_DIR}"

echo "✅ Sync complete! Files are now updated on TrueNAS."
