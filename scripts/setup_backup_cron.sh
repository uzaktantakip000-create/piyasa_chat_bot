#!/bin/bash
#
# Setup Automated Database Backups (Linux/macOS)
#
# This script configures a cron job to run daily database backups at 2 AM.
#
# Usage:
#   bash scripts/setup_backup_cron.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Database Backup Automation Setup${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Check if backup script exists
BACKUP_SCRIPT="$SCRIPT_DIR/backup_database.py"
if [ ! -f "$BACKUP_SCRIPT" ]; then
    echo -e "${RED}Error: Backup script not found at $BACKUP_SCRIPT${NC}"
    exit 1
fi

echo -e "${GREEN}[1/4]${NC} Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    exit 1
fi
echo -e "  ✅ Python 3 found: $(python3 --version)"

echo ""
echo -e "${GREEN}[2/4]${NC} Checking DATABASE_URL environment variable..."
if [ -z "$DATABASE_URL" ]; then
    echo -e "${YELLOW}Warning: DATABASE_URL not set in environment${NC}"
    echo -e "  Make sure to set it in your cron environment or .env file"
else
    echo -e "  ✅ DATABASE_URL: $DATABASE_URL"
fi

echo ""
echo -e "${GREEN}[3/4]${NC} Creating backup directory..."
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
mkdir -p "$BACKUP_DIR/daily"
mkdir -p "$BACKUP_DIR/weekly"
mkdir -p "$BACKUP_DIR/monthly"
echo -e "  ✅ Backup directory: $BACKUP_DIR"

echo ""
echo -e "${GREEN}[4/4]${NC} Setting up cron job..."

# Cron job definition
# Runs daily at 2:00 AM
CRON_SCHEDULE="0 2 * * *"
CRON_COMMAND="cd $PROJECT_DIR && /usr/bin/env python3 $BACKUP_SCRIPT --backup-dir $BACKUP_DIR >> $PROJECT_DIR/logs/backup.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "$BACKUP_SCRIPT"; then
    echo -e "${YELLOW}  ⚠️  Cron job already exists${NC}"
    echo -e "  Current crontab entries for backup:"
    crontab -l | grep "$BACKUP_SCRIPT"
    echo ""
    read -p "  Do you want to update it? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}  Skipping cron job setup${NC}"
        exit 0
    fi

    # Remove existing cron job
    crontab -l | grep -v "$BACKUP_SCRIPT" | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_SCHEDULE $CRON_COMMAND") | crontab -

echo -e "  ✅ Cron job added successfully"
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Backup schedule:"
echo -e "  • ${GREEN}Daily:${NC}   2:00 AM (keep last 7 days)"
echo -e "  • ${GREEN}Weekly:${NC}  2:00 AM on Sundays (keep last 4 weeks)"
echo -e "  • ${GREEN}Monthly:${NC} 2:00 AM on 1st of month (keep last 12 months)"
echo ""
echo -e "Backup location:"
echo -e "  ${BACKUP_DIR}"
echo ""
echo -e "Log file:"
echo -e "  ${PROJECT_DIR}/logs/backup.log"
echo ""
echo -e "Manual backup:"
echo -e "  python3 $BACKUP_SCRIPT"
echo ""
echo -e "View cron jobs:"
echo -e "  crontab -l"
echo ""
echo -e "Remove cron job:"
echo -e "  crontab -e"
echo ""
echo -e "${YELLOW}Note: Make sure DATABASE_URL is set in your environment or .env file${NC}"
echo ""
