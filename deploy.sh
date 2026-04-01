#!/usr/bin/env bash
# Deploy piqued to Docker host.
# Run from: dev/piqued/
#
# This copies the build context to the Docker host, then prints
# the commands to run there. Claude can't run docker commands via SSH.
set -euo pipefail

DOCKER_HOST="homeflix"
DEPLOY_PATH="/mnt/apps/piqued"
BUILD_PATH="${DEPLOY_PATH}/build"

echo "=== Deploying Piqued to ${DOCKER_HOST} ==="

# Copy build context (exclude test files, caches, local DBs)
echo "Copying source to ${DOCKER_HOST}:${BUILD_PATH}..."
ssh ${DOCKER_HOST} "mkdir -p ${BUILD_PATH} ${DEPLOY_PATH}/secrets"
rsync -av --delete \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '*.db' \
    --exclude '.env' \
    --exclude 'tests/' \
    --exclude '.gitignore' \
    . ${DOCKER_HOST}:${BUILD_PATH}/

echo ""
echo "=== Source deployed. Run these on the Docker host: ==="
echo ""
echo "  cd ${BUILD_PATH}"
echo "  docker compose build"
echo "  docker compose up -d"
echo ""
echo "=== First-time setup: ==="
echo ""
echo "  No secret files needed — configure via web UI at http://HOST:8400/settings"
