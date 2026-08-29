#!/bin/bash

# Script to backup GX10 files to Mac using SSH
# This script automates the process of backing up important directories from GX10 to Mac
#
# Usage: ./backup_gx10_to_mac.sh [destination_dir]
# If no destination is provided, it uses ~/URA/backups/

set -e # Exit on any error

# Default backup directory
BACKUP_DIR="${1:-$HOME/URA/backups}"
SSH_USER="ramon"
GX10_HOST="100.72.103.12" # Using Tailscale IP
SOURCE_BASE="/home/${SSH_USER}/URA"

echo "Starting backup from GX10 (${GX10_HOST}) to ${BACKUP_DIR}"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Define directories and files to exclude or include based on URA's structure
EXCLUDES="--exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='.pytest_cache'"
EXCLUDES="$EXCLUDES --exclude='.mypy_cache' --exclude='.ruff_cache'"

# Backup important directories from GX10
echo "Backing up core URA directories..."
rsync -avzP $EXCLUDES ${SSH_USER}@${GX10_HOST}:${SOURCE_BASE}/core/ "$BACKUP_DIR/core/" || echo "Failed to backup core"
rsync -avzP $EXCLUDES ${SSH_USER}@${GX10_HOST}:${SOURCE_BASE}/motor/ "$BACKUP_DIR/motor/" || echo "Failed to backup motor"
rsync -avzP $EXCLUDES ${SSH_USER}@${GX10_HOST}:${SOURCE_BASE}/scripts/pro/ "$BACKUP_DIR/scripts/pro/" || echo "Failed to backup scripts"
rsync -avzP $EXCLUDES ${SSH_USER}@${GX10_HOST}:${SOURCE_BASE}/docs/ "$BACKUP_DIR/docs/" || echo "Failed to backup docs"
rsync -avzP $EXCLUDES ${SSH_USER}@${GX10_HOST}:${SOURCE_BASE}/tests/ "$BACKUP_DIR/tests/" || echo "Failed to backup tests"

# Backup config files and important data
echo "Backing up configuration files..."
mkdir -p "$BACKUP_DIR/config/"
rsync -avzP ${SSH_USER}@${GX10_HOST}:${SOURCE_BASE}/config/ "$BACKUP_DIR/config/"

# Backup the main URA application
echo "Backing up main URA script and config..."
rsync -avzP ${SSH_USER}@${GX10_HOST}:${SOURCE_BASE}/ura.py "$BACKUP_DIR/"
rsync -avzP ${SSH_USER}@${GX10_HOST}:${SOURCE_BASE}/pyproject.toml "$BACKUP_DIR/"
rsync -avzP ${SSH_USER}@${GX10_HOST}:${SOURCE_BASE}/Makefile "$BACKUP_DIR/"

echo "Backup completed to: $BACKUP_DIR"
