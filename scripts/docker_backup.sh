#!/bin/bash
#
# Docker Container Database Backup Script
#
# Runs backup inside the API container for Docker deployments.
# Can be run from host or scheduled in container.
#
# Usage:
#   bash scripts/docker_backup.sh [daily|weekly|monthly]
#

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Default values
BACKUP_TYPE="${1:-auto}"
CONTAINER_NAME="${CONTAINER_NAME:-piyasa_chat_bot-api-1}"
BACKUP_HOST_DIR="${BACKUP_HOST_DIR:-./backups}"

echo -e "${GREEN}Docker Database Backup${NC}"
echo ""

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Error: Container $CONTAINER_NAME is not running"
    exit 1
fi

echo "Container: $CONTAINER_NAME"
echo "Backup type: $BACKUP_TYPE"
echo "Host backup directory: $BACKUP_HOST_DIR"
echo ""

# Create backup directory on host
mkdir -p "$BACKUP_HOST_DIR"

# Run backup inside container
echo "Running backup..."
if [ "$BACKUP_TYPE" = "auto" ]; then
    docker exec $CONTAINER_NAME python scripts/backup_database.py \
        --backup-dir /backups
else
    docker exec $CONTAINER_NAME python scripts/backup_database.py \
        --backup-dir /backups \
        --type "$BACKUP_TYPE"
fi

# Copy backups from container to host (if using volume)
# Note: If using Docker volume, backups are already on host
echo ""
echo -e "${GREEN}✅ Backup completed${NC}"
echo ""
echo "Backup location (inside container): /backups"
echo "Backup location (host): $BACKUP_HOST_DIR"
echo ""
echo "To access backups:"
echo "  ls -lh $BACKUP_HOST_DIR/daily/"
echo "  ls -lh $BACKUP_HOST_DIR/weekly/"
echo "  ls -lh $BACKUP_HOST_DIR/monthly/"
echo ""
