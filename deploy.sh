#!/bin/bash
# Deploy script for irm-api-bot-dc (bot_dc)
# Called by Jenkins or manually
# Assumes running on the host

set -e

REPO_DIR="/home/gery/Documents/projects/AI/bot_dc"
START_TIME=$(date +%s)

echo "=== Deploy: bot_dc (Kei) ==="

# 1. Pull latest from git
echo "--- Pulling latest ---"
cd "$REPO_DIR"
git pull origin master

# 2. Build & restart container
echo "--- Rebuilding container ---"
docker compose build --no-cache
docker compose up -d

# 3. Verify
sleep 3
echo "--- Verifying ---"
docker ps --filter name=irm-api-bot-dc --format "{{.Names}} {{.Status}}"

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
echo "=== Deploy complete in ${DURATION}s ==="
