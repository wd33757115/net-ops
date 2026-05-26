#!/usr/bin/env bash
# 生产环境 - 启动（Linux）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/deployment/docker-compose.yml"
WAIT_SECONDS="${WAIT_SECONDS:-45}"

USE_V2="${USE_SUPERVISOR_V2:-true}"
export USE_SUPERVISOR_V2="$USE_V2"

echo "============================================================"
echo "  NetOps 生产环境 - 启动 (USE_SUPERVISOR_V2=$USE_V2)"
echo "============================================================"

cd "$PROJECT_ROOT"
docker compose -f "$COMPOSE_FILE" up -d

echo "等待服务就绪 (${WAIT_SECONDS}s) ..."
sleep "$WAIT_SECONDS"

docker compose -f "$COMPOSE_FILE" exec -T django \
  python manage.py migrate --noinput || true

docker compose -f "$COMPOSE_FILE" ps

echo "[完成] React: http://localhost:3000  Django: http://localhost:8001"
